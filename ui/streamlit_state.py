from __future__ import annotations

import os

import streamlit as st


def default_chat_settings() -> dict:
    return {
        "persona_count": 3,
        "debate_rounds": 1,
        "max_reply_agents": 2,
        "use_llm": True,
        "model": os.getenv("PERSONA_GRAPH_MODEL", "gpt-5.4-mini"),
        "search_mode": "auto",
        "temperature": 0.35,
    }

def ensure_chat_state() -> None:
    defaults = {
        "pg_chat_mode": "empty",
        "pg_current_response": None,
        "pg_current_run_id": None,
        "pg_draft_problem": "",
        "pg_pending_problem": None,
        "pg_pending_followup": None,
        "pg_confirmed_settings": None,
        "pg_clear_draft": False,
        "pg_settings": default_chat_settings(),
        "pg_settings_policy": "ask_each_time",
        "pg_show_settings_dialog": False,
        "pg_stream_messages": [],
        "pg_stream_personas": [],
        "pg_active_agent": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_chat_state() -> None:
    st.session_state["pg_chat_mode"] = "empty"
    st.session_state["pg_current_response"] = None
    st.session_state["pg_current_run_id"] = None
    st.session_state["pg_draft_problem"] = ""
    st.session_state["pg_pending_problem"] = None
    st.session_state["pg_pending_followup"] = None
    st.session_state["pg_confirmed_settings"] = None
    st.session_state["pg_clear_draft"] = True
    st.session_state["pg_stream_messages"] = []
    st.session_state["pg_stream_personas"] = []
    st.session_state["pg_active_agent"] = None
