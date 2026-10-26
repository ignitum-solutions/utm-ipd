"""UI-independent simulation services used by HTTP and local research tests."""
from __future__ import annotations

import random
from pathlib import Path
from typing import Callable

import axelrod as axl
import numpy as np
import yaml

from backend.models import MoranRequest, Parameters, TournamentRequest, TrustRequest
from dash.opponents import build_extra_opponent, extra_opponent_options
from strategies.utm_pure import TrustOnlyIPDStrategy
from strategies.utm_tft import UTMTFT
from strategies.utm_tft_wsls import UTMTFT_WSLS
from strategies.utm_wsls import UTMWSLS
from tournaments.run_round_robin import run_tournament
from utm.trust_meter import TrustMeter
from backend.provenance import provenance

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = {"TFT": UTMTFT, "WSLS": UTMWSLS, "TFT→WSLS": UTMTFT_WSLS, "Trust-only IPD": TrustOnlyIPDStrategy}
STRATEGIES = {cls.name: cls for cls in axl.strategies}
Emit = Callable[[dict], None]


def load_presets() -> dict:
    # This optional override matches the local research dashboard behavior.
    import os
    uri = os.getenv("PRESETS_S3_URI", str(ROOT / "config/presets.yaml"))
    if uri.startswith("s3://"):
        import boto3
        bucket, key = uri[5:].split("/", 1)
        source = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    else:
        source = Path(uri).read_text(encoding="utf-8")
    return yaml.safe_load(source) or {}


def catalogue() -> dict:
    import os
    return {
        "variants": list(REGISTRY), "opponents": sorted(STRATEGIES),
        "extra_opponents": extra_opponent_options(), "presets": load_presets(),
        "submissions_enabled": bool(os.getenv("SUBMIT_PREFIX")),
        "version": os.getenv("GIT_SHA", "local"),
    }


def validate_selections(cfg: TournamentRequest, presets: dict) -> None:
    if any(name not in STRATEGIES for name in cfg.opponents):
        raise ValueError("Choose opponents from the approved strategy list.")
    if any(name not in presets for name in cfg.presets):
        raise ValueError("Choose an existing personality preset.")
    if cfg.extra_opponent not in extra_opponent_options():
        raise ValueError("Choose an approved extra opponent.")


def player(cfg: Parameters):
    return REGISTRY[cfg.variant](cfg.theta, cfg.alpha_pos, cfg.alpha_neg, cfg.delta, cfg.threshold)


def preset_player(spec: dict, fallback: Parameters):
    """Resolve incomplete presets against the actual requested focal settings."""
    return player(Parameters(
        theta=spec.get("theta", fallback.theta), alpha_pos=spec.get("alpha_pos", fallback.alpha_pos),
        alpha_neg=spec.get("alpha_neg", fallback.alpha_neg), delta=spec.get("delta", fallback.delta),
        threshold=spec.get("tau", fallback.threshold), variant=spec.get("variant", fallback.variant),
    ))


def progress(emit: Emit, phase: str, done: int, total: int):
    emit({"type": "progress", "phase": phase, "completed": done, "total": total,
          "percent": round(100 * done / total, 1) if total else None})


def tournament(cfg: TournamentRequest, emit: Emit, checkpoint: Callable, presets: dict | None = None) -> dict:
    presets = load_presets() if presets is None else presets
    validate_selections(cfg, presets)
    players = [player(cfg)] + [STRATEGIES[name]() for name in cfg.opponents]
    for name in cfg.presets:
        spec = presets[name]
        p = preset_player(spec, cfg)
        p.name = f"UTM-{name}"
        players.append(p)
    extra = build_extra_opponent(cfg.extra_opponent, noise_wrap=cfg.noise_wrap)
    if extra is not None:
        players.append(extra)
    metadata = provenance("tournament", players)
    leaderboard, results = run_tournament(
        players, turns=cfg.rounds, repetitions=cfg.repetitions, seed=cfg.seed,
        noise=cfg.noise_pct / 100, quiet=True, return_results=True,
        progress_callback=lambda done, total: progress(emit, "Simulating player pairs", done, total),
        checkpoint=checkpoint,
    )
    emit({"type": "progress", "phase": "Preparing charts and downloads", "percent": None})
    checkpoint()
    return {
        "kind": "tournament", "config": cfg.model_dump(), "metadata": metadata,
        "leaderboard": leaderboard.to_dict(orient="records"),
        "players": [str(p) for p in players],
        "scores": [[float(v) for v in values] for values in results.normalised_scores],
        "payoff_matrix": [[float(v) for v in row] for row in results.payoff_matrix],
        "wins": [[float(v) for v in values] for values in results.wins],
        "cooperation_counts": [[int(v) for v in row] for row in results.cooperation],
        "match_lengths": results.match_lengths,
    }


def moran(cfg: MoranRequest, emit: Emit, checkpoint: Callable) -> dict:
    utm = player(cfg)
    label = str(utm)
    population = [utm] + [axl.Cooperator() for _ in range(cfg.population - 1)]
    metadata = provenance("moran", population)
    process = axl.MoranProcess(population, turns=cfg.rounds, seed=cfg.seed, game=axl.Game(r=3, s=0, t=5, p=1))
    shares = [1 / cfg.population]
    fixation = None
    for generation in range(1, cfg.generations + 1):
        checkpoint()
        try:
            next(process)
        except StopIteration:
            break
        share = process.populations[-1].get(label, 0) / cfg.population
        shares.append(share)
        progress(emit, "Evolving population", generation, cfg.generations)
        if share in (0, 1):
            fixation = generation
            break
    return {"kind": "moran", "config": cfg.model_dump(), "metadata": metadata, "series": shares,
            "summary": {"Final UTM share": shares[-1], "Mean UTM share": float(np.mean(shares)),
                        "Generations completed": len(shares) - 1, "Fixation generation": fixation}}


def trust_game(cfg: TrustRequest, emit: Emit, checkpoint: Callable) -> dict:
    metadata = provenance("trust")
    rng = random.Random(cfg.seed)
    trust = TrustMeter(cfg.theta, cfg.alpha_pos, cfg.alpha_neg, cfg.delta)
    values, payoffs, cumulative, sends = [], [], [], []
    for index in range(cfg.rounds):
        checkpoint()
        betrayed = rng.random() < cfg.betrayal_probability
        sent = cfg.send if trust.value >= cfg.threshold else 0.0
        payoff = sent * 3 * (cfg.return_bad if betrayed else cfg.return_good) - sent
        trust.observe(1 if payoff >= 0 else -1)
        values.append(trust.value)
        payoffs.append(payoff)
        cumulative.append(sum(payoffs))
        sends.append(sent)
        progress(emit, "Playing investment rounds", index + 1, cfg.rounds)
    return {"kind": "trust", "config": cfg.model_dump(), "metadata": metadata, "series": values,
            "payoffs": payoffs, "cumulative": cumulative, "investments": sends,
            "summary": {"Final trust": values[-1], "Cumulative payoff": cumulative[-1],
                        "Nonnegative payoff fraction": sum(p >= 0 for p in payoffs) / cfg.rounds,
                        "Investment fraction": sum(s > 0 for s in sends) / cfg.rounds}}


def simulate(kind: str, config: dict, emit: Emit, checkpoint: Callable, presets=None) -> dict:
    if kind == "tournament":
        return tournament(TournamentRequest(**config), emit, checkpoint, presets)
    if kind == "moran":
        return moran(MoranRequest(**config), emit, checkpoint)
    if kind == "trust":
        return trust_game(TrustRequest(**config), emit, checkpoint)
    raise ValueError("Unknown simulation.")
