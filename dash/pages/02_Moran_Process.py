"""
moran.py  –  Streamlit visualiser for an Axelrod-Py Moran evolutionary process
==============================================================================

**IMPORTANT NOTE: Still a work in progress/testing.

Purpose
-------
Lets you explore how a single **Universal Trust Model** strategy spreads (or
fails) in a population of Cooperators under the classic Moran birth–death
process:

* Start population = 1 × UTM variant + (*N–1*) × Cooperator
* Each generation:
    1. Randomly choose two players for a 200-round IPD
    2. Reproduce proportional to score, replacing a random individual
* Track the **share** of UTM players over time.

UI Inputs
---------
* **Generations** – fixed horizon (or runs to fixation on older Axelrod versions)
* **Population size** – integer 5 – 50
* Sidebar controls for the UTM hyper-parameters (handled in *dash.shared*).

Outputs
-------
* Line chart of UTM population share  
* Markdown summary and copy-ready textarea  
* INFO-level log lines for reproducibility

Author  : **Ryan Carlisle** — Ignitum Solutions, 2025  
Licence : MIT (Attribution-required)

Note
----
The module is **demo-only**; deleting it will not affect tournament libraries.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard-library
# ---------------------------------------------------------------------------
import logging

# ---------------------------------------------------------------------------
# Third-party
# ---------------------------------------------------------------------------
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib import pyplot as plt
import axelrod as axl

# ---------------------------------------------------------------------------
# Internal project
# ---------------------------------------------------------------------------
from dash.shared import sidebar          # helper to render sidebar controls
from dash.state import init_state        # session-state initialisation
from strategies.utm_tft import UTMTFT
from strategies.utm_wsls import UTMWSLS
from strategies.utm_tft_wsls import UTMTFT_WSLS

# ---------------------------------------------------------------------------
# Streamlit page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Moran Process",
    page_icon="static/IgnitumSolutions_RGB_Icon.png",
    layout="wide",
)

logger = logging.getLogger("utm.ipd")
if not logging.getLogger().hasHandlers():     # fallback if user code sets none
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Strategy registry for dropdown
# ---------------------------------------------------------------------------
UTM_REGISTRY = {
    "TFT":      UTMTFT,
    "WSLS":     UTMWSLS,
    "TFT→WSLS": UTMTFT_WSLS,
}

# ══════════════════════════════ UI BODY ═══════════════════════════════════

cfg = sidebar()           # sidebar() provides hyper-parameter widgets
state = init_state()      # ensure session state keys exist (not used further)

st.title("Moran Evolutionary Process")

generations = st.number_input("Generations", 50, 1_000, 200)
pop_size = st.slider("Population size", 5, 50, 20)

if st.button("Run Moran"):
    # ── 1. Build initial population ─────────────────────────────────────
    utm_player = UTM_REGISTRY[cfg["utm_variant"]](
        cfg["theta"],
        cfg["alpha_pos"],
        cfg["alpha_neg"],
        cfg["delta"],
        cfg["threshold"],
    )
    population = [utm_player] + [axl.Cooperator()] * (pop_size - 1)

    logger.info(
        "Moran config → players=%s | pop=%d | generations=%d | turns=%d",
        [p.name for p in population],
        pop_size,
        generations,
        200,
    )

    # ── 2. Run process ──────────────────────────────────────────────────
    mp = axl.MoranProcess(population, turns=200)

    try:                       # Axelrod ≥ 5 returns a DataFrame
        counts = mp.play(n=generations)
    except TypeError:          # Older versions run to fixation and return list
        mp.play()
        counts = mp.populations

    # ── 3. Extract UTM share per generation ─────────────────────────────
    if isinstance(counts, pd.DataFrame):
        df = counts.cumsum()                        # cumulative birth events
        utm_col = next(c for c in df.columns if str(c).startswith("UTM-"))
        share = df[utm_col] / pop_size
        gens = df.index
    else:                                           # list-of-lists fallback
        utm_counts = [
            sum(getattr(p, "name", p).startswith("UTM-") for p in pop)
            for pop in counts
        ]
        share = np.array(utm_counts) / pop_size
        gens = range(len(share))

    # ── 4. Summary metrics ──────────────────────────────────────────────
    final_share = float(share[-1] if isinstance(share, np.ndarray) else share.iloc[-1])
    mean_share = float(share.mean())
    fixation_gen = next((i for i, s in enumerate(share) if s in (0.0, 1.0)), None)

    logger.info(
        "Moran summary → final share %.3f | mean share %.3f | fixation=%s",
        final_share,
        mean_share,
        fixation_gen if fixation_gen is not None else "none",
    )

    # ── 5. Plot ─────────────────────────────────────────────────────────
    fig, ax = plt.subplots()
    ax.plot(gens, share)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Population share")
    ax.set_title("UTM population share over time")
    st.pyplot(fig)

    # ── 6. Markdown + copy-paste summary ───────────────────────────────
    summary_md = (
        "### Moran summary\n\n"
        f"- Final share: **{final_share:.3f}**\n"
        f"- Mean share: **{mean_share:.3f}**\n"
        f"- Fixation generation: "
        f"{fixation_gen if fixation_gen is not None else 'none'}"
    )
    st.markdown(summary_md)

    st.text_area("Copy-ready text", summary_md.replace("**", ""), height=100)
