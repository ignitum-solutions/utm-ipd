"""
Trust-only IPD strategy: decisions are driven by the Universal Trust Meter.

Unlike UTMTFT or UTMWSLS, this agent does NOT delegate to a classic
Axelrod strategy. It:

  1. Observes the last round (my_move, opp_move) via TrustMeter.
  2. Updates internal trust T ∈ [0,1].
  3. Cooperates if trust ≥ threshold τ, otherwise defects.

This is an IPD-only strategy variant with no Tit-for-Tat or WSLS skeleton
underneath.
"""

from __future__ import annotations

import logging
import axelrod as axl
from axelrod.action import Action

from utm.trust_meter import TrustMeter, payoff_to_signed_reward

logger = logging.getLogger(__name__)


class TrustOnlyIPDStrategy(axl.Player):
    """
    Trust-only IPD strategy.

    Parameters
    ----------
    theta : float
        Initial trust θ ∈ [0,1].
    alpha_pos : float
        Learning-rate α⁺ for positive surprises.
    alpha_neg : float
        Learning-rate α⁻ for negative surprises.
    delta : float
        Betrayal ramp-up factor δ.
    threshold : float
        Trust cutoff τ. If current trust < τ, agent defects;
        otherwise it cooperates.

    Behaviour
    ---------
    First move:
        • Cooperate if θ ≥ τ, else defect.

    Subsequent moves:
        • Observe last outcome via TrustMeter.
        • If trust ≥ τ → COOPERATE
          Else          → DEFECT
    """

    name: str = "Trust-only IPD"

    classifier: dict[str, object] = {
        "memory_depth": float("inf"),  # remembers full history via TrustMeter
        "stochastic": False,
        "makes_use_of": set(),
        "long_run_time": False,
        "inspects_source": False,
        "manipulates_source": False,
        "manipulates_state": False,
    }

    def __init__(
        self,
        theta: float = 0.5,
        alpha_pos: float = 0.05,
        alpha_neg: float = 0.5,
        delta: float = 0.3,
        threshold: float = 0.5,
    ) -> None:
        super().__init__()

        self.trust: TrustMeter = TrustMeter(theta, alpha_pos, alpha_neg, delta)
        self.threshold: float = threshold

        logger.debug(
            "Initialized TrustOnlyIPDStrategy: θ=%.3f, α⁺=%.3f, α⁻=%.3f, δ=%.3f, τ=%.3f",
            theta,
            alpha_pos,
            alpha_neg,
            delta,
            threshold,
        )

    def strategy(self, opponent: axl.Player) -> str:
        """Decide next move (“C” or “D”) based solely on UTM trust level."""

        # Observe previous round (if any)
        if self.history:
            last_my: str = self.history[-1]
            last_opp: str = opponent.history[-1]
            reward: float = payoff_to_signed_reward(last_my, last_opp)
            round_n: int = len(self.history) + 1

            if round_n <= 10:
                logger.debug(
                    "Rnd %d • pre-observe: trust=%.3f / τ=%.3f, last=(%s,%s)",
                    round_n,
                    self.trust.value,
                    self.threshold,
                    last_my,
                    last_opp,
                )

            self.trust.observe(reward)

            if round_n <= 10:
                logger.debug(
                    "Rnd %d • post-observe: trust=%.3f (R=%.3f, betrayals=%d)",
                    round_n,
                    self.trust.value,
                    reward,
                    getattr(self.trust, "_betrayals", 0),
                )

        current_trust: float = self.trust.value
        next_round: int = len(self.history) + 1

        # Trust-only IPD decision rule
        if current_trust < self.threshold:
            decision: str = Action.D
            logger.debug(
                "Rnd %d • trust %.3f < τ %.3f → DEFECT",
                next_round,
                current_trust,
                self.threshold,
            )
        else:
            decision = Action.C
            logger.debug(
                "Rnd %d • trust %.3f ≥ τ %.3f → COOPERATE",
                next_round,
                current_trust,
                self.threshold,
            )

        return decision

    def reset(self) -> None:
        """Reset trust state between matches."""
        super().reset()
        self.trust.reset()
        logger.debug("TrustOnlyIPDStrategy reset: TrustMeter reset to θ.")
