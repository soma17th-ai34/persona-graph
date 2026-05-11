from __future__ import annotations

import html
import time

import streamlit as st

from app.schemas import SolveResponse
from app.storage import save_run
from app.workflow import continue_discussion_stream, solve_problem_stream
from ui.streamlit_browser import scroll_chat_to_bottom
from ui.streamlit_chat import (
    agent_group_key,
    group_agent_items,
    message_item,
    persona_intro_item,
    render_chat_bubble,
    render_chat_item,
    render_confirmed_settings_bubble,
    render_chat_thread,
    render_pending_problem_thread,
)
from ui.streamlit_common import (
    avatar_markup,
    character_for_persona,
    live_message_frames,
    system_avatar_label,
)


def render_active_agent_status(active_agent, personas_by_id: dict) -> None:
    if not active_agent:
        return
    stage = str(active_agent.get("stage", "unknown"))
    agent_id = str(active_agent.get("agent_id", ""))
    agent_name = str(active_agent.get("agent_name", "Agent"))
    if stage == "persona_generation":
        label = "페르소나를 구성하고 있습니다..."
        character = None
        fallback = "PG"
    else:
        label = f"{agent_name}가 의견을 정리 중입니다..."
        persona = personas_by_id.get(agent_id)
        character = character_for_persona(persona)
        fallback = system_avatar_label(agent_id, agent_name, stage)
    avatar = avatar_markup(agent_name, character, fallback)
    st.markdown(
        f"""
<div class="pg-chat-shell">
  <div class="pg-chat-row pg-chat-row-agent">
    <div class="pg-chat-avatar-wrap">{avatar}</div>
    <div class="pg-active-status">{html.escape(label)}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

def render_streaming_chat_thread(
    placeholder,
    live_messages,
    live_personas,
    active_event,
    streaming_message=None,
    base_response: SolveResponse | None = None,
    pending_problem: str | None = None,
    confirmed_settings: dict | None = None,
    keep_agent_group_expanded: bool = False,
    expanded_agent_group_key: str | None = None,
    render_context: bool = True,
) -> None:
    with placeholder.container():
        if render_context:
            if base_response is not None:
                render_chat_thread(
                    base_response,
                    include_anchor=False,
                    confirmed_settings=confirmed_settings,
                )
            elif pending_problem:
                render_pending_problem_thread(pending_problem)
                render_confirmed_settings_bubble(confirmed_settings)

        if render_context and base_response is None:
            for persona in live_personas:
                render_chat_bubble(persona_intro_item(persona))
        personas_by_id = {
            persona.id: persona
            for persona in (live_personas or (base_response.personas if base_response else []))
        }
        message_items = []
        for message in live_messages:
            item = message_item(message, personas_by_id)
            if item:
                message_items.append(item)
        if streaming_message is not None:
            item = message_item(streaming_message, personas_by_id)
            if item:
                message_items.append(item)
        is_streaming_agent_message = (
            streaming_message is not None
            and streaming_message.stage in {"specialist", "debate"}
        )
        for item in group_agent_items(
            message_items,
            expand_last_group=is_streaming_agent_message or keep_agent_group_expanded,
            expanded_group_key=expanded_agent_group_key,
        ):
            render_chat_item(item)
        st.markdown('<div id="pg-chat-bottom" class="pg-scroll-anchor"></div>', unsafe_allow_html=True)
        render_active_agent_status(active_event, personas_by_id)
        scroll_chat_to_bottom(smooth=False)

def consume_chat_stream(
    events,
    base_response: SolveResponse | None = None,
    pending_problem: str | None = None,
    initial_personas=None,
) -> SolveResponse | None:
    live_messages = []
    live_personas = list(initial_personas or [])
    active_event = None
    keep_agent_group_expanded = False
    expanded_agent_group_key = None
    final_response = None
    confirmed_settings = st.session_state.get("pg_confirmed_settings")
    render_context = base_response is None
    if base_response is not None:
        render_chat_thread(
            base_response,
            include_anchor=False,
            confirmed_settings=confirmed_settings,
        )
    placeholder = st.empty()
    render_streaming_chat_thread(
        placeholder,
        live_messages,
        live_personas,
        active_event,
        base_response=base_response,
        pending_problem=pending_problem,
        confirmed_settings=confirmed_settings,
        keep_agent_group_expanded=keep_agent_group_expanded,
        expanded_agent_group_key=expanded_agent_group_key,
        render_context=render_context,
    )

    for event in events:
        rendered_this_event = False
        event_type = event.get("type")
        if event_type == "personas_ready":
            live_personas = list(event.get("personas", []))
            active_event = None
            keep_agent_group_expanded = False
            expanded_agent_group_key = None
        elif event_type == "agent_started":
            if event.get("stage") in {"critic", "evaluator"}:
                active_event = None
                continue
            active_event = event
            event_group_key = agent_event_group_key(event)
            if event_group_key != expanded_agent_group_key:
                keep_agent_group_expanded = False
                expanded_agent_group_key = None
        elif event_type == "agent_message":
            message = event.get("message")
            if message is not None:
                if message.stage == "persona_generation":
                    active_event = None
                    keep_agent_group_expanded = False
                    expanded_agent_group_key = None
                elif message.stage == "critic":
                    active_event = None
                    keep_agent_group_expanded = False
                    expanded_agent_group_key = None
                elif message.stage == "user":
                    live_messages.append(message)
                    active_event = None
                    keep_agent_group_expanded = False
                    expanded_agent_group_key = None
                else:
                    keep_agent_group_expanded = message.stage in {"specialist", "debate"}
                    expanded_agent_group_key = (
                        agent_message_group_key(message)
                        if keep_agent_group_expanded
                        else None
                    )
                    for frame in live_message_frames(message.content):
                        preview_message_model = message.model_copy(update={"content": frame})
                        render_streaming_chat_thread(
                            placeholder,
                            live_messages,
                            live_personas,
                            None,
                            streaming_message=preview_message_model,
                            base_response=base_response,
                            pending_problem=pending_problem,
                            confirmed_settings=confirmed_settings,
                            keep_agent_group_expanded=keep_agent_group_expanded,
                            expanded_agent_group_key=expanded_agent_group_key,
                            render_context=render_context,
                        )
                        rendered_this_event = True
                        time.sleep(0.025)
                    live_messages.append(message)
                    active_event = None
        elif event_type == "final_response":
            final_response = event.get("response")
            active_event = None
            keep_agent_group_expanded = False
            expanded_agent_group_key = None

        if not rendered_this_event:
            render_streaming_chat_thread(
                placeholder,
                live_messages,
                live_personas,
                active_event,
                base_response=base_response,
                pending_problem=pending_problem,
                confirmed_settings=confirmed_settings,
                keep_agent_group_expanded=keep_agent_group_expanded,
                expanded_agent_group_key=expanded_agent_group_key,
                render_context=render_context,
            )

    return final_response

def agent_message_group_key(message) -> str:
    return agent_group_key(
        {
            "stage": message.stage,
            "round": message.metadata.get("round"),
            "phase": message.metadata.get("phase"),
        }
    )

def agent_event_group_key(event: dict) -> str | None:
    stage = str(event.get("stage", ""))
    if stage not in {"specialist", "debate"}:
        return None
    return agent_group_key(
        {
            "stage": stage,
            "round": event.get("round"),
        }
    )

def run_initial_stream() -> None:
    problem = st.session_state.get("pg_pending_problem")
    if not problem:
        st.session_state["pg_chat_mode"] = "empty"
        st.rerun()

    settings = st.session_state["pg_settings"]
    response = consume_chat_stream(
        solve_problem_stream(
            problem=problem,
            persona_count=int(settings["persona_count"]),
            debate_rounds=int(settings["debate_rounds"]),
            use_llm=bool(settings["use_llm"]),
            model=settings.get("model"),
            temperature=float(settings["temperature"]),
        ),
        pending_problem=problem,
    )
    if response is None:
        st.error("토론 결과를 만들지 못했습니다.")
        st.session_state["pg_chat_mode"] = "configuring"
        return
    stored = save_run(response)
    st.session_state["pg_current_response"] = stored
    st.session_state["pg_current_run_id"] = stored.run_id
    st.session_state["pg_pending_problem"] = None
    st.session_state["pg_chat_mode"] = "completed"

def run_followup_stream() -> None:
    response = st.session_state.get("pg_current_response")
    content = st.session_state.get("pg_pending_followup")
    if response is None or not content:
        st.session_state["pg_chat_mode"] = "completed" if response else "empty"
        st.rerun()

    settings = st.session_state["pg_settings"]
    updated = consume_chat_stream(
        continue_discussion_stream(
            response=response,
            user_content=content,
            max_agents=int(settings["max_reply_agents"]),
            use_llm=bool(settings["use_llm"]),
            model=settings.get("model"),
            temperature=float(settings["temperature"]),
        ),
        base_response=response,
        initial_personas=response.personas,
    )
    if updated is None:
        st.error("이어 말하기 결과를 만들지 못했습니다.")
        st.session_state["pg_chat_mode"] = "completed"
        return
    stored = save_run(updated)
    st.session_state["pg_current_response"] = stored
    st.session_state["pg_current_run_id"] = stored.run_id
    st.session_state["pg_pending_followup"] = None
    st.session_state["pg_chat_mode"] = "completed"
