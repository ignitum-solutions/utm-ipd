import streamlit as st, pathlib
st.set_page_config(page_title="UTM Explained", page_icon="static/IgnitumSolutions_RGB_Icon.png", layout="wide")
from dash.shared import sidebar
sidebar()
md = pathlib.Path(__file__).with_suffix(".md")
st.markdown(md.read_text(), unsafe_allow_html=True)
