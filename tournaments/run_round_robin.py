# tournaments/run_round_robin.py
"""
Round-robin driver for Iterated Prisoner’s Dilemma experiments that use UTM.

This file is *IPD-specific* glue around Axelrod-Python.  It does **not**
contain any UTM maths; instead it:

1. Receives a list of `axelrod.Player` objects (some may wrap UTM).
2. Runs an Axelrod tournament (turns × repetitions).
3. Returns a `pandas.DataFrame` leaderboard plus (optionally) the raw
   `axl.ResultSet` for downstream plotting.

If you adapt UTM to another repeated-game domain,
replace only this runner and the reward-mapping code in `utm/trust_meter.py`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union

import axelrod as axl
import numpy as np
import pandas as pd

log = logging.getLogger("utm.ipd")
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _scores_stats(results: axl.ResultSet, player_names: list[str]) -> tuple[list[float], list[float], list[float]]:
    """
    Extract mean, median, stdev per player in a version-agnostic way.

    Axelrod-Python changed its API around v5 → v6.  This helper shields us
    from that by picking whichever attribute exists.

    Returns
    -------
    means, medians, stds : lists of float (one element per player)
    """
    if hasattr(results, "mean_score_per_player"):  # ≥ v6.0
        return (
            list(results.mean_score_per_player),
            list(results.median_score_per_player),
            list(results.score_std_per_player),
        )

    # Fallback for v5.x
    try:
        nscores = results.normalised_scores
    except AttributeError as exc:  # pragma: no cover
        raise RuntimeError("Unsupported Axelrod version – cannot retrieve scores") from exc

    means   = [float(np.mean(s))   if s else float("nan") for s in nscores]
    medians = [float(np.median(s)) if s else float("nan") for s in nscores]
    stds    = [float(np.std(s))    if s else float("nan") for s in nscores]
    return means, medians, stds

def _coop_rates(resultset: axl.ResultSet) -> list[float]:
    """
    Return per-player cooperation rates (decimals in [0, 1]).

    Works with all known Axelrod versions.
    """
    # Newer field first
    for attr in (
        "cooperating_rating",           # ≥ 6.0
        "cooperation_rate_per_player",  # some dev snapshots
        "normalised_cooperation_rates", # ≤ 5.x
    ):
        if hasattr(resultset, attr):
            return list(map(float, getattr(resultset, attr)))

    # Last-ditch: average the NxN matrix that is always present
    if hasattr(resultset, "normalised_cooperation"):
        mat = resultset.normalised_cooperation
        n   = len(mat)
        return [float(np.mean([mat[i][j] for j in range(n) if j != i]))
                for i in range(n)]

    raise AttributeError("ResultSet has no cooperation-rate data.")

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def run_tournament(
    players: Iterable[axl.Player],
    *,
    turns: int = 200,
    repetitions: int = 30,
    seed: Optional[int] = 42,
    quiet: bool = False,
    csv_dir: Optional[str] = None,
    return_results: bool = False,
) -> Union[pd.DataFrame, Tuple[pd.DataFrame, axl.ResultSet]]:
    """
    Execute a round-robin IPD tournament and return a leaderboard.

    Parameters
    ----------
    players : iterable of `axelrod.Player`
        Instances to include in the tournament.  They can be pure Axelrod
        strategies, UTM-wrapped strategies, or any mix.
    turns : int, default 200
        Number of turns per match.
    repetitions : int, default 30
        Re-runs of the entire round-robin (handles stochastic strategies).
    seed : int or None, default 42
        RNG seed used by Axelrod’s tournament for reproducibility.
    quiet : bool, default False
        Suppress progress bar and most logging.
    csv_dir : str or None, default None
        Directory in which Axelrod should dump per-match CSV files.
        None → disable CSV output.
    return_results : bool, default False
        If *True*, returns a ``(DataFrame, ResultSet)`` tuple; otherwise
        just the leaderboard DataFrame.

    Returns
    -------
    pandas.DataFrame
        Columns: Strategy | Mean | Median | Stdev | % Coop
    axl.ResultSet, optional
        Only if *return_results* is True.

    Notes
    -----
    * Mean, median, stdev are computed on *normalised* scores (0–5 scale).
    * `% Coop` is the per-player cooperation rate across the entire run.
    * CSV output uses Axelrod’s built-in mechanism, controlled via env vars.
    """

    player_names = [str(p) for p in players]
    log.info(
        "Tournament config → players=%s | turns=%d | reps=%d | seed=%s | csv_dir=%s",
        player_names, turns, repetitions, seed, csv_dir or "disabled",
    )

    # ------------------------------------------------------------------
    # Axelrod CSV behaviour (IPD-library detail, not UTM)
    # ------------------------------------------------------------------
    if csv_dir is None:
        os.environ["AXELROD_SAVE_INTERACTIONS"] = "0"
    else:
        out = Path(csv_dir).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        os.environ["AXELROD_SAVE_INTERACTIONS"] = "1"
        os.environ["AXELROD_OUTPUT_DIR"] = str(out)
        log.info("CSV writing enabled → %s", out)

    # ------------------------------------------------------------------
    # Run tournament
    # ------------------------------------------------------------------
    tournament = axl.Tournament(
        list(players), turns=turns, repetitions=repetitions, seed=seed
    )
    log.info("Playing tournament…")
    results = tournament.play(progress_bar=not quiet)
    log.info("Tournament complete")

    means, medians, stds = _scores_stats(results, player_names)

    # ------------------------------------------------------------------
    # Cooperation statistics (API changed v5 → v6)
    # ------------------------------------------------------------------
    
    coop_rates = _coop_rates(results)
    coop_pct      = [round(r * 100, 1) for r in coop_rates]
    total_turns   = turns * repetitions * (len(players) - 1)
    coop_counts   = [int(round(r * total_turns)) for r in coop_rates]
    defect_counts = [total_turns - c for c in coop_counts]

    summary = pd.DataFrame(
        {
            "Strategy": player_names,
            "Mean":    [round(m, 3) for m in means],
            "Median":  [round(m, 3) for m in medians],
            "Stdev":   [round(s, 3) for s in stds],
            "% Coop":  coop_pct,
        }
    )
    log.info("Run summary:\n%s", summary.to_string(index=False))

    # ------------------------------------------------------------------
    # Diagnostic leaderboard (adds counts of C/D)
    # ------------------------------------------------------------------

    df = pd.DataFrame(
        {
            "Player":  player_names,
            "Mean":    means,
            "Median":  medians,
            "Stdev":   stds,
            "#C":      coop_counts,
            "#D":      defect_counts,
            "C-rate":  [round(r, 3) if not np.isnan(r) else np.nan for r in coop_rates],
        }
    ).sort_values("Mean", ascending=False).reset_index(drop=True)

    if not quiet:
        try:
            log.info("Leaderboard with diagnostics:\n%s", df.to_markdown(index=False))
        except Exception:
            log.info("Leaderboard with diagnostics:\n%s", df.to_string(index=False))

    return (df, results) if return_results else df
