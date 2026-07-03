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
import random, logging, time
from typing import List, Tuple

import axelrod as axl
import numpy as np
import pandas as pd
import streamlit as st
st.set_page_config(page_title="Mini-Sweep",
                   page_icon="static/IgnitumSolutions_RGB_Icon.png",
                   layout="wide")

from matplotlib import pyplot as plt

from dash.opponents import NO_EXTRA_OPPONENT, build_extra_opponent
from dash.shared import sidebar, PRESETS
from dash.sweep_guard import (
    ENABLE_SWEEP_ENV,
    MAX_SWEEP_COMBINATIONS,
    MAX_SWEEP_PLAYERS,
    MAX_SWEEP_REPETITIONS,
    MAX_SWEEP_ROUNDS,
    SweepBusyError,
    SweepDisabledError,
    SweepTimeoutError,
    ensure_sweep_time_remaining,
    ensure_sweep_execution_allowed,
    sweep_execution_guard,
    sweep_ui_enabled,
    validate_sweep_budget,
)
from dash.state  import init_state
from tournaments.run_round_robin import run_tournament
from utm.trust_meter import get_ipd_reward_values, temporary_ipd_reward_values
from strategies.utm_tft       import UTMTFT
from strategies.utm_wsls      import UTMWSLS
from strategies.utm_tft_wsls  import UTMTFT_WSLS
from strategies.utm_pure      import TrustOnlyIPDStrategy


logging.getLogger("utm.ipd").setLevel(logging.WARNING)

UTM_REGISTRY = {
    "TFT":        UTMTFT,
    "WSLS":       UTMWSLS,
    "TFT→WSLS":   UTMTFT_WSLS,
    "Trust-only IPD": TrustOnlyIPDStrategy,
}

Grid = Tuple[float, float, float, float, float]       # θ, α⁺, α⁻, δ, τ

RewardGrid = Tuple[float, float, float, float]  # R(CC), R(DC), R(DD), R(CD)

_IPD_REWARD_LABELS = [
    ("Mutual cooperation", "R(CC)"),
    ("I defect, they cooperate", "R(DC)"),
    ("Mutual defection", "R(DD)"),
    ("I cooperate, they defect", "R(CD)"),
]

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
    reward_params: RewardGrid | None = None,
) -> float:
    ensure_sweep_execution_allowed()
    θ, αp, αn, δ, τ = p
    utm_player = UTM_REGISTRY[variant](θ, αp, αn, δ, τ)

    players: list[axl.Player] = [utm_player]

    players += [next(cls for cls in axl.strategies if cls.name == n)() for n in opponents]

    for name in presets:
        pl = _build_preset_player(name)
        pl.name = name
        players.append(pl)

    extra = build_extra_opponent(extra_cls, noise_wrap=noise_wrap)
    if extra is not None:
        players.append(extra)

    def _run() -> pd.DataFrame:
        return run_tournament(
            players,
            turns=turns,
            repetitions=reps,
            seed=seed,
            noise=noise_pct / 100.0,
            quiet=True,
            csv_dir=None,
        )

    if reward_params is None:
        df = _run()
    else:
        with temporary_ipd_reward_values(*reward_params):
            df = _run()

    mask = df["Player"].astype(str).str.startswith("UTM-")
    if not mask.any():
        logging.warning("UTM player row not found in tournament summary.")
        return float("nan")
    return float(df.loc[mask, "Mean"].iloc[0])


def _heatmap(df: pd.DataFrame) -> None:
    pivot = df.pivot_table("Mean vs field", index="θ", columns="α⁻", aggfunc="max")
    fig, ax = plt.subplots()
    im = ax.imshow(pivot, aspect="auto")
    ax.set_xlabel("α⁻"); ax.set_ylabel("θ"); ax.set_title("UTM Mean Payoff")
    plt.colorbar(im, ax=ax)
    st.pyplot(fig)


def _player_count(cfg: dict) -> int:
    extra = 0 if cfg["extra_cls"] in {"", NO_EXTRA_OPPONENT} else 1
    return 1 + len(cfg["selected_names"]) + len(cfg["utm_presets"]) + extra


def _render_reference_settings(cfg: dict) -> None:
    st.subheader("Reference Settings")
    left, right = st.columns(2)
    with left:
        st.markdown("**Current UTM settings**")
        st.dataframe(
            pd.DataFrame(
                [
                    ("θ Initial trust", cfg["theta"]),
                    ("α⁺ Positive learning", cfg["alpha_pos"]),
                    ("α⁻ Negative learning", cfg["alpha_neg"]),
                    ("δ Betrayal ramp", cfg["delta"]),
                    ("τ Cooperation threshold", cfg["threshold"]),
                    ("Inner strategy", cfg["utm_variant"]),
                ],
                columns=["Parameter", "Value"],
            ),
            hide_index=True,
            use_container_width=True,
        )
    with right:
        st.markdown("**Default IPD reward matrix**")
        values = get_ipd_reward_values()
        st.dataframe(
            pd.DataFrame(
                [
                    {"Outcome": label, "Symbol": symbol, "Reward": reward}
                    for (label, symbol), reward in zip(_IPD_REWARD_LABELS, values)
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    st.caption("These settings are displayed without launching a live sweep.")

cfg   = sidebar()
state = init_state()

st.title("Mini Parameter Sweep")
_render_reference_settings(cfg)

if not sweep_ui_enabled():
    st.info(
        "Live sweep execution is disabled on the hosted demo to protect shared "
        "CPU. The default UTM settings and IPD reward matrix remain visible "
        "above, and the sweep source code is available for local/offline "
        "research runs."
    )
    st.code(
        f"{ENABLE_SWEEP_ENV}=true poetry run streamlit run dash/pages/01_IPD_Mini_Sweep.py",
        language="bash",
    )
    st.stop()

st.warning(
    "Sweeps are CPU-intensive. This local tool allows one sweep at a time and "
    "uses conservative request limits: "
    f"{MAX_SWEEP_COMBINATIONS} combinations, {MAX_SWEEP_ROUNDS} rounds, "
    f"{MAX_SWEEP_REPETITIONS} repetitions, and {MAX_SWEEP_PLAYERS} players."
)
sweep_rounds = min(int(cfg["rounds"]), MAX_SWEEP_ROUNDS)
sweep_reps = min(int(cfg["reps"]), MAX_SWEEP_REPETITIONS)
if sweep_rounds != int(cfg["rounds"]) or sweep_reps != int(cfg["reps"]):
    st.caption(
        f"Sweep runs are capped at {sweep_rounds} rounds and {sweep_reps} "
        "repetitions, even if the sidebar tournament settings are higher."
    )

colA, colB = st.columns(2)
with colA:
    θ_low , θ_high  = st.slider("θ range", 0.0, 1.0, (0.30, 0.70), 0.01)
    αp_low, αp_high = st.slider("α⁺ range", 0.0, 0.3, (0.02, 0.08), 0.01)
    αn_low, αn_high = st.slider("α⁻ range", 0.1, 1.0, (0.30, 0.80), 0.01)
with colB:
    δ_low , δ_high  = st.slider("δ range", 0.0, 1.0, (0.20, 0.40), 0.01)
    τ_low , τ_high  = st.slider("τ range", 0.05, 0.5, (0.20, 0.40), 0.01)
    noise_pct = cfg["noise_pct"]
    st.markdown(f"Noise during sweep: **{noise_pct}%** (from sidebar)")

st.markdown("---")
sweep_mode = st.radio(
    "Sweep mode",
    ["UTM parameters", "IPD reward matrix"],
    horizontal=True,
)

if sweep_mode == "IPD reward matrix":
    st.markdown("#### IPD reward matrix")
    st.caption(
        "These controls vary the IPD outcome-to-reward mapping used by this "
        "simulation only."
    )
    r_cc_low, r_cc_high = st.slider("R(CC) – mutual cooperation",
                                    0.3, 1.5, (1.0, 1.0), 0.05)
    r_dc_low, r_dc_high = st.slider("R(DC) – exploit opponent",
                                    0.0, 1.0, (0.5, 0.5), 0.05)
    r_dd_low, r_dd_high = st.slider("R(DD) – mutual defection",
                                    -1.0, 0.2, (-0.2, -0.2), 0.05)
    r_cd_low, r_cd_high = st.slider("R(CD) – betrayed",
                                    -2.0, -0.1, (-1.0, -1.0), 0.05)


colC, colD = st.columns(2)
if sweep_mode == "UTM parameters":
    with colC:
        steps_θ  = st.number_input("θ steps",  2, 20, 5)
        steps_αp = st.number_input("α⁺ steps", 2, 20, 3)
        steps_αn = st.number_input("α⁻ steps", 2, 20, 3)
    with colD:
        steps_δ  = st.number_input("δ steps",  2, 20, 3)
        steps_τ  = st.number_input("τ steps",  2, 20, 3)
        rand_ct  = st.number_input("Random combos (if random)", 10, MAX_SWEEP_COMBINATIONS, 32)
else:
    with colC:
        steps_r_cc = st.number_input("R(CC) steps", 2, 10, 3)
        steps_r_dc = st.number_input("R(DC) steps", 2, 10, 3)
    with colD:
        steps_r_dd = st.number_input("R(DD) steps", 2, 10, 3)
        steps_r_cd = st.number_input("R(CD) steps", 2, 10, 3)
        rand_ct    = st.number_input("Random combos (if random)", 10, MAX_SWEEP_COMBINATIONS, 32)


grid_on     = st.checkbox("Grid search (else random)", False)
run_clicked = st.button("Run Sweep")

if run_clicked:
    try:
        with sweep_execution_guard():
            started_at = time.monotonic()
            if sweep_mode == "UTM parameters":
                θ_vals  = np.linspace(θ_low , θ_high , steps_θ)
                αp_vals = np.linspace(αp_low, αp_high, steps_αp)
                αn_vals = np.linspace(αn_low, αn_high, steps_αn)
                δ_vals  = np.linspace(δ_low , δ_high , steps_δ)
                τ_vals  = np.linspace(τ_low , τ_high, steps_τ)

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

                validate_sweep_budget(
                    combinations=len(search),
                    rounds=sweep_rounds,
                    repetitions=sweep_reps,
                    players=_player_count(cfg),
                )

                bar, means = st.progress(0.0), []
                for i, p in enumerate(search, 1):
                    ensure_sweep_time_remaining(started_at)
                    means.append(
                        _single_mean(
                            cfg["utm_variant"], p,
                            turns=sweep_rounds, reps=sweep_reps, seed=cfg["seed"],
                            noise_pct=noise_pct,
                            opponents=cfg["selected_names"],
                            presets=cfg["utm_presets"],
                            extra_cls=cfg["extra_cls"].strip(),
                            noise_wrap=cfg["noise_wrap"],
                            reward_params=None,
                        )
                    )
                    bar.progress(i / len(search))

                df = pd.DataFrame(search, columns=["θ", "α⁺", "α⁻", "δ", "τ"])
                df["Mean vs field"] = means
                st.dataframe(df.sort_values("Mean vs field", ascending=False),
                             use_container_width=True)
                _heatmap(df)
                state["last_sweep_search"] = search
            else:
                # IPD reward-matrix sweep mode
                r_cc_vals = np.linspace(r_cc_low, r_cc_high, steps_r_cc)
                r_dc_vals = np.linspace(r_dc_low, r_dc_high, steps_r_dc)
                r_dd_vals = np.linspace(r_dd_low, r_dd_high, steps_r_dd)
                r_cd_vals = np.linspace(r_cd_low, r_cd_high, steps_r_cd)

                if grid_on:
                    search_rewards: List[RewardGrid] = [
                        (r_cc, r_dc, r_dd, r_cd)
                        for r_cc in r_cc_vals
                        for r_dc in r_dc_vals
                        for r_dd in r_dd_vals
                        for r_cd in r_cd_vals
                    ]
                else:
                    search_rewards = [
                        (
                            float(random.choice(r_cc_vals)),
                            float(random.choice(r_dc_vals)),
                            float(random.choice(r_dd_vals)),
                            float(random.choice(r_cd_vals)),
                        )
                        for _ in range(rand_ct)
                    ]

                validate_sweep_budget(
                    combinations=len(search_rewards),
                    rounds=sweep_rounds,
                    repetitions=sweep_reps,
                    players=_player_count(cfg),
                )

                # Use current UTM sliders from the sidebar as the fixed trust profile
                fixed_p: Grid = (
                    cfg["theta"],
                    cfg["alpha_pos"],
                    cfg["alpha_neg"],
                    cfg["delta"],
                    cfg["threshold"],
                )

                bar, means = st.progress(0.0), []
                for i, r in enumerate(search_rewards, 1):
                    ensure_sweep_time_remaining(started_at)
                    means.append(
                        _single_mean(
                            cfg["utm_variant"],
                            fixed_p,
                            turns=sweep_rounds,
                            reps=sweep_reps,
                            seed=cfg["seed"],
                            noise_pct=noise_pct,
                            opponents=cfg["selected_names"],
                            presets=cfg["utm_presets"],
                            extra_cls=cfg["extra_cls"].strip(),
                            noise_wrap=cfg["noise_wrap"],
                            reward_params=r,
                        )
                    )
                    bar.progress(i / len(search_rewards))

                df = pd.DataFrame(
                    search_rewards,
                    columns=["R(CC)", "R(DC)", "R(DD)", "R(CD)"],
                )
                df["Mean vs field"] = means
                st.dataframe(df.sort_values("Mean vs field", ascending=False),
                             use_container_width=True)

                # Simple 2D heatmap: R(CC) vs R(CD)
                pivot = df.pivot_table(
                    "Mean vs field", index="R(CC)", columns="R(CD)", aggfunc="max"
                )
                fig, ax = plt.subplots()
                im = ax.imshow(pivot, aspect="auto")
                ax.set_xlabel("R(CD) – betrayed")
                ax.set_ylabel("R(CC) – mutual cooperation")
                ax.set_title("UTM Mean Payoff (IPD reward-matrix sweep)")
                plt.colorbar(im, ax=ax)
                st.pyplot(fig)
                state["last_sweep_search"] = search_rewards

            # common TSV + download
            tsv = df.to_csv(sep="\t", index=False)
            st.text_area("Results (TSV – copy/paste)", value=tsv,
                         height=min(400, 32 + 18 * len(df) + 50))
            st.download_button("💾 Download CSV",
                               data=df.to_csv(index=False).encode(),
                               file_name="sweep_results.csv",
                               mime="text/csv")

            state["last_sweep_noise"] = noise_pct
            st.success("Sweep completed!")
    except (SweepDisabledError, SweepBusyError, SweepTimeoutError, ValueError) as exc:
        st.error(str(exc))
