from __future__ import annotations
from typing import List, Any
import logging, streamlit as st

logger = logging.getLogger("utm.ipd")

def _init_plotter(players: List[Any], results: Any):  # type: ignore[valid-type]
    try:
        from axelrod.plot import Plot  # type: ignore
    except ImportError:
        return None
    try:
        return Plot(results)           # new API
    except TypeError:                  # legacy API
        return Plot(players, results)

def render_plots(players, results):
    plotter = _init_plotter(players, results)
    if plotter is None:
        st.warning("⚠️  `axelrod.plot` unavailable – graphs skipped")
        return

    st.subheader("📊 Performance graphs")
    for method in ("boxplot", "payoff_matrix", "ranking_plot", "winplot"):
        try:
            fig = getattr(plotter, method)()
            if fig:
                st.pyplot(fig, use_container_width=True)
        except Exception as exc:
            logger.debug("Skip plot %s: %s", method, exc)
