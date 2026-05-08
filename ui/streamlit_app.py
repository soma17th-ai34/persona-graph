from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
import streamlit as st


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

st.set_page_config(
    page_title="PersonaGraph",
    page_icon="PG",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.streamlit_flow import render_chat_body, render_chat_composer
from ui.streamlit_header import render_top_actions
from ui.streamlit_settings import render_settings_dialog
from ui.streamlit_sidebar import render_chat_sidebar
from ui.streamlit_state import ensure_chat_state
from ui.streamlit_styles import render_chat_styles


def render_chat_app() -> None:
    ensure_chat_state()
    render_chat_styles()
    render_chat_sidebar()
    render_top_actions()
    if st.session_state.get("pg_show_settings_dialog"):
        render_settings_dialog()
    render_chat_body()
    render_chat_composer()


render_chat_app()
