"""
Streamlit dashboard ─ UTM  ↔  Iterated Prisoner’s Dilemma

This is the *entry point* most readers will launch first.  It:

1.   Collects hyper-parameters for the Universal Trust Model (UTM) via the
     sidebar (see `dash/shared.py`).
2.   Spawns an asynchronous tournament worker (`dash.background.run_async`)
     so the UI stays responsive.
3.   Shows live progress and then renders a leaderboard + plots.

What is **IPD-specific** here?
    • The page title / icon and labels
    • The call to `run_async`, which ultimately runs
      `tournaments.run_round_robin` (Axelrod-based).

All UTM math lives in `utm/`  — this file only orchestrates the UI.

No functional logic below is altered by adding this doc-string.
"""

from __future__ import annotations
import time, logging
from queue import Queue, Empty

import streamlit as st

st.set_page_config(
    page_title="Iterated Prisoner's Dilemma",
    page_icon="static/IgnitumSolutions_RGB_Icon.png",
    layout="wide",
)

from dash.state import init_state
from dash.background import EXECUTOR, run_async
from dash.utils import summarise_run, render_results
from dash.shared import sidebar

log = logging.getLogger("utm.ipd")
state = init_state()
cfg = sidebar()

st.title("Universal Trust Model → Iterated Prisoner’s Dilemma")
run_area = st.empty()

if cfg["run_clicked"]:
    if state.running and state.future and not state.future.done():
        state.future.cancel()
    state.summary_md = summarise_run(**cfg)
    run_area.info(state.summary_md)
    log.info(state.summary_md.replace("**", ""))
    state.progress_q = Queue()
    state.running = True
    state.future = EXECUTOR.submit(
        run_async,
        utm_presets=cfg["utm_presets"],
        utm_variant=cfg["utm_variant"],
        theta=cfg["theta"],
        alpha_pos=cfg["alpha_pos"],
        alpha_neg=cfg["alpha_neg"],
        delta=cfg["delta"],
        threshold=cfg["threshold"],
        rounds=cfg["rounds"],
        reps=cfg["reps"],
        seed=cfg["seed"],
        noise_pct=cfg["noise_pct"],
        selected_names=cfg["selected_names"],
        extra_cls=cfg["extra_cls"].strip(),
        noise_wrap=cfg["noise_wrap"],
        progress_q=state.progress_q,
    )

if state.running and state.future:
    if "progress_q" not in state:
        state.progress_q = Queue()
    progress_bar = st.progress(0, text="Running tournament … 0%")
    last_pct = 0
    done_flag = False
    while not done_flag and not state.future.done():
        try:
            msg = state.progress_q.get(timeout=0.1)
            if msg == ("done", "done"):
                progress_bar.progress(100, text="Running tournament … 100%")
                done_flag = True
            else:
                completed, total = msg
                pct = int(completed / total * 100)
                if pct > last_pct:
                    last_pct = pct
                    progress_bar.progress(pct, text=f"Running tournament … {pct}%")
        except Empty:
            pass
    if state.future.done():
        progress_bar.progress(100, text="Running tournament … 100%")
    progress_bar.empty()
    if state.future.cancelled():
        run_area.warning("Tournament cancelled")
    else:
        try:
            lb_df, players_ret, results_ret = state.future.result()
        except Exception as exc:
            run_area.error(f"Tournament failed: {exc}")
            log.error("Tournament raised: %s", exc)
        else:
            run_area.empty()
            with run_area.container():
                render_results(
                    state,
                    lb_df,
                    players_ret,
                    results_ret,
                    copy_key=f"copy_{time.time_ns()}",
                )
    state.running = False
    state.future = None

if state.get("have_results") and not state.running:
    with run_area.container():
        render_results(
            state,
            state.last_leaderboard,
            state.last_players,
            state.last_results,
            copy_key="copy_persist",
        )
