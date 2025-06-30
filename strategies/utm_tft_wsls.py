"""
utm_tft_wsls.py
~~~~~~~~~~~~~~~

Hybrid strategy for Axelrod-Py tournaments:

    • **Phase 1** – *Tit-for-Tat* while confidence is still forming  
    • **Phase 2** – switch permanently to *Win-Stay-Lose-Shift* once the
      Universal **Trust Model** says trust is “solid enough” (≥ `promote_at`)  
    • At **any** point, if current trust drops below `threshold`, the agent
      defects unconditionally to protect itself.

The design reflects human behaviour: start cautious, graduate to a more
self-reliant rule once the relationship proves stable, but never tolerate
extended betrayal.

This was an experiment to see if the Universal Trust Model could broach hybrid strategies.
(It could, but did not win as often as utm_tft in preliminary runs/tests.)

*Author :* **Ryan Carlisle** — Ignitum Solutions, 2025  
*License:* MIT (Attribution-required)
"""

from __future__ import annotations
import logging, axelrod as axl
from axelrod.action import Action
from utm.trust_meter import TrustMeter, payoff_to_signed_reward

logger = logging.getLogger(__name__)

class UTMTFT_WSLS(axl.Player):
    """TFT while trust is shaky → WSLS once trust is solid (>0.80)."""

    name = "UTM-TFT→WSLS"
    classifier = dict(
        memory_depth=float("inf"), stochastic=False, makes_use_of=set(),
        long_run_time=False, inspects_source=False,
        manipulates_source=False, manipulates_state=False,
    )

    def __init__(
        self,
        theta: float = 0.45, alpha_pos: float = 0.05,
        alpha_neg: float = 0.50, delta: float = 0.55,
        threshold: float = 0.45, promote_at: float = 0.55,
    ):
        super().__init__()
        self.trust = TrustMeter(theta, alpha_pos, alpha_neg, delta)
        self.threshold = threshold
        self.promote_at = promote_at
        self.inner: axl.Player = axl.TitForTat()      # start cautious
        logger.debug("Init UTM-TFT→WSLS (θ=%.2f τ=%.2f promote=%.2f)",
                     theta, threshold, promote_at)

    def strategy(self, opponent: axl.Player) -> str:
        if self.history:
            r = payoff_to_signed_reward(self.history[-1], opponent.history[-1])
            self.trust.observe(r)

        # upgrade inner engine the first time trust soars past promote_at
        if (self.trust.value > self.promote_at and
                not isinstance(self.inner, axl.WinStayLoseShift)):
            self.inner = axl.WinStayLoseShift()
            logger.debug("Trust %.3f > promote_at %.2f → switch to WSLS",
                         self.trust.value, self.promote_at)

        move = self.inner.strategy(opponent)
        return Action.D if self.trust.value < self.threshold else move

    def reset(self) -> None:
        super().reset(); self.trust.reset()
        self.inner = axl.TitForTat()     # reset to cautious
        logger.debug("UTM-TFT→WSLS reset")
