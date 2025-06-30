from __future__ import annotations
import importlib, logging, random
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import List, Tuple

import axelrod as axl
import numpy as np
import pandas as pd
import tqdm as _tqdm_mod

from strategies.utm_tft import UTMTFT
from strategies.utm_wsls import UTMWSLS
from strategies.utm_tft_wsls import UTMTFT_WSLS
from tournaments.run_round_robin import run_tournament
from dash.shared import PRESETS

logger = logging.getLogger("utm.ipd")
EXECUTOR = ThreadPoolExecutor(max_workers=1)

UTM_REGISTRY = {
    "TFT": UTMTFT,
    "WSLS": UTMWSLS,
    "TFT→WSLS": UTMTFT_WSLS,
}

ReturnType = Tuple[pd.DataFrame, List[axl.Player], axl.ResultSet | None]

def _df_from_summary(s):
    if isinstance(s, pd.DataFrame):
        return s.reset_index(drop=True)
    if isinstance(s, list):
        if not s:
            return pd.DataFrame()
        if isinstance(s[0], dict):
            return pd.DataFrame(s).reset_index(drop=True)
        if isinstance(s[0], (list, tuple)):
            if any(str(x).lower() == "mean" for x in s[0]):
                hdr, *data = s
                return pd.DataFrame(data, columns=[str(c) for c in hdr]).reset_index(drop=True)
            return pd.DataFrame(s).reset_index(drop=True)
    raise TypeError("unexpected summary format")

def _patch_tqdm(progress_q: Queue):
    orig_tqdm = _tqdm_mod.tqdm
    def _streamlit_tqdm(*args, **kwargs):
        bar = orig_tqdm(*args, **kwargs)
        progress_q.put((0, bar.total))
        orig_update = bar.update
        def update(n=1, _=None):
            orig_update(n)
            progress_q.put((bar.n, bar.total))
        bar.update = update
        return bar
    _tqdm_mod.tqdm = _streamlit_tqdm

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
    random.seed(seed)
    np.random.seed(seed)
    _patch_tqdm(progress_q)

    players: List[axl.Player] = [
        next(cls for cls in axl.strategies if cls.name == n)() for n in selected_names
    ]

    for name in utm_presets:
        spec = PRESETS.get(name, {})
        variant = spec.get("variant", utm_variant)
        cls = UTM_REGISTRY.get(variant, UTMTFT)
        p = cls(
            spec.get("theta", theta),
            spec.get("alpha_pos", alpha_pos),
            spec.get("alpha_neg", alpha_neg),
            spec.get("delta", delta),
            spec.get("tau", threshold),
        )
        p.name = f"UTM-{name}"
        players.append(p)

    if extra_cls:
        try:
            mod, c = extra_cls.rsplit(".", 1)
            cls = getattr(importlib.import_module(mod), c)
            p: axl.Player = cls()
            if noise_wrap:
                p = axl.Noise(p, noise=0.05)
            players.append(p)
        except Exception as exc:
            logger.warning("Could not load extra opponent '%s': %s", extra_cls, exc)

    players.insert(0, UTM_REGISTRY[utm_variant](theta, alpha_pos, alpha_neg, delta, threshold))

    if noise_pct == 0:
        leaderboard_df, results = run_tournament(
            players,
            turns=rounds,
            repetitions=reps,
            seed=seed,
            quiet=False,
            csv_dir=None,
            return_results=True,
        )
    else:
        tournament = axl.Tournament(
            players,
            turns=rounds,
            repetitions=reps,
            seed=seed,
            noise=noise_pct / 100.0,
        )
        results = tournament.play(progress_bar=True)
        leaderboard_df = _df_from_summary(results.summarise())

    progress_q.put(("done", "done"))
    logger.info("Run summary:\n%s", leaderboard_df.to_string(index=False))
    return leaderboard_df.reset_index(drop=True), players, results

run_async = background_task
__all__ = ["EXECUTOR", "run_async"]
