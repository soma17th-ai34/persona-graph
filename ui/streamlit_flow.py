from __future__ import annotations

import streamlit as st

from ui.streamlit_browser import install_composer_autosize
from ui.streamlit_chat import render_chat_thread, render_empty_state
from ui.streamlit_settings import render_configuration_card
from ui.streamlit_streaming import run_followup_stream, run_initial_stream


def render_chat_body() -> None:
    mode = st.session_state.get("pg_chat_mode", "empty")
    response = st.session_state.get("pg_current_response")
    if mode == "streaming":
        run_initial_stream()
        return
    if mode == "streaming_followup":
        run_followup_stream()
        return
    if mode == "configuring":
        render_configuration_card()
        return
    if response is not None:
        render_chat_thread(
            response,
            confirmed_settings=st.session_state.get("pg_confirmed_settings"),
        )
        return
    render_empty_state()

def render_chat_composer() -> None:
    mode = st.session_state.get("pg_chat_mode", "empty")
    if mode in {"streaming", "streaming_followup", "configuring"}:
        return

    placeholder = (
        "무엇이든 물어보세요"
        if mode == "empty"
        else "이 대화에 의견을 추가하세요"
    )
    composer_kind = "empty" if mode == "empty" else "docked"
    prompt = render_prompt_form(
        placeholder=placeholder,
        composer_kind=composer_kind,
        key=f"pg_{composer_kind}_prompt",
    )
    install_composer_autosize()

    if prompt is None:
        return

    content = prompt.strip()
    if not content:
        st.warning("내용을 한 글자 이상 입력해주세요.")
        return

    if mode == "completed" and st.session_state.get("pg_current_response") is not None:
        st.session_state["pg_pending_followup"] = content
        st.session_state["pg_clear_draft"] = True
        st.session_state["pg_chat_mode"] = "streaming_followup"
        st.rerun()
        return

    st.session_state["pg_pending_problem"] = content
    if st.session_state.get("pg_settings_policy") == "use_session_default":
        st.session_state["pg_confirmed_settings"] = dict(st.session_state["pg_settings"])
        st.session_state["pg_chat_mode"] = "streaming"
    else:
        st.session_state["pg_chat_mode"] = "configuring"
    st.rerun()

def render_prompt_form(placeholder: str, composer_kind: str, key: str) -> str | None:
    anchor_class = (
        "pg-empty-composer-anchor"
        if composer_kind == "empty"
        else "pg-docked-composer-anchor"
    )
    with st.form(
        f"{key}_form",
        clear_on_submit=True,
        border=False,
    ):
        st.markdown(f'<span class="{anchor_class}"></span>', unsafe_allow_html=True)
        value = st.text_area(
            "메시지",
            key=f"{key}_text",
            placeholder=placeholder,
            height=44,
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "보내기",
            icon=":material/arrow_upward:",
            type="primary",
        )
    if submitted:
        return value
    return None
