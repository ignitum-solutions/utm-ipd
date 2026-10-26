from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import List, Tuple

import axelrod as axl
import pandas as pd

from strategies.utm_tft import UTMTFT
from strategies.utm_wsls import UTMWSLS
from strategies.utm_tft_wsls import UTMTFT_WSLS
from strategies.utm_pure      import TrustOnlyIPDStrategy
from tournaments.run_round_robin import run_tournament
from dash.opponents import build_extra_opponent
from dash.shared import PRESETS
from backend.engine import preset_player
from backend.models import Parameters

logger = logging.getLogger("utm.ipd")
EXECUTOR = ThreadPoolExecutor(max_workers=1)

UTM_REGISTRY = {
    "TFT": UTMTFT,
    "WSLS": UTMWSLS,
    "TFT→WSLS": UTMTFT_WSLS,
    "Trust-only IPD": TrustOnlyIPDStrategy,
}

ReturnType = Tuple[pd.DataFrame, List[axl.Player], axl.ResultSet | None]

def background_task(
    *,
    utm_presets: list[str],
    utm_variant: str,
    theta: float,
    alpha_pos: float,
    alpha_neg: float,
    delta: float,
    threshold: float,
    rounds: int,
    reps: int,
    seed: int,
    selected_names: list[str],
    extra_cls: str,
    noise_wrap: bool,
    noise_pct: int,
    progress_q: Queue,
) -> ReturnType:
    players: List[axl.Player] = [
        next(cls for cls in axl.strategies if cls.name == n)() for n in selected_names
    ]

    for name in utm_presets:
        spec = PRESETS.get(name, {})
        p = preset_player(spec, Parameters(theta=theta, alpha_pos=alpha_pos, alpha_neg=alpha_neg,
                                          delta=delta, threshold=threshold, variant=utm_variant))
        p.name = f"UTM-{name}"
        players.append(p)

    try:
        extra_player = build_extra_opponent(extra_cls, noise_wrap=noise_wrap)
    except ValueError:
        logger.warning("Rejected unsupported extra opponent '%s'", extra_cls)
        raise
    if extra_player is not None:
        players.append(extra_player)

    players.insert(0, UTM_REGISTRY[utm_variant](theta, alpha_pos, alpha_neg, delta, threshold))

    leaderboard_df, results = run_tournament(
        players, turns=rounds, repetitions=reps, seed=seed,
        noise=noise_pct / 100.0, quiet=True, return_results=True,
        progress_callback=lambda done, total: progress_q.put((done, total)),
    )

    progress_q.put(("done", "done"))
    logger.info("Run summary:\n%s", leaderboard_df.to_string(index=False))
    return leaderboard_df.reset_index(drop=True), players, results

run_async = background_task
__all__ = ["EXECUTOR", "run_async"]
