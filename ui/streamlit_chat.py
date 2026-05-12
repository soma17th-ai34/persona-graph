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
    perspective = persona.perspective
    content = trim_summary(perspective, 120)
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
    if message.stage == "critic":
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
        "stage": message.stage,
        "round": message.metadata.get("round"),
        "phase": message.metadata.get("phase"),
        "groupable": message.stage in {"specialist", "debate"},
    }

def chat_thread_items(response: SolveResponse, confirmed_settings: dict | None = None) -> list[dict]:
    personas_by_id = {persona.id: persona for persona in response.personas}
    items = [initial_problem_item(response)]
    items.extend(persona_intro_item(persona) for persona in response.personas)
    for message in response.messages:
        item = message_item(message, personas_by_id)
        if item:
            items.append(item)
    return items

def grouped_chat_thread_items(
    response: SolveResponse,
    confirmed_settings: dict | None = None,
) -> list[dict]:
    return group_agent_items(chat_thread_items(response, confirmed_settings=confirmed_settings))

def group_agent_items(
    items: list[dict],
    expand_last_group: bool = False,
    expanded_group_key: str | None = None,
) -> list[dict]:
    grouped_items: list[dict] = []
    agent_group: list[dict] = []
    group_index = 0

    def flush_group() -> None:
        nonlocal agent_group, group_index
        if not agent_group:
            return
        grouped_items.append(agent_group_item(agent_group, group_index))
        group_index += 1
        agent_group = []

    for item in items:
        if item.get("groupable"):
            agent_group.append(item)
        else:
            flush_group()
            grouped_items.append(item)
    flush_group()

    if expanded_group_key is not None:
        for item in grouped_items:
            if item.get("kind") == "agent_group":
                item["expanded"] = item.get("group_key") == expanded_group_key
    elif expand_last_group:
        for item in reversed(grouped_items):
            if item.get("kind") == "agent_group":
                item["expanded"] = True
                break
    return grouped_items

def agent_group_item(agent_items: list[dict], group_index: int) -> dict:
    first_item = agent_items[0]
    stage = first_item.get("stage")
    round_number = first_item.get("round")
    phase = first_item.get("phase")
    speaker_count = len(agent_items)

    if stage == "specialist":
        title = "Agent 첫 의견"
    elif phase == "user_response":
        title = "후속 Agent 답변"
    elif round_number:
        title = f"{round_number}라운드 Agent 발화"
    else:
        title = "Agent 발화"

    return {
        "kind": "agent_group",
        "items": agent_items,
        "title": title,
        "meta": f"{speaker_count}개 발화",
        "group_id": group_index,
        "group_key": agent_group_key(first_item, group_index),
        "expanded": False,
    }

def agent_group_key(item: dict, group_index: int | None = None) -> str:
    stage = str(item.get("stage") or "agent")
    round_number = item.get("round")
    phase = str(item.get("phase") or "")
    if stage == "specialist":
        return "specialist_initial"
    if round_number:
        return f"{stage}_round_{round_number}"
    if group_index is not None:
        return f"{stage}_{phase}_group_{group_index}"
    return f"{stage}_{phase}"

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

def render_agent_group(item: dict) -> None:
    title = str(item.get("title", "Agent 발화"))
    meta = str(item.get("meta", ""))
    label = f"{title} · {meta}" if meta else title
    open_attribute = " open" if item.get("expanded", False) else ""

    rows = [
        f"""
<details class="pg-agent-group-details"{open_attribute}>
  <summary>{html.escape(label)}</summary>
  <div class="pg-agent-group-content">
    <span class="pg-agent-group-content-anchor"></span>
"""
    ]
    for agent_item in item.get("items", []):
        name = str(agent_item.get("name", "Agent"))
        item_meta = str(agent_item.get("meta", ""))
        content = str(agent_item.get("content", ""))
        character = agent_item.get("character")
        character_css = character_class(character)
        avatar = avatar_markup(
            str(agent_item.get("avatar_name", name)),
            character,
            str(agent_item.get("avatar_fallback", "")),
        )
        rows.append(
            f"""
<div class="pg-agent-group-message">
  <div class="pg-chat-avatar-wrap">{avatar}</div>
  <div class="pg-agent-group-body pg-chat-bubble-agent {character_css}">
    <div class="pg-message-meta"><span class="pg-message-name">{html.escape(name)}</span><span>{html.escape(item_meta)}</span></div>
    {message_content_html(content)}
  </div>
</div>
"""
        )
    rows.append(
        """
  </div>
</details>
"""
    )
    st.markdown("\n".join(rows), unsafe_allow_html=True)

def render_chat_item(item: dict) -> None:
    if item.get("kind") == "agent_group":
        render_agent_group(item)
    else:
        render_chat_bubble(item)

def render_chat_items(items: list[dict]) -> None:
    for item in group_agent_items(items):
        render_chat_item(item)

def render_chat_thread(
    response: SolveResponse,
    include_anchor: bool = True,
    confirmed_settings: dict | None = None,
) -> None:
    for item in grouped_chat_thread_items(response, confirmed_settings=confirmed_settings):
        render_chat_item(item)
    if include_anchor:
        st.markdown('<div id="pg-chat-bottom" class="pg-scroll-anchor"></div>', unsafe_allow_html=True)
        scroll_chat_to_bottom()

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
