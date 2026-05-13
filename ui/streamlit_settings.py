from __future__ import annotations

import html
import os

import streamlit as st

from ui.streamlit_browser import install_config_start_hide
from ui.streamlit_chat import render_pending_problem_thread
from ui.streamlit_common import trim_summary
from ui.api_client import PersonaGraphAPIError, api_base_url, load_model_catalog
from ui.streamlit_state import default_chat_settings


def settings_value(key: str, fallback=None):
    return st.session_state.get("pg_settings", {}).get(key, fallback)

def render_setting_intro(label: str, description: str) -> None:
    st.markdown(
        f"""
<div class="pg-config-control-label">{html.escape(label)}</div>
<div class="pg-config-control-description">{html.escape(description)}</div>
""",
        unsafe_allow_html=True,
    )

def render_settings_controls(prefix: str) -> dict:
    current = dict(st.session_state.get("pg_settings", default_chat_settings()))
    render_setting_intro(
        "참여 Agent 수",
        "처음 답변을 만들 때 함께 참여할 AI 관점의 수예요. 숫자가 많을수록 더 다양한 의견을 볼 수 있지만, 대화가 조금 길어질 수 있어요.",
    )
    persona_count = st.slider(
        "참여 Agent 수",
        min_value=3,
        max_value=5,
        value=int(current.get("persona_count", 3)),
        help="처음 토론에 참여할 페르소나 수입니다.",
        label_visibility="collapsed",
        key=f"{prefix}_persona_count",
    )

    render_setting_intro(
        "토론 깊이",
        "Agent들이 첫 의견을 낸 뒤 서로의 의견을 얼마나 더 주고받을지 정해요. 1은 빠르게 정리하고, 3은 더 꼼꼼히 따져보는 방식이에요.",
    )
    debate_rounds = st.slider(
        "토론 깊이",
        min_value=1,
        max_value=3,
        value=int(current.get("debate_rounds", 1)),
        help="첫 의견 뒤 Agent들이 서로 반응하는 라운드 수입니다.",
        label_visibility="collapsed",
        key=f"{prefix}_debate_rounds",
    )

    render_setting_intro(
        "후속 답변 Agent 수",
        "대화 중간에 의견을 추가했을 때 몇 명의 Agent가 이어서 답할지 정해요. 적게 두면 빠르고 간결하고, 많게 두면 여러 반응을 비교하기 좋아요.",
    )
    max_reply_agents = st.slider(
        "후속 답변 Agent 수",
        min_value=1,
        max_value=3,
        value=int(current.get("max_reply_agents", 2)),
        help="의견 추가 후 답변할 Agent 수입니다.",
        label_visibility="collapsed",
        key=f"{prefix}_max_reply_agents",
    )

    with st.expander("AI 모델 설정", expanded=False):
        use_llm = st.toggle(
            "실제 AI 응답 사용",
            value=bool(current.get("use_llm", True)),
            key=f"{prefix}_use_llm",
        )
        model_ids, model_labels, default_model, model_warning = available_models_for_ui()
        current_model = str(current.get("model") or default_model).strip() or default_model
        if current_model not in model_ids:
            current_model = default_model
        model = st.selectbox(
            "모델",
            options=model_ids,
            index=model_ids.index(current_model),
            format_func=lambda model_id: model_labels.get(model_id, model_id),
            key=f"{prefix}_model",
        )
        if model_warning:
            st.warning("모델 목록을 불러오지 못해 기본 모델만 표시합니다.")
        temperature = st.slider(
            "답변 변동성",
            min_value=0.0,
            max_value=1.2,
            value=float(current.get("temperature", 0.35)),
            step=0.05,
            key=f"{prefix}_temperature",
        )
        st.caption(f"백엔드 API: {api_base_url()}")

    with st.expander("검색 설정", expanded=False):
        search_options = {
            "auto": "자동",
            "always": "항상 검색",
            "off": "검색 끄기",
        }
        current_search_mode = str(current.get("search_mode", "auto"))
        if current_search_mode not in search_options:
            current_search_mode = "auto"
        search_mode = st.selectbox(
            "검색 모드",
            options=list(search_options.keys()),
            index=list(search_options.keys()).index(current_search_mode),
            format_func=lambda mode: search_options[mode],
            help="자동은 질문에서 최신성, 추천, 비교, 가격, 메타 같은 신호가 보이면 검색을 사용합니다.",
            key=f"{prefix}_search_mode",
        )

    return {
        "persona_count": persona_count,
        "debate_rounds": debate_rounds,
        "max_reply_agents": max_reply_agents,
        "use_llm": use_llm,
        "model": model,
        "search_mode": search_mode,
        "temperature": temperature,
    }

def available_models_for_ui() -> tuple[list[str], dict[str, str], str, str | None]:
    fallback_model = os.getenv("PERSONA_GRAPH_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini"
    try:
        catalog = load_model_catalog()
    except PersonaGraphAPIError as exc:
        return [fallback_model], {fallback_model: fallback_model}, fallback_model, str(exc)

    model_ids = [option.id for option in catalog.models]
    model_labels = {option.id: option.label for option in catalog.models}
    default_model = catalog.default_model
    if default_model not in model_ids:
        model_ids.insert(0, default_model)
        model_labels[default_model] = default_model
    if not model_ids:
        model_ids = [fallback_model]
        model_labels[fallback_model] = fallback_model
        default_model = fallback_model
    return model_ids, model_labels, default_model, None

def dismiss_settings_dialog() -> None:
    st.session_state["pg_show_settings_dialog"] = False

@st.dialog("실행 설정", width="medium", on_dismiss=dismiss_settings_dialog)
def render_settings_dialog() -> None:
    st.markdown("토론 실행 전에 사용할 기본 설정입니다. 이 값은 현재 Streamlit 세션 안에서만 유지됩니다.")
    settings = render_settings_controls("pg_dialog_settings")
    cols = st.columns(2)
    with cols[0]:
        if st.button("저장", type="primary", use_container_width=True, key="pg_dialog_save"):
            st.session_state["pg_settings"] = settings
            st.session_state["pg_show_settings_dialog"] = False
            st.rerun()
    with cols[1]:
        if st.button("닫기", use_container_width=True, key="pg_dialog_close"):
            st.session_state["pg_show_settings_dialog"] = False
            st.rerun()

def render_configuration_card() -> None:
    problem = st.session_state.get("pg_pending_problem") or ""
    render_pending_problem_thread(problem)
    install_config_start_hide()
    with st.chat_message("assistant", avatar="assistant"):
        st.markdown(
            f"""
<span class="pg-config-bubble-anchor"></span>
<div class="pg-config-title">대화 구성을 확인하세요</div>
""",
            unsafe_allow_html=True,
        )
        settings = render_settings_controls("pg_inline_settings")
        policy = st.radio(
            "설정 확인 방식",
            ["토론 때마다 묻기", "기본값으로 설정"],
            index=0 if st.session_state.get("pg_settings_policy") == "ask_each_time" else 1,
            horizontal=False,
            key="pg_inline_policy",
        )
        start = st.button("시작하기", type="primary", use_container_width=True, key="pg_start_with_settings")
    if start:
        st.session_state["pg_settings"] = settings
        st.session_state["pg_confirmed_settings"] = dict(settings)
        st.session_state["pg_settings_policy"] = (
            "ask_each_time" if policy == "토론 때마다 묻기" else "use_session_default"
        )
        st.session_state["pg_chat_mode"] = "streaming"
        st.rerun()
