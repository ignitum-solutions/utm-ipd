"""
trust_game.py  –  Streamlit playground for the Universal Trust Model
====================================================================

A lightweight “investment / trust game” where:

1. **Investor (our agent)** decides each round whether to send a fixed amount
   based on its current trust level.
2. **Trustee (environment)** may betray with probability *p*; if not, it
   returns a user-chosen percentage of the tripled investment.
3. The investor’s behaviour is governed by **UTM-TitForTat**:
       • Trust increases after profitable rounds, decreases after losses.  
       • If trust < τ, the investor refuses to send (defects).

Users manipulate sliders to see how
`alpha_pos`, `alpha_neg`, `delta`, `τ`, and the environment parameters
shape the trust trajectory and cumulative pay-off.

Author  : **Ryan Carlisle** — Ignitum Solutions, 2025  
License : MIT (Attribution-required)

Notes
-----
* Purely a **demo**; it is **not** imported by tournament code.
* Not related to the IPD in any way.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard-library imports
# ---------------------------------------------------------------------------
import logging
import random

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
import numpy as np
import streamlit as st
from matplotlib import pyplot as plt  # noqa: F401  (used by st.line_chart backend)

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from strategies.utm_tft import UTMTFT

# ---------------------------------------------------------------------------
# Streamlit page metadata
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Trust Game",
    page_icon="static/IgnitumSolutions_RGB_Icon.png",  # ensure asset exists
    layout="wide",
)

log = logging.getLogger("utm.ipd")

# ═══════════════════════════ game engine ═══════════════════════════════════
def run_trust_game(
    rounds: int,
    send: float,
    ret_good: float,
    betray_prob: float,
    ret_bad: float,
    alpha_pos: float,
    alpha_neg: float,
    delta: float,
    tau: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Simulate *rounds* of the trust game.

    Returns
    -------
    trust_vals : ndarray
        Trust score after each round.
    payoffs : ndarray
        Per-round monetary payoff to the investor.
    """
    agent = UTMTFT(
        theta=0.5,
        alpha_pos=alpha_pos,
        alpha_neg=alpha_neg,
        delta=delta,
        threshold=tau,
    )

    trust_vals: list[float] = []
    payoffs: list[float] = []

    for _ in range(rounds):
        betrayed = random.random() < betray_prob

        sent = send if agent.trust.value >= tau else 0.0
        returned = sent * 3 * (ret_bad if betrayed else ret_good)
        payoff = -sent + returned

        # Update trust: +1 for profit, −1 for loss
        agent.trust.observe(+1 if payoff >= 0 else -1)

        trust_vals.append(agent.trust.value)
        payoffs.append(payoff)

    return np.array(trust_vals), np.array(payoffs)


# ═══════════════════════════ UI  ═══════════════════════════════════════════
st.title("Investment / Trust Game")

# ── parameter controls ─────────────────────────────────────────────────────
colA, colB = st.columns(2)
with colA:
    rounds = st.slider("Rounds", 10, 500, 50)
    send = st.slider("Send amount", 0.0, 10.0, 5.0, 0.5)
with colB:
    ret_good = st.slider("Return % (good round)", 0.0, 1.0, 0.50, 0.05)
    betray_prob = st.slider("Betrayal probability", 0.0, 1.0, 0.00, 0.05)
    ret_bad = st.slider("Return % (betrayal round)", 0.0, 1.0, 0.00, 0.05)

if st.button("▶ Run Trust Game"):
    tvals, pays = run_trust_game(
        rounds,
        send,
        ret_good,
        betray_prob,
        ret_bad,
        alpha_pos=0.05,
        alpha_neg=0.50,
        delta=0.55,
        tau=0.45,
    )

    # ── charts ────────────────────────────────────────────────────────────
    st.subheader("Trust trajectory")
    st.line_chart(tvals, height=220)

    st.subheader("Cumulative payoff")
    st.line_chart(pays.cumsum(), height=220)

    # ── summary metrics ───────────────────────────────────────────────────
    final_trust = float(tvals[-1])
    cum_payoff = float(pays.sum())
    coop_rate = float((pays >= 0).mean())

    summary_md = (
        "### Summary\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Final trust | {final_trust:.3f} |\n"
        f"| Cumulative payoff | {cum_payoff:.2f} |\n"
        f"| Coop fraction | {coop_rate:.2f} |\n"
        f"| Betrayal prob | {betray_prob:.2f} |\n"
        f"| Good return % | {ret_good:.2f} |\n"
        f"| Bad return % | {ret_bad:.2f} |"
    )
    st.markdown(summary_md, unsafe_allow_html=True)

    # plain-text copy block
    st.text_area(
        "Copy-ready text",
        summary_md.replace("**", "").replace("### ", ""),
        height=110,
    )

    # log identical line for debugging
    log.info(
        (
            "TrustGame | rounds=%d | send=%.2f | good=%.2f | bad=%.2f "
            "| p_betray=%.2f | final_trust=%.3f | cum_payoff=%.2f "
            "| coop_frac=%.2f"
        ),
        rounds,
        send,
        ret_good,
        ret_bad,
        betray_prob,
        final_trust,
        cum_payoff,
        coop_rate,
    )
