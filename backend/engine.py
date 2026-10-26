"""UI-independent simulation services used by HTTP and local research tests."""
from __future__ import annotations

from typing import Callable

import axelrod as axl
import numpy as np

from backend.models import MoranRequest, Parameters, TournamentRequest, TrustRequest
from dash.opponents import build_extra_opponent
from strategies.utm_pure import TrustOnlyIPDStrategy
from strategies.utm_tft import UTMTFT
from strategies.utm_tft_wsls import UTMTFT_WSLS
from strategies.utm_wsls import UTMWSLS
from tournaments.run_round_robin import run_tournament
from backend.provenance import provenance
from backend.catalogue import catalogue, load_presets, validate_selections
from backend.trust_game import trust_game

REGISTRY = {"TFT": UTMTFT, "WSLS": UTMWSLS, "TFT→WSLS": UTMTFT_WSLS, "Trust-only IPD": TrustOnlyIPDStrategy}
STRATEGIES = {cls.name: cls for cls in axl.strategies}
Emit = Callable[[dict], None]


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


def simulate(kind: str, config: dict, emit: Emit, checkpoint: Callable, presets=None) -> dict:
    if kind == "tournament":
        return tournament(TournamentRequest(**config), emit, checkpoint, presets)
    if kind == "moran":
        return moran(MoranRequest(**config), emit, checkpoint)
    if kind == "trust":
        return trust_game(TrustRequest(**config), emit, checkpoint)
    raise ValueError("Unknown simulation.")
