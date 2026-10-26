"""Keep a delegated rule's memory aligned with actions actually played."""
from __future__ import annotations

import math


def validate_threshold(value: float, name: str = "threshold") -> None:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be finite and between 0 and 1.")


def proposal(inner, player, opponent):
    # Include gate-forced and noise-flipped actions, never hypothetical moves.
    # Reconstruct all available history after a hybrid switches its inner rule.
    for index in range(len(inner.history), len(player.history)):
        inner.update_history(player.history[index], opponent.history[index])
    inner.set_match_attributes(**player.match_attributes)
    return inner.strategy(opponent)
