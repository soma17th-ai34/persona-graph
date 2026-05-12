from __future__ import annotations

import html

import streamlit as st

from ui.api_client import PersonaGraphAPIError, list_run_summaries, load_run_detail
from ui.streamlit_common import normalize_summary_text, trim_summary
from ui.streamlit_state import reset_chat_state


def render_chat_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="pg-sidebar-brand">PersonaGraph</div>',
            unsafe_allow_html=True,
        )

        if st.button(
            "새 채팅",
            key="pg_new_chat",
            icon=":material/edit_square:",
            use_container_width=True,
        ):
            reset_chat_state()
            st.rerun()
        if st.button(
            "실행 설정",
            key="pg_sidebar_settings",
            icon=":material/tune:",
            use_container_width=True,
        ):
            st.session_state["pg_show_settings_dialog"] = True
            st.rerun()

        st.markdown('<div class="pg-sidebar-title">최근</div>', unsafe_allow_html=True)
        try:
            summaries = list_run_summaries()
        except PersonaGraphAPIError as exc:
            st.warning(str(exc))
            return
        if not summaries:
            st.markdown(
                '<div class="pg-sidebar-empty">아직 저장된 대화가 없습니다.</div>',
                unsafe_allow_html=True,
            )

            return

        st.markdown('<div class="pg-sidebar-history">', unsafe_allow_html=True)
        for summary in summaries:
            label = sidebar_run_label(summary)
            selected = summary.run_id == st.session_state.get("pg_current_run_id")
            if selected:
                st.markdown(sidebar_run_card(summary), unsafe_allow_html=True)
                continue
            if st.button(
                label,
                key=f"pg_run_{summary.run_id}",
                type="secondary",
                use_container_width=True,
            ):
                try:
                    response = load_run_detail(summary.run_id)
                except PersonaGraphAPIError as exc:
                    st.warning(str(exc))
                    continue
                st.session_state["pg_current_response"] = response
                st.session_state["pg_current_run_id"] = summary.run_id
                st.session_state["pg_pending_problem"] = None
                st.session_state["pg_pending_followup"] = None
                st.session_state["pg_confirmed_settings"] = None
                st.session_state["pg_chat_mode"] = "completed"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def sidebar_run_label(summary) -> str:
    return trim_summary(normalize_summary_text(summary.problem_preview), 28)

def sidebar_run_card(summary) -> str:
    preview = html.escape(trim_summary(normalize_summary_text(summary.problem_preview), 28))
    return (
        '<div class="pg-sidebar-run">'
        f'<div class="pg-sidebar-run-title">{preview}</div>'
        '<span class="pg-sidebar-active-dot"></span>'
        '</div>'
    )
