from __future__ import annotations

import html

import streamlit as st

from app.schemas import SolveResponse
from ui.streamlit_browser import scroll_chat_to_bottom
from ui.streamlit_common import (
    SAMPLE_PROBLEMS,
    avatar_markup,
    character_class,
    character_for_persona,
    message_content_html,
    stage_meta_label,
    system_avatar_label,
    trim_summary,
)


def initial_problem_item(response: SolveResponse) -> dict:
    return {
        "kind": "user",
        "name": "나",
        "meta": "처음 입력한 문제",
        "content": response.problem,
    }

def persona_intro_item(persona) -> dict:
    character = character_for_persona(persona)
    role = persona.role
    perspective = persona.perspective
    content = (
        f"안녕하세요. 저는 {persona.name}입니다.\n"
        f"{role}로 도와드릴게요.\n"
        f"{trim_summary(perspective, 120)}"
    )
    return {
        "kind": "agent",
        "name": persona.name,
        "meta": "페르소나 소개",
        "content": content,
        "character": character,
        "avatar_name": persona.name,
    }

def message_item(message, personas_by_id: dict) -> dict | None:
    if message.stage == "persona_generation":
        return None
    if message.stage == "user":
        return {
            "kind": "user",
            "name": "나",
            "meta": "내 의견",
            "content": message.content,
        }

    persona = personas_by_id.get(message.agent_id)
    character = character_for_persona(persona)
    is_persona_message = message.stage in {"specialist", "debate"}
    kind = "agent" if is_persona_message else "system"
    fallback = system_avatar_label(message.agent_id, message.agent_name, message.stage)
    return {
        "kind": kind,
        "name": message.agent_name,
        "meta": stage_meta_label(message),
        "content": message.content,
        "character": character,
        "avatar_name": message.agent_name,
        "avatar_fallback": fallback,
    }

def chat_thread_items(response: SolveResponse, confirmed_settings: dict | None = None) -> list[dict]:
    personas_by_id = {persona.id: persona for persona in response.personas}
    items = [initial_problem_item(response)]
    settings_item = settings_summary_item(confirmed_settings)
    if settings_item:
        items.append(settings_item)
    items.extend(persona_intro_item(persona) for persona in response.personas)
    for message in response.messages:
        item = message_item(message, personas_by_id)
        if item:
            items.append(item)
    return items

def settings_summary_item(settings: dict | None) -> dict | None:
    if not settings:
        return None
    persona_count = int(settings.get("persona_count", 3))
    debate_rounds = int(settings.get("debate_rounds", 1))
    max_reply_agents = int(settings.get("max_reply_agents", 2))
    content = (
        "이 설정으로 토론을 시작할게요.\n"
        f"참여 Agent 수: {persona_count}명\n"
        f"토론 깊이: {debate_rounds}단계\n"
        f"후속 답변 Agent 수: {max_reply_agents}명"
    )
    return {
        "kind": "system",
        "name": "PersonaGraph",
        "meta": "대화 설정",
        "content": content,
        "avatar_name": "PersonaGraph",
        "avatar_fallback": "PG",
    }

def render_chat_bubble(item: dict) -> None:
    kind = item.get("kind", "agent")
    name = str(item.get("name", "Agent"))
    meta = str(item.get("meta", ""))
    content = str(item.get("content", ""))
    character = item.get("character")
    character_css = character_class(character)

    if kind == "user":
        st.markdown(
            f"""
<div class="pg-chat-shell">
<div class="pg-chat-row pg-chat-row-user">
  <div class="pg-chat-bubble pg-chat-bubble-user">
    <div class="pg-message-meta"><span class="pg-message-name">{html.escape(name)}</span><span>{html.escape(meta)}</span></div>
    {message_content_html(content)}
  </div>
</div>
</div>
""",
            unsafe_allow_html=True,
        )
        return

    bubble_class = "pg-chat-bubble-system" if kind == "system" else "pg-chat-bubble-agent"
    row_class = "pg-chat-row-system" if kind == "system" else "pg-chat-row-agent"
    avatar = avatar_markup(
        str(item.get("avatar_name", name)),
        character,
        str(item.get("avatar_fallback", "")),
    )
    st.markdown(
        f"""
<div class="pg-chat-shell">
<div class="pg-chat-row {row_class}">
  <div class="pg-chat-avatar-wrap">{avatar}</div>
  <div class="pg-chat-bubble {bubble_class} {character_css}">
    <div class="pg-message-meta"><span class="pg-message-name">{html.escape(name)}</span><span>{html.escape(meta)}</span></div>
    {message_content_html(content)}
  </div>
</div>
</div>
""",
        unsafe_allow_html=True,
    )

def render_chat_thread(
    response: SolveResponse,
    include_anchor: bool = True,
    confirmed_settings: dict | None = None,
) -> None:
    for item in chat_thread_items(response, confirmed_settings=confirmed_settings):
        render_chat_bubble(item)
    if include_anchor:
        st.markdown('<div id="pg-chat-bottom" class="pg-scroll-anchor"></div>', unsafe_allow_html=True)
        scroll_chat_to_bottom()

def render_confirmed_settings_bubble(settings: dict | None) -> None:
    item = settings_summary_item(settings)
    if item:
        render_chat_bubble(item)

def render_pending_problem_thread(problem: str) -> None:
    render_chat_bubble(
        {
            "kind": "user",
            "name": "나",
            "meta": "처음 입력한 문제",
            "content": problem,
        }
    )

def fill_sample_problem(problem: str) -> None:
    st.session_state["pg_empty_prompt_text"] = problem

def render_empty_state() -> None:
    samples = [
        ("AI 프로젝트 MVP", SAMPLE_PROBLEMS["Software Maestro 프로젝트 선정"]),
        ("팀 프로젝트 계획", SAMPLE_PROBLEMS["캠퍼스 팀 프로젝트 리스크"]),
        ("Physical AI 검증", SAMPLE_PROBLEMS["Physical AI 아이디어 검증"]),
    ]
    st.markdown(
        """
<div class="pg-empty-state">
  <div class="pg-empty-title">어떤 문제를 고민중이신가요?</div>
  <div class="pg-empty-subtitle">여러 관점이 필요한 결정을 함께 정리해드릴게요.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    with st.container(key="pg_empty_samples"):
        st.markdown('<span class="pg-empty-samples-anchor"></span>', unsafe_allow_html=True)
        cols = st.columns(3, gap="small")
        for index, (label, problem) in enumerate(samples):
            with cols[index]:
                st.button(
                    label,
                    key=f"pg_sample_problem_{index}",
                    use_container_width=True,
                    on_click=fill_sample_problem,
                    args=(problem,),
                )
