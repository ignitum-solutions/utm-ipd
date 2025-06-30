"""
utm_tft.py
~~~~~~~~~~

A *trust-aware* variant of Axelrod's classic **Tit-for-Tat (TFT)** strategy.

Motivation
----------
Laboratory experiments and large-scale agent-based simulations show that
*reactive* strategies such as TFT are highly effective in iterated Prisoner’s
Dilemma (IPD) environments, yet they can still be exploited by noisy or
strategically opportunistic opponents.  The **Universal Trust Meter (UTM)**
adds an explicit, continuous trust signal that:

1. **Penalises betrayal quickly** –– trust plunges after negative rewards.
2. **Recovers slowly** –– cooperation must persist for trust to rebuild.
3. **Decays toward neutral** –– ancient history matters less each round.

When trust drops below a configurable *threshold*, the player overrides TFT
and defects until trust has healed.  This mirror-real-world behaviour:
humans forgive, but only once confidence is re-established.

*Author :* **Ryan Carlisle** — Ignitum Solutions, 2025  
*License:* MIT (Attribution-required)
"""

from __future__ import annotations

import logging

import axelrod as axl
from axelrod.action import Action
from utm.trust_meter import TrustMeter, payoff_to_signed_reward

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

#: Use the package-level logger so that the host application can control
#: verbosity centrally (e.g. via `logging.basicConfig` in main.py).
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategy definition
# ---------------------------------------------------------------------------


class UTMTFT(axl.Player):
    """Tit-for-Tat enhanced with the Universal Trust Meter.

    Parameters
    ----------
    theta :
        Initial trust value :math:`\\theta \\in [0,1]`.
    alpha_pos :
        Learning-rate for *positive* rewards (cooperation gains trust).
    alpha_neg :
        Learning-rate for *negative* rewards (defection erodes trust).
    delta :
        Per-round exponential decay toward neutrality (memory length).
    threshold :
        If current trust < ``threshold`` then the agent *defects*
        regardless of the inner TFT’s recommendation.

    Behavioural summary
    -------------------
    ::

        ┌──────────────────────┐
        │ Receive last outcome │
        └─────────┬────────────┘
                  │
                  ▼
          payoff_to_signed_reward
                  │
                  ▼
            TrustMeter.observe()   (update internal trust)
                  │
                  ├──── trust < τ ? ──► DEFECT
                  │
                  └──────── otherwise ─► inner TitForTat decision

    The TrustMeter itself is **stateless across matches** once :py:meth:`reset`
    is called, matching the expectations of Axelrod-Py tournament runners.
    """

    # Display name used by Axelrod-Py
    name: str = "UTM-TitForTat"

    #: Strategy metadata consumed by the Axelrod tournament framework.
    classifier: dict[str, object] = {
        "memory_depth": float("inf"),       # remembers full history
        "stochastic": False,               # deterministic
        "makes_use_of": set(),
        "long_run_time": False,
        "inspects_source": False,
        "manipulates_source": False,
        "manipulates_state": False,
    }

    # ------------------------------------------------------------------ #
    # Construction                                                        #
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        theta: float = 0.45,
        alpha_pos: float = 0.05,
        alpha_neg: float = 0.5,
        delta: float = 0.6,
        threshold: float = 0.45,
    ) -> None:
        super().__init__()

        # Persistent trust accumulator
        self.trust: TrustMeter = TrustMeter(theta, alpha_pos, alpha_neg, delta)

        # Cut-off below which we suspend cooperation
        self.threshold: float = threshold

        # The underlying TFT “engine” (delegation instead of inheritance keeps
        # TrustMeter orthogonal to TFT internals).
        self.inner: axl.Player = axl.TitForTat()

        logger.debug(
            (
                "Initialized UTMTFT: θ=%.3f, α⁺=%.3f, α⁻=%.3f, δ=%.3f, "
                "threshold=%.3f"
            ),
            theta,
            alpha_pos,
            alpha_neg,
            delta,
            threshold,
        )

    # ------------------------------------------------------------------ #
    # Core strategy loop                                                  #
    # ------------------------------------------------------------------ #
    def strategy(self, opponent: axl.Player) -> str:
        """Decide the next move (“C” or “D”) given *opponent*’s history."""

        # ------------------- Observe previous round ------------------- #
        if self.history:  # skip on very first move
            last_my: str = self.history[-1]
            last_opp: str = opponent.history[-1]
            reward: float = payoff_to_signed_reward(last_my, last_opp)
            round_n: int = len(self.history) + 1

            if round_n <= 10:  # avoid log spam on long tournaments
                logger.debug(
                    "Rnd %d • pre-observe: trust=%.3f / τ=%.3f, last=(%s,%s)",
                    round_n,
                    self.trust.value,
                    self.threshold,
                    last_my,
                    last_opp,
                )

            # Update trust based on signed reward
            self.trust.observe(reward)

            if round_n <= 10:
                logger.debug(
                    "Rnd %d • post-observe: trust=%.3f (Δ=%.3f, betrayals=%d)",
                    round_n,
                    self.trust.value,
                    reward,
                    getattr(self.trust, "_betrayals", 0),
                )

        # ------------------------- Decide ----------------------------- #
        # 1. Ask vanilla TFT what it *would* do.
        proposed_move: str = self.inner.strategy(opponent)

        # 2. Override if trust is too low.
        current_trust: float = self.trust.value
        next_round: int = len(self.history) + 1

        if current_trust < self.threshold:
            decision: str = Action.D  # “D” is also a valid Action subclass
            logger.debug(
                "Rnd %d • trust %.3f < τ %.3f → DEFECT",
                next_round,
                current_trust,
                self.threshold,
            )
        else:
            decision = proposed_move
            logger.debug(
                "Rnd %d • trust %.3f ≥ τ %.3f → %s",
                next_round,
                current_trust,
                self.threshold,
                proposed_move,
            )

        return decision

    # ------------------------------------------------------------------ #
    # Framework housekeeping                                             #
    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        """Restore *exact* initial state between matches (Axelrod protocol)."""
        super().reset()
        self.trust.reset()
        self.inner.reset()
        logger.debug("UTMTFT reset: TrustMeter and inner TitForTat were reset.")


# ---------------------------------------------------------------------------
# Historical alias – retained for backward compatibility with older scripts
# ---------------------------------------------------------------------------

UTMTitForTat = UTMTFT  # noqa: N816  (CamelCase name kept intentionally)
