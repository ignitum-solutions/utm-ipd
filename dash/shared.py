
"""
dash/shared.py  –  common helpers & sidebar for the Streamlit IPD dashboard.

* Loads preset “personalities” for the Universal Trust Model (UTM).
* Builds the sidebar UI so researchers can tweak UTM hyper-parameters and
  choose opponents for an Iterated Prisoner’s Dilemma tournament.

IPD-specific bits:
    • default opponent list (Axelrod strategy names)
    • `_load_presets()` reward lookup (can pull from S3)

Everything else is generic dashboard/UI code; swap the opponent list and
presets loader to port UTM to another repeated-game environment.
"""

from __future__ import annotations
import pathlib, streamlit as st, logging, os, yaml, boto3, datetime, uuid, json
from utm.log_config import setup_logging

if "libs" not in st.session_state:
    setup_logging(level_console="INFO")
    log = logging.getLogger("utm.ipd")
    import axelrod as axl
    from strategies.utm_tft import UTMTFT
    from strategies.utm_wsls import UTMWSLS
    from strategies.utm_tft_wsls import UTMTFT_WSLS
    st.session_state.libs = (
        axl,
        [cls.name for cls in axl.strategies],
        {"TFT": UTMTFT, "WSLS": UTMWSLS, "TFT→WSLS": UTMTFT_WSLS},
    )

axl, STRATEGY_NAMES, UTM_REGISTRY = st.session_state.libs
_LOGO = pathlib.Path(__file__).parent / "static" / "IgnitumSolutions_Logo.png"

def _load_presets() -> dict:
    """
    Load UTM personality presets from either:

    * local YAML  – default `config/presets.yaml`
    * S3 URI      – set env var  PRESETS_S3_URI="s3://bucket/key.yaml"

    The S3 option lets instructors update classroom presets without
    redeploying the app.  File format:   {preset_name: {theta: …, …}}
    """
    uri = os.getenv("PRESETS_S3_URI", "config/presets.yaml")
    if uri.startswith("s3://"):
        s3 = boto3.client("s3")
        bucket, key = uri.replace("s3://", "").split("/", 1)
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        return yaml.safe_load(body) or {}
    try:
        with open(uri, "r") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {}

PRESETS: dict = _load_presets()

def _fmt(x): return "—" if x is None else f"{x:.2f}"

@st.dialog("Suggest a UTM preset", width="large")
def reco_dialog():
    name = st.text_input("Name (e.g. Diplomat/Narcissist)", key="d_name")
    theta = st.slider("θ", 0.0, 1.0, 0.6, 0.01, key="d_theta")
    alpha_pos = st.slider("α⁺", 0.0, 0.5, 0.03, 0.001, key="d_ap")
    alpha_neg = st.slider("α⁻", 0.0, 1.0, 0.9, 0.01, key="d_an")
    delta = st.slider("δ", 0.0, 1.0, 0.8, 0.01, key="d_delta")
    tau = st.slider("τ", 0.05, 1.0, 0.6, 0.01, key="d_tau")
    creator = st.text_input("Your name / handle", key="d_creator")
    desc = st.text_area("Why is this interesting?", key="d_desc")
    if st.button("Submit", key="d_submit"):
        prefix = os.getenv("SUBMIT_PREFIX")
        if prefix:
            bucket, *rest = prefix.replace("s3://", "").split("/", 1)
            key = f"{(rest[0] if rest else '')}{datetime.datetime.utcnow():%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex}.json"
            boto3.client("s3").put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(
                    dict(
                        name=name, creator=creator, theta=theta,
                        alpha_pos=alpha_pos, alpha_neg=alpha_neg,
                        delta=delta, tau=tau, description=desc
                    )
                ).encode(),
                ContentType="application/json",
            )
            st.toast("✅ Suggestion saved; thanks!")
            st.rerun()
        else:
            st.error("SUBMIT_PREFIX environment variable not set.")

def sidebar() -> dict:
    # ─── UTM hyper-parameters ─────────────────────────────────────────────
    # These five sliders map 1-to-1 onto UTM symbols θ, α⁺, α⁻, δ, τ.
    # Changing them does **not** alter PD payoffs; they only steer the
    # learner’s internal trust dynamics.

    if _LOGO.exists():
        st.logo(str(_LOGO), size="large")

    c: dict = {}
    st.sidebar.markdown("### UTM parameters")
    c["theta"] = st.sidebar.slider("θ Initial Trust", 0.0, 1.0, 0.6, 0.01)
    c["alpha_pos"] = st.sidebar.slider("α⁺ Learning Rate (+)", 0.0, 0.5, 0.02, 0.001)
    c["alpha_neg"] = st.sidebar.slider("α⁻ Learning Rate (-)", 0.0, 1.0, 0.675, 0.01)
    c["delta"] = st.sidebar.slider("δ Betrayal Ramp", 0.0, 1.0, 0.45, 0.01)
    c["threshold"] = st.sidebar.slider("τ Threshold", 0.05, 1.0, 0.5, 0.01)
    c["utm_variant"] = st.sidebar.radio("Inner strategy", list(UTM_REGISTRY.keys()), horizontal=True)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Classic opponents")

    # ─── Opponent selection (IPD-specific) ────────────────────────────────
    # Strategy names come straight from Axelrod-Python.  Swap this list if
    # you plug UTM into another repeated-game framework.

    default_bots = [
        "Tit For Tat", "Defector", "Win-Stay Lose-Shift", "Random",
        "ZD-Extort-2", "EvolvedLookerUp2_2_2", "AON2",
        "Adaptive Pavlov 2011", "Meta Hunter",
    ]
    c["selected_names"] = st.sidebar.multiselect("Choose bots", STRATEGY_NAMES, default=default_bots)

    st.sidebar.markdown("#### UTM personalities (Battle-Royale)")
    preset_selections: list[str] = []
    with st.sidebar.expander("Select personalities"):
        for name, spec in PRESETS.items():
            tip = (
                f"Creator: {spec.get('creator','Unknown')}\n"
                f"{spec.get('description','')}\n\n"
                f"θ={_fmt(spec.get('theta'))}  "
                f"α⁺={_fmt(spec.get('alpha_pos'))}  "
                f"α⁻={_fmt(spec.get('alpha_neg'))}\n"
                f"δ={_fmt(spec.get('delta'))}  "
                f"τ={_fmt(spec.get('tau'))}"
            )
            if st.checkbox(name, key=f"preset_{name}", help=tip):
                preset_selections.append(name)
    c["utm_presets"] = preset_selections

    with st.sidebar.expander("Advanced: custom opponent"):
        c["extra_cls"] = st.text_input("Fully-qualified class (e.g. axelrod.Grudger)")
        c["noise_wrap"] = st.checkbox("Add 5 % noise wrapper", value=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Tournament")
    c["rounds"] = st.sidebar.number_input("Rounds / match", 50, 1000, 200, 50)
    c["reps"] = st.sidebar.number_input("Repetitions", 1, 100, 30)
    c["seed"] = st.sidebar.number_input("Seed", 0, 9999, 42)
    c["noise_pct"] = st.sidebar.slider("Noise (%)", 0, 20, 0)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <style>
        .run-sim button{font-size:18px!important;font-weight:700!important;width:100%!important;background:#1f77b4!important;color:white!important;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    c["run_clicked"] = st.sidebar.button("▶ Run simulation", key="run_sim", help="Start tournament", type="primary", use_container_width=True)
    st.sidebar.markdown("---")
    if st.sidebar.button("Reset History"):
        st.session_state.get("history", []).clear()

    if st.sidebar.button("Recommend new personality", key="recommend_btn"):
        reco_dialog()

    sha = os.getenv("GIT_SHA", "unknown")
    st.sidebar.markdown(
        f"**Version:** [`{sha[:7]}`](https://github.com/ignitum-solutions/utm-ipd/commit/{sha})"
    )
    st.session_state.update(c)
    return c

def git_sha(short: bool = True, default: str = "dev") -> str:
    """
    Return the git commit baked into the Docker image.
    • short=True  → first 7 chars   (e.g. 1a2b3c4)
    • short=False → full 40-char SHA
    """
    sha = os.getenv("GIT_SHA", default)
    return sha[:7] if short else sha