from __future__ import annotations

import streamlit as st

def render_top_actions() -> None:
    st.markdown('<div class="pg-main-topbar"></div>', unsafe_allow_html=True)
