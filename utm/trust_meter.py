# utm/trust_meter.py
"""
Trust-meter for a *single* counterpart under the Universal Trust Model (UTM).

---------------------------------------------------------------------------
How this file fits the UTM core equation
---------------------------------------------------------------------------
T_old        → `self._trust`
T_new        → updated `self._trust`
α⁺ / α⁻      → `alpha_pos`, `alpha_neg`
δ            → `delta`
s (severity) → `severity` arg to `.observe()`
n            → `self._betrayals`
θ            → `theta` (initial trust / baseline)

The only Iterated-Prisoner-Dilemma (IPD) glue is:
    * `_REWARD_TABLE`
    * `payoff_to_signed_reward`
    * `observe_moves`
If you port UTM to another domain, replace those three bits with a
domain-specific outcome-to-reward mapper.  Everything else is generic UTM.

Notes
-----
    * Trust is bounded to the closed interval [0, 1]; negative values
      (active mistrust) are not represented in this implementation.
      Empirically we found the 0–1 range sufficient for IPD modelling,
      but the update rule can be extended to [−1, 1] if required.
    * Learning rates differ (α⁺ ≠ α⁻) to capture the well-known
      asymmetry where negative events update trust faster than positive
      reinforcement.

Author: Ryan Carlisle, 2025 — released under MIT (Attribution-required).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Default hyper-parameters (tuned for our baseline IPD experiments)
# ────────────────────────────────────────────────────────────────────────────
ALPHA_POS: Final[float] = 0.05  # learning-rate for positive surprises (α⁺)
ALPHA_NEG: Final[float] = 0.50  # learning-rate for negative surprises (α⁻)
DELTA: Final[float]     = 0.30  # betrayal ramp-up multiplier (δ)

# ────────────────────────────────────────────────────────────────────────────
# IPD-specific reward table  (calibrated for UTM experiments)
#
# The numeric values are *not* PD payoffs; they are a signed “event
# reward” R ∈ (−1 … 1] fed to the UTM update rule.  We chose this scale
# empirically so that:
#   • mutual cooperation feels maximally positive  (+1.0)
#   • betrayal feels maximally negative           (−1.0)
#   • mutual defection registers as a mild penalty (−0.2)
#   • successfully exploiting an opponent is still positive  (+0.5)
#
# This calibration produced stable convergence in our Iterated Prisoner’s
# Dilemma (IPD) tournaments but can be replaced for other domains.
# ────────────────────────────────────────────────────────────────────────────
_REWARD_TABLE: Final[dict[tuple[str, str], float]] = {
    ("C", "C"):  1.0,   # mutual cooperation
    ("D", "C"):  0.5,   # I defected, they cooperated
    ("D", "D"): -0.2,   # mutual defection (mild distrust)
    ("C", "D"): -1.0,   # sucker’s payoff / betrayal
}


# ────────────────────────────────────────────────────────────────────────────
# Helper: map a raw payoff to the signed reward R used by UTM
# NOTE: IPD-specific function — swap this out for other environments/trials/games.
# ────────────────────────────────────────────────────────────────────────────
def payoff_to_signed_reward(my_move: str, opp_move: str) -> float:
    """Return the signed reward *R* for a single IPD round.

    Parameters
    ----------
    my_move, opp_move : {'C', 'D'}
        Moves made by me and the opponent
        ('C' = cooperate, 'D' = defect).

    Returns
    -------
    float
        Reward ∈ (−1 … 1], never zero (UTM requires non-zero events).

    Raises
    ------
    ValueError
        If either move is not 'C' or 'D'.
    """
    try:
        reward = _REWARD_TABLE[(str(my_move), str(opp_move))]
        logger.debug(
            "payoff_to_signed_reward: my=%s, opp=%s → R=%.3f",
            my_move, opp_move, reward
        )
        return reward
    except KeyError as exc:
        logger.error("Invalid move pair (%s, %s)", my_move, opp_move)
        raise ValueError("move must be 'C' or 'D'") from exc


# ────────────────────────────────────────────────────────────────────────────
# Core class
# ────────────────────────────────────────────────────────────────────────────
@dataclass
class TrustMeter:
    """
    Online estimator of *my* trust in one partner, per the UTM update rule.

    Parameters
    ----------
    theta : float, default 0.5
        Initial trust T_old (baseline θ). 0 = no trust, 1 = full trust.
    alpha_pos : float, default 0.05
        Learning-rate α⁺ for positive surprises (R > T_old).
    alpha_neg : float, default 0.50
        Learning-rate α⁻ for negative surprises (R < T_old).
    delta : float, default 0.30
        Betrayal ramp-up factor δ applied per prior betrayal.

    Notes
    -----
    * All values are clamped to [0, 1] after each update.
    * Negative trust / active mistrust is not represented here; extend to
      [−1, 1] if your use-case needs it.
    * Internal counter `_betrayals` (n) increments only when `reward < trust`.
    """

    theta: float = 0.5
    alpha_pos: float = ALPHA_POS
    alpha_neg: float = ALPHA_NEG
    delta: float = DELTA

    _betrayals: int = 0         # n — number of past betrayals by this partner
    _trust: float | None = None  # will be initialised to θ in __post_init__

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        self._trust = self.theta
        logger.debug(
            "TrustMeter init: θ=%.3f α⁺=%.3f α⁻=%.3f δ=%.3f",
            self.theta, self.alpha_pos, self.alpha_neg, self.delta,
        )

    @property
    def value(self) -> float:
        """Return current trust level T (always clipped to [0, 1])."""
        return self._trust

    # ------------------------------------------------------------------
    # Universal Trust Model update rule
    # ------------------------------------------------------------------
    def observe(self, reward: float, severity: float = 1.0) -> None:
        """Apply one UTM update step given a signed reward *R*.

        Parameters
        ----------
        reward : float
            Signed outcome in (−1 … 1], domain-specific.
        severity : float, default 1.0
            Event severity s (UTM spec §2); use <1 for minor events,
            >1 only if your domain defines scaled severities.

        Raises
        ------
        ValueError
            If reward == 0 (UTM requires non-zero events).
        """
        if reward == 0:
            raise ValueError("reward must be non-zero")

        # Pick α based on “surprise” direction
        alpha = self.alpha_pos if reward > self._trust else self.alpha_neg

        # Detect betrayal and bump n
        if reward < self._trust:
            self._betrayals += 1

        factor  = severity * (1 + self._betrayals * self.delta)  # s · (1 + nδ)
        delta_t = alpha * factor * (reward - self._trust)
        self._trust = max(0.0, min(1.0, self._trust + delta_t))

    # ------------------------------------------------------------------
    # IPD convenience adapter
    # ------------------------------------------------------------------
    def observe_moves(self, my_move: str, opp_move: str, *, severity: float = 1.0) -> None:
        """IPD-specific shortcut — convert moves → reward → observe()."""
        reward = payoff_to_signed_reward(my_move, opp_move)
        self.observe(reward, severity)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Reset trust to θ and clear betrayal counter before a new match."""
        self._trust = self.theta
        self._betrayals = 0
