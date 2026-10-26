"""Axelrod round robin with uniform, explicit aggregation for every player.

Self-play is simulated by Axelrod but excluded from leaderboard aggregates.
Rows identify player slots. Raw match CSVs can be
retained with csv_dir; JSON services also expose per-repetition observations.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

import axelrod as axl
import numpy as np
import pandas as pd

from tournaments.progress import ProgressTournament

log = logging.getLogger("utm.ipd")


def focal_mean(frame: pd.DataFrame, player_index: int = 0) -> float:
    """Select an exact input slot, irrespective of labels or leaderboard order."""
    rows = frame.loc[frame["Player index"] == player_index, "Mean"]
    if len(rows) != 1:
        raise ValueError("The focal player slot is missing or duplicated.")
    value = float(rows.iloc[0])
    if not np.isfinite(value):
        raise ValueError("The focal player score is not finite.")
    return value


def run_tournament(
    players: Iterable[axl.Player], *, turns: int = 200, repetitions: int = 30,
    seed: int | None = 42, noise: float = 0.0, quiet: bool = False,
    csv_dir: str | None = None, return_results: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
    checkpoint: Callable[[], None] | None = None, game: axl.Game | None = None,
):
    """Return full-precision statistics; reject invalid or incomplete results.

    Mean/Median/Stdev describe per-repetition mean score per turn against other
    player slots, with population standard deviation (ddof=0). Counts are exact
    sums of recorded non-self moves; C-rate is #C / (#C + #D). Equal means share
    a competition rank. Tied rows sort by label, then slot.
    """
    players = list(players)
    if len(players) < 2:
        raise ValueError("A tournament needs at least two player slots.")
    if isinstance(turns, bool) or not isinstance(turns, int) or turns < 1:
        raise ValueError("turns must be a positive integer.")
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer.")
    if not np.isfinite(noise) or not 0 <= noise <= 1:
        raise ValueError("noise must be finite and between 0 and 1.")
    game = game if game is not None else axl.Game(r=3, s=0, t=5, p=1)
    filename = None
    if csv_dir is not None:
        directory = Path(csv_dir).expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        filename = str(directory / f"interactions-{uuid4().hex}.csv")
        log.info("Retaining raw match CSV: %s", filename)
    tournament = ProgressTournament(players, turns=turns, repetitions=repetitions,
                                    seed=seed, noise=noise, game=game,
                                    progress_callback=progress_callback, checkpoint=checkpoint)
    results = tournament.play(progress_bar=not quiet, filename=filename)
    rows = []
    for index, player in enumerate(players):
        scores = np.asarray(results.normalised_scores[index], dtype=float)
        if len(scores) != repetitions or not np.isfinite(scores).all():
            raise ValueError(f"Missing or non-finite scores for player slot {index}.")
        cooperations = int(sum(count for j, count in enumerate(results.cooperation[index]) if j != index))
        total = int(sum(length for rep in results.match_lengths for j, length in enumerate(rep[index]) if j != index))
        if total != turns * repetitions * (len(players) - 1) or not 0 <= cooperations <= total:
            raise ValueError(f"Incomplete move counts for player slot {index}.")
        rows.append({"Player index": index, "Player": str(player),
                     "Mean": float(np.mean(scores)), "Median": float(np.median(scores)),
                     "Stdev": float(np.std(scores, ddof=0)), "#C": cooperations,
                     "#D": total - cooperations, "C-rate": cooperations / total})
    frame = pd.DataFrame(rows)
    frame.insert(0, "Rank", frame["Mean"].rank(method="min", ascending=False).astype(int))
    frame = frame.sort_values(["Mean", "Player", "Player index"], ascending=[False, True, True], kind="stable").reset_index(drop=True)
    if not quiet:
        log.info("Leaderboard:\n%s", frame.to_string(index=False))
    return (frame, results) if return_results else frame
