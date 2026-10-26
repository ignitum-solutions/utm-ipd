"""TFT-to-WSLS hybrid with a trust gate.

Switch permanently to WSLS when trust is strictly greater than promote_at
(default 0.55). The new inner rule uses the already-played history. Trust below
the separate cooperation threshold forces D in either phase. Reset restores TFT.
"""

from __future__ import annotations
import logging, axelrod as axl
from axelrod.action import Action
from utm.trust_meter import TrustMeter, payoff_to_signed_reward
from strategies.delegation import proposal, validate_threshold

logger = logging.getLogger(__name__)

class UTMTFT_WSLS(axl.Player):
    """TFT until trust > promote_at (default 0.55), then WSLS until reset."""

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
        validate_threshold(threshold)
        validate_threshold(promote_at, "promote_at")
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

        # Switch at the explicitly configured promotion threshold.
        if (self.trust.value > self.promote_at and
                not isinstance(self.inner, axl.WinStayLoseShift)):
            self.inner = axl.WinStayLoseShift()
            logger.debug("Trust %.3f > promote_at %.2f → switch to WSLS",
                         self.trust.value, self.promote_at)

        move = proposal(self.inner, self, opponent)
        return Action.D if self.trust.value < self.threshold else move

    def reset(self) -> None:
        super().reset(); self.trust.reset()
        self.inner = axl.TitForTat()     # reset to cautious
        logger.debug("UTM-TFT→WSLS reset")
