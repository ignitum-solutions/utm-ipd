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
    * `IPD_REWARD_MATRIX_DEFAULTS` and the effective reward mapping
    * `payoff_to_signed_reward`
    * `observe_moves`
If you port UTM to another domain, replace those three bits with a
domain-specific outcome-to-reward mapper.  Everything else is generic UTM.

Notes
-----
    * Trust is bounded to [0, 1] by the defined update rule.
    * Learning rates and the signed reward mapping are modeling choices.
      This repository does not provide empirical validation for these defaults.
    * There is no time decay. Delta multiplies updates through the cumulative
      count of rewards below current trust.

Author: Ryan Carlisle, 2025 — released under MIT (attribution appreciated).
"""

from __future__ import annotations

import logging
import math
from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Final, Iterator

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Explicit default model parameters; not a demonstrated optimum.
ALPHA_POS: Final[float] = 0.05  # learning-rate for positive surprises (α⁺)
ALPHA_NEG: Final[float] = 0.50  # learning-rate for negative surprises (α⁻)
DELTA: Final[float]     = 0.30  # betrayal ramp-up multiplier (δ)

# ────────────────────────────────────────────────────────────────────────────
# Model-specific signed rewards. These do not alter the PD scoring game.
# Choices are fixed and exported with each run; they are not evidence of fit.
# In particular DC=+0.5 and DD=-0.2 are assumptions, not universal rewards.
IPD_REWARD_MATRIX_DEFAULTS: Final[dict[tuple[str, str], float]] = {
    ("C", "C"):  1.0,   # mutual cooperation
    ("D", "C"):  0.5,   # I defected, they cooperated
    ("D", "D"): -0.2,   # mutual defection (mild distrust)
    ("C", "D"): -1.0,   # sucker’s payoff / betrayal
}

_REWARD_VALUES: ContextVar[tuple[float, float, float, float]] = ContextVar(
    "ipd_reward_values", default=(1.0, 0.5, -0.2, -1.0)
)


def get_ipd_reward_values() -> tuple[float, float, float, float]:
    """Effective signed rewards (CC, DC, DD, CD) in the current execution context."""
    return _REWARD_VALUES.get()


def _validated_rewards(values) -> tuple[float, float, float, float]:
    values = tuple(float(v) for v in values)
    if any(not math.isfinite(v) or v == 0 for v in values):
        raise ValueError("Signed trust rewards must be finite and nonzero.")
    return values


def set_ipd_reward_values(r_cc: float, r_dc: float, r_dd: float, r_cd: float) -> None:
    """Set an explicit reward mapping in this context, without changing PD payoffs."""
    _REWARD_VALUES.set(_validated_rewards((r_cc, r_dc, r_dd, r_cd)))


@contextmanager
def temporary_ipd_reward_values(r_cc: float, r_dc: float, r_dd: float, r_cd: float) -> Iterator[None]:
    """Isolate one experiment's mapping and restore it even on failure."""
    token = _REWARD_VALUES.set(_validated_rewards((r_cc, r_dc, r_dd, r_cd)))
    try:
        yield
    finally:
        _REWARD_VALUES.reset(token)


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
        Finite nonzero signed reward from the effective mapping. Custom mappings
        may extend beyond the default range [-1, 1].

    Raises
    ------
    ValueError
        If either move is not 'C' or 'D'.
    """
    try:
        index = {("C", "C"): 0, ("D", "C"): 1, ("D", "D"): 2, ("C", "D"): 3}[(str(my_move), str(opp_move))]
        reward = get_ipd_reward_values()[index]
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

    _betrayals: int = field(default=0, init=False)
    _trust: float | None = field(default=None, init=False)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        for name, value in (("theta", self.theta), ("alpha_pos", self.alpha_pos), ("alpha_neg", self.alpha_neg)):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be finite and between 0 and 1.")
        if not math.isfinite(self.delta) or self.delta < 0:
            raise ValueError("delta must be finite and nonnegative.")
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
            Finite nonzero signed outcome, domain-specific. Defaults are in
            [-1, 1]; custom mappings may use a different scale.
        severity : float, default 1.0
            Event severity s (UTM spec §2); use <1 for minor events,
            >1 only if your domain defines scaled severities.

        Raises
        ------
        ValueError
            If reward == 0 (UTM requires non-zero events).
        """
        if not math.isfinite(reward) or reward == 0:
            raise ValueError("reward must be finite and non-zero")
        if not math.isfinite(severity) or severity < 0:
            raise ValueError("severity must be finite and nonnegative")

        # Pick α based on “surprise” direction
        alpha = self.alpha_pos if reward > self._trust else self.alpha_neg

        # Detect betrayal and bump n
        betrayals = self._betrayals + int(reward < self._trust)

        factor  = severity * (1 + betrayals * self.delta)  # s · (1 + nδ)
        delta_t = alpha * factor * (reward - self._trust)
        if not math.isfinite(delta_t):
            raise ValueError("The trust update overflowed; use smaller parameters.")
        self._betrayals = betrayals
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
