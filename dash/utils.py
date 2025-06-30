from __future__ import annotations
import os
import pandas as pd, streamlit as st
import yaml, boto3, io, urllib.parse as up
from pandas.errors import PyperclipException
from .plots import render_plots

def _ensure_header(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    if "Mean" in df.columns:
        return df
    hdr_idx = next((i for i, row in df.iterrows() if "Mean" in row.values), None)
    if hdr_idx is not None:
        hdr = df.iloc[hdr_idx].astype(str).tolist()
        df = df.iloc[hdr_idx + 1:].copy()
        df.columns = hdr
    return df.reset_index(drop=True)

def summarise_run(**kw) -> str:
    strat_list = [f"UTM-{kw['utm_variant']}", *kw["selected_names"]]
    if kw["extra_cls"]:
        strat_list.append(kw["extra_cls"] + (" + Noise" if kw["noise_wrap"] else ""))
    return (
        f"**Strategies:** {', '.join(strat_list)}  \n"
        f"**UTM:** θ={kw['theta']:.2f}, α⁺={kw['alpha_pos']:.2f}, "
        f"α⁻={kw['alpha_neg']:.2f}, δ={kw['delta']:.2f}, τ={kw['threshold']:.2f}  \n"
        f"**Tournament:** {kw['rounds']} rounds × {kw['reps']} reps (seed {kw['seed']})  \n"
        f"**Noise:** {kw['noise_pct']} %"
    )

def render_results(state, df: pd.DataFrame, players, results, copy_key: str):
    df = _ensure_header(df)
    df.columns = df.columns.map(str)
    st.success("✅ Tournament completed")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if st.button("📋 Copy leaderboard", key=copy_key):
        tsv = df.to_csv(sep="\t", index=False)
        try:
            df.to_clipboard(index=False, sep="\t")
            st.toast("Copied!")
        except (PyperclipException, RuntimeError):
            st.warning("Automatic copy failed – copy manually.")
            st.text_area("TSV", value=tsv, height=min(450, 32 + 18 * len(df) + 50))
    render_plots(players, results)
    state.last_leaderboard = df
    state.last_players = players
    state.last_results = results
    state.have_results = True

def _load_presets() -> dict:
    """YAML from repo OR s3://bucket/key if PRESETS_S3_URI is set."""
    uri = os.getenv("PRESETS_S3_URI", "config/presets.yaml")
    if uri.startswith("s3://"):
        s3 = boto3.client("s3")
        bucket, key = uri.replace("s3://", "").split("/", 1)
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        return yaml.safe_load(body)
    with open(uri, "r") as fh:
        return yaml.safe_load(fh)

PRESETS = _load_presets()