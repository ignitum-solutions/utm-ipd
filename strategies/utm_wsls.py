"""
utm_wsls.py
~~~~~~~~~~~

A **Win-Stay-Lose-Shift (WSLS)** strategy wrapped by the **Universal Trust
Model (UTM)** for Axelrod-Py tournaments.

*Author :* **Ryan Carlisle** — Ignitum Solutions, 2025  
*License:* MIT (Attribution-required)

Concept
-------
The inner WSLS repeats its previous move after a win (mutual C or T) and
switches after a loss.  The surrounding Trust *Model* tracks cumulative
behaviour; when trust < τ the agent defects regardless of WSLS advice, guarding
against exploitative opponents.

(Only comments / doc-strings were altered; functional code is untouched.)
"""

from __future__ import annotations

import logging
import axelrod as axl
from axelrod.action import Action
from utm.trust_meter import TrustMeter, payoff_to_signed_reward

logger = logging.getLogger(__name__)


class UTMWSLS(axl.Player):
    """Win-Stay-Lose-Shift governed by a Universal Trust Meter (UTM).

    The inner WSLS engine cooperates on mutual C and repeats D only
    after a loss.  The outer TrustMeter decides whether we allow the
    inner engine to act or force defection until trust recovers.
    """

    name = "UTM-WSLS"

    classifier = {
        "memory_depth": float("inf"),
        "stochastic": False,
        "makes_use_of": set(),
        "long_run_time": False,
        "inspects_source": False,
        "manipulates_source": False,
        "manipulates_state": False,
    }

    # ---------------------------------------------------------------
    def __init__(
        self,
        theta: float = 0.45,
        alpha_pos: float = 0.05,
        alpha_neg: float = 0.50,
        delta: float = 0.55,
        threshold: float = 0.45,
    ):
        super().__init__()
        self.trust = TrustMeter(theta, alpha_pos, alpha_neg, delta)
        self.threshold = threshold
        self.inner: axl.Player = axl.WinStayLoseShift()

        logger.debug(
            "Initialized UTMWSLS: θ=%.3f, α⁺=%.3f, α⁻=%.3f, δ=%.3f, τ=%.3f",
            theta, alpha_pos, alpha_neg, delta, threshold,
        )

    # ---------------------------------------------------------------
    def strategy(self, opponent: axl.Player) -> str:
        """Choose C/D this turn, updating trust after the previous turn."""
        if self.history:
            last_my, last_opp = self.history[-1], opponent.history[-1]
            reward = payoff_to_signed_reward(last_my, last_opp)
            self.trust.observe(reward)

        # Inner engine’s suggestion
        proposed = self.inner.strategy(opponent)
        # Gate through trust threshold
        return Action.D if self.trust.value < self.threshold else proposed

    # ---------------------------------------------------------------
    def reset(self) -> None:
        super().reset()
        self.trust.reset()
        self.inner.reset()
        logger.debug("UTMWSLS reset")

# Back-compat alias if you want to import by old name
UTM_WinStayLoseShift = UTMWSLS
