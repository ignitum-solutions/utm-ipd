from __future__ import annotations
import streamlit as st

def init_state():
    """Ensure Streamlit session‑state keys exist."""
    state = st.session_state
    state.setdefault("running", False)
    state.setdefault("future", None)
    state.setdefault("history", [])
    return state