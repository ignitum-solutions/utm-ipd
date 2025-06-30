# ./dash/pages/01_IPD_Mini_Sweep.py
"""
Mini-sweep UI for exploring UTM hyper-parameters _inside_ an IPD context.

* Users pick ranges for θ, α⁺, α⁻, δ, τ.
* We evaluate each combination against a configurable field of opponents
  via `tournaments.run_round_robin.run_tournament`.
* Results are shown as a leaderboard + heat-map.

IPD-specific glue is limited to:
    • the opponent list (Axelrod strategies)
    • the payoff mapping in utm/trust_meter.py
Porting to another repeated game only requires swapping those parts.
"""
from __future__ import annotations
import random, logging
from typing import List, Tuple

import axelrod as axl
import numpy as np
import pandas as pd
import streamlit as st
st.set_page_config(page_title="Mini-Sweep",
                   page_icon="static/IgnitumSolutions_RGB_Icon.png",
                   layout="wide")

from matplotlib import pyplot as plt

from dash.shared import sidebar, PRESETS
from dash.state  import init_state
from tournaments.run_round_robin import run_tournament
from strategies.utm_tft       import UTMTFT
from strategies.utm_wsls      import UTMWSLS
from strategies.utm_tft_wsls  import UTMTFT_WSLS

logging.getLogger("utm.ipd").setLevel(logging.WARNING)

UTM_REGISTRY = {"TFT": UTMTFT, "WSLS": UTMWSLS, "TFT→WSLS": UTMTFT_WSLS}
Grid = Tuple[float, float, float, float, float]       # θ, α⁺, α⁻, δ, τ

def _build_preset_player(name: str) -> axl.Player:
    s = PRESETS[name]
    variant = s.get("variant", "TFT")
    cls = UTM_REGISTRY.get(variant, UTMTFT)
    return cls(
        s.get("theta", 0.6),
        s.get("alpha_pos", 0.02),
        s.get("alpha_neg", 0.7),
        s.get("delta", 0.4),
        s.get("tau", 0.5),
    )

def _single_mean(
    variant: str,
    p: Grid,
    *,
    turns: int,
    reps: int,
    seed: int,
    noise_pct: int,
    opponents: list[str],
    presets: list[str],
    extra_cls: str,
    noise_wrap: bool,
) -> float:
    θ, αp, αn, δ, τ = p
    utm_player = UTM_REGISTRY[variant](θ, αp, αn, δ, τ)

    players: list[axl.Player] = [utm_player]

    players += [next(cls for cls in axl.strategies if cls.name == n)() for n in opponents]

    for name in presets:
        pl = _build_preset_player(name)
        pl.name = name
        players.append(pl)

    if extra_cls:
        try:
            mod, cls_name = extra_cls.rsplit(".", 1)
            extra = getattr(__import__(mod, fromlist=[cls_name]), cls_name)()
            if noise_wrap:
                extra = axl.Noise(extra, noise=0.05)
            players.append(extra)
        except Exception as exc:
            logging.warning("Could not load extra opponent %s: %s", extra_cls, exc)

    if noise_pct == 0:
        df = run_tournament(players, turns=turns, repetitions=reps,
                            seed=seed, quiet=True, csv_dir=None)
    else:
        res = axl.Tournament(players, turns=turns, repetitions=reps,
                             seed=seed, noise=noise_pct/100).play(progress_bar=False)
        df = res.summarise()

    if isinstance(df, pd.DataFrame):
        mask = df.iloc[:, 0].astype(str).str.startswith("UTM-")
        return float(df.loc[mask, "Mean"].iloc[0])
    if isinstance(df, list) and df and isinstance(df[0], (list, tuple)):
        header, *rows = df
        mid = header.index("Mean")
        for r in rows:
            if str(r[0]).startswith("UTM-"):
                return float(r[mid])
    return float("nan")

def _heatmap(df: pd.DataFrame) -> None:
    pivot = df.pivot_table("Mean vs field", index="θ", columns="α⁻", aggfunc="max")
    fig, ax = plt.subplots()
    im = ax.imshow(pivot, aspect="auto")
    ax.set_xlabel("α⁻"); ax.set_ylabel("θ"); ax.set_title("UTM Mean Payoff")
    plt.colorbar(im, ax=ax)
    st.pyplot(fig)

cfg   = sidebar()
state = init_state()

st.title("Mini Parameter Sweep")

colA, colB = st.columns(2)
with colA:
    θ_low , θ_high  = st.slider("θ range", 0.0, 1.0, (0.30, 0.70), 0.01)
    αp_low, αp_high = st.slider("α⁺ range", 0.0, 0.3, (0.02, 0.08), 0.01)
    αn_low, αn_high = st.slider("α⁻ range", 0.1, 1.0, (0.30, 0.80), 0.01)
with colB:
    δ_low , δ_high  = st.slider("δ range", 0.0, 1.0, (0.20, 0.40), 0.01)
    τ_low , τ_high  = st.slider("τ range", 0.05, 0.5, (0.20, 0.40), 0.01)
    noise_pct       = st.slider("Noise (%) during sweep", 0, 20, 0)

colC, colD = st.columns(2)
with colC:
    steps_θ  = st.number_input("θ steps",  2, 20, 5)
    steps_αp = st.number_input("α⁺ steps", 2, 20, 3)
    steps_αn = st.number_input("α⁻ steps", 2, 20, 3)
with colD:
    steps_δ  = st.number_input("δ steps",  2, 20, 3)
    steps_τ  = st.number_input("τ steps",  2, 20, 3)
    rand_ct  = st.number_input("Random combos (if random)", 10, 500, 50)

grid_on     = st.checkbox("Grid search (else random)", False)
run_clicked = st.button("Run Sweep")

if run_clicked:
    θ_vals  = np.linspace(θ_low , θ_high , steps_θ)
    αp_vals = np.linspace(αp_low, αp_high, steps_αp)
    αn_vals = np.linspace(αn_low, αn_high, steps_αn)
    δ_vals  = np.linspace(δ_low , δ_high , steps_δ)
    τ_vals  = np.linspace(τ_low , τ_high , steps_τ)

    if grid_on:
        search: List[Grid] = [
            (θ, αp, αn, δ, τ)
            for θ in θ_vals
            for αp in αp_vals
            for αn in αn_vals
            for δ in δ_vals
            for τ in τ_vals
        ]
    else:
        search = [
            (
                float(random.choice(θ_vals )),
                float(random.choice(αp_vals)),
                float(random.choice(αn_vals)),
                float(random.choice(δ_vals )),
                float(random.choice(τ_vals )),
            )
            for _ in range(rand_ct)
        ]

    bar, means = st.progress(0.0), []
    for i, p in enumerate(search, 1):
        means.append(
            _single_mean(
                cfg["utm_variant"], p,
                turns=cfg["rounds"], reps=cfg["reps"], seed=cfg["seed"],
                noise_pct=noise_pct,
                opponents=cfg["selected_names"],
                presets=cfg["utm_presets"],
                extra_cls=cfg["extra_cls"].strip(),
                noise_wrap=cfg["noise_wrap"],
            )
        )
        bar.progress(i / len(search))

    df = pd.DataFrame(search, columns=["θ", "α⁺", "α⁻", "δ", "τ"])
    df["Mean vs field"] = means
    st.dataframe(df.sort_values("Mean vs field", ascending=False),
                 use_container_width=True)
    _heatmap(df)

    tsv = df.to_csv(sep="\t", index=False)
    st.text_area("Results (TSV – copy/paste)", value=tsv,
                 height=min(400, 32 + 18 * len(df) + 50))
    st.download_button("💾 Download CSV",
                       data=df.to_csv(index=False).encode(),
                       file_name="sweep_results.csv",
                       mime="text/csv")

    state["last_sweep_search"] = search
    state["last_sweep_noise"]  = noise_pct
    st.success("Sweep completed!")

if st.button("🔄 Rerun last grid"):
    if "last_sweep_search" in state:
        search    = state["last_sweep_search"]
        noise_pct = state["last_sweep_noise"]

        bar, means = st.progress(0.0), []
        for i, p in enumerate(search, 1):
            means.append(
                _single_mean(
                    cfg["utm_variant"], p,
                    turns=cfg["rounds"], reps=cfg["reps"], seed=cfg["seed"],
                    noise_pct=noise_pct,
                    opponents=cfg["selected_names"],
                    presets=cfg["utm_presets"],
                    extra_cls=cfg["extra_cls"].strip(),
                    noise_wrap=cfg["noise_wrap"],
                )
            )
            bar.progress(i / len(search))

        df = pd.DataFrame(search, columns=["θ", "α⁺", "α⁻", "δ", "τ"])
        df["Mean vs field"] = means
        st.dataframe(df.sort_values("Mean vs field", ascending=False),
                     use_container_width=True)
        _heatmap(df)

        tsv = df.to_csv(sep="\t", index=False)
        st.text_area("Results (TSV – copy/paste)", value=tsv,
                     height=min(400, 32 + 18 * len(df) + 50))
    else:
        st.warning("No previous sweep in memory.")
