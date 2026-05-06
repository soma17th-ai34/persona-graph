from __future__ import annotations

import base64
import html
import os
import re
import sys
import time

from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st

from app.characters import CHARACTER_POOL
from app.schemas import SolveResponse
from app.storage import list_runs, load_run, save_run
from app.workflow import continue_discussion_stream, solve_problem_stream


load_dotenv(os.path.join(ROOT_DIR, ".env"))

SAMPLE_PROBLEMS = {
    "Software Maestro 프로젝트 선정": "2026 Software Maestro를 목표로 2주 안에 보여줄 수 있는 AI 프로젝트 MVP를 정해야 한다. 포트폴리오 가치, 데모 안정성, 구현 난이도를 함께 고려해줘.",
    "캠퍼스 팀 프로젝트 리스크": "4명 팀이 3주 안에 AI 기반 학습 도우미를 만들어야 한다. 기능 욕심이 많고 역할 분담이 애매하다. 성공 가능성을 높이는 계획을 제안해줘.",
    "Physical AI 아이디어 검증": "저예산으로 Physical AI 프로젝트를 시작하고 싶다. 하드웨어 구매 전에 시뮬레이션과 소프트웨어 MVP로 검증할 방법을 찾아줘.",
}

STAGE_LABELS = {
    "persona_generation": "페르소나 생성",
    "user": "사용자 의견",
    "moderator": "사회자 진행",
    "specialist": "전문가 의견",
    "debate": "Agent 대화",
    "critic": "비판",
    "synthesizer": "최종 종합",
}

SOURCE_LABELS = {
    "llm": "LLM",
    "fallback": "기본 응답",
    "user": "사용자",
    "unknown": "알 수 없음",
}

HERO_IMAGE_PATH = os.path.join(
    ROOT_DIR, "assets", "hero", "personagraph-agent-network.png"
)
PERSONA_IMAGE_DIR = os.path.join(ROOT_DIR, "assets", "personas")
CHARACTER_IMAGE_PATHS = {
    "nori": os.path.join(PERSONA_IMAGE_DIR, "nori.png"),
    "orbit": os.path.join(PERSONA_IMAGE_DIR, "orbit.png"),
    "milmil": os.path.join(PERSONA_IMAGE_DIR, "milmil.png"),
    "sori": os.path.join(PERSONA_IMAGE_DIR, "sori.png"),
    "mori": os.path.join(PERSONA_IMAGE_DIR, "mori.png"),
    "gyeol": os.path.join(PERSONA_IMAGE_DIR, "gyeol.png"),
    "jari": os.path.join(PERSONA_IMAGE_DIR, "jari.png"),
    "sallycore": os.path.join(PERSONA_IMAGE_DIR, "sallycore.png"),
    "lumi": os.path.join(PERSONA_IMAGE_DIR, "lumi.png"),
    "haneul": os.path.join(PERSONA_IMAGE_DIR, "haneul.png"),
}
CHARACTERS_BY_ID = {character.id: character for character in CHARACTER_POOL}


st.set_page_config(
    page_title="PersonaGraph",
    page_icon="PG",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data(show_spinner=False)
def image_data_uri(path: str) -> str:
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    extension = os.path.splitext(path)[1].lower().lstrip(".") or "png"
    if extension == "jpg":
        extension = "jpeg"
    return f"data:image/{extension};base64,{encoded}"


def render_app_header() -> None:
    if not os.path.exists(HERO_IMAGE_PATH):
        st.title("PersonaGraph")
        st.caption(
            "문제를 입력하면 여러 AI 에이전트가 각자의 페르소나로 토론하고, 비판과 종합을 거쳐 최종 해결안을 만듭니다."
        )
        return

    hero_uri = image_data_uri(HERO_IMAGE_PATH)
    st.markdown(
        f"""
<style>
.pg-hero {{
    min-height: 8.4rem;
    border-radius: 8px;
    padding: clamp(1rem, 2.4vw, 1.55rem);
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    background-image:
        linear-gradient(90deg, rgba(255, 255, 255, 0.98) 0%, rgba(255, 255, 255, 0.91) 52%, rgba(255, 255, 255, 0.34) 100%),
        url("{hero_uri}");
    background-size: cover;
    background-position: center;
    border: 1px solid rgba(62, 72, 88, 0.08);
}}
.pg-hero-content {{
    max-width: 44rem;
}}
.pg-hero-kicker {{
    color: #2f80ed;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0;
    margin-bottom: 0.4rem;
}}
.pg-hero h1 {{
    color: #1f2937;
    font-size: clamp(1.8rem, 3vw, 2.7rem);
    line-height: 1;
    margin: 0 0 0.45rem 0;
    letter-spacing: 0;
}}
.pg-hero p {{
    color: #374151;
    font-size: 0.95rem;
    line-height: 1.5;
    max-width: 38rem;
    margin: 0;
}}
.pg-flow {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.42rem;
    margin-top: 0.82rem;
}}
.pg-flow-step {{
    display: inline-flex;
    align-items: center;
    min-height: 1.7rem;
    border-radius: 999px;
    padding: 0.18rem 0.58rem;
    background: rgba(255, 255, 255, 0.76);
    border: 1px solid rgba(47, 128, 237, 0.16);
    color: #334155;
    font-size: 0.78rem;
    font-weight: 700;
}}
.pg-network {{
    border: 1px solid rgba(47, 128, 237, 0.14);
    border-radius: 8px;
    background: #fbfcfd;
    padding: 0.9rem;
    margin: 0.4rem 0 1.4rem 0;
}}
.pg-network-row {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem;
}}
.pg-agent-node {{
    display: flex;
    align-items: center;
    gap: 0.55rem;
    min-width: 11rem;
    max-width: 15rem;
    padding: 0.5rem 0.62rem;
    border-radius: 8px;
    border: 1px solid rgba(31, 41, 55, 0.08);
    background: rgba(255, 255, 255, 0.86);
    color: inherit;
    text-decoration: none;
    transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
}}
.pg-agent-node:hover {{
    border-color: rgba(47, 128, 237, 0.42);
    box-shadow: 0 8px 20px rgba(31, 41, 55, 0.08);
    transform: translateY(-1px);
    text-decoration: none;
}}
.pg-agent-node-selected {{
    border-color: rgba(47, 128, 237, 0.68);
    box-shadow: 0 0 0 2px rgba(47, 128, 237, 0.12);
}}
.pg-agent-node img {{
    width: 3.2rem;
    height: 4.7rem;
    border-radius: 10px;
    object-fit: contain;
    background: #f8f5ef;
    flex: 0 0 auto;
}}
.pg-card-image {{
    width: 3.4rem;
    height: 4.35rem;
    border-radius: 10px;
    object-fit: contain;
    background: #f8f5ef;
    border: 1px solid rgba(31, 41, 55, 0.08);
    display: block;
}}
.pg-chat-avatar {{
    width: 2.6rem;
    height: 3.35rem;
    border-radius: 9px;
    object-fit: contain;
    background: #f8f5ef;
    border: 1px solid rgba(31, 41, 55, 0.08);
    display: block;
}}
.pg-start-panel {{
    border: 1px solid rgba(47, 128, 237, 0.18);
    border-radius: 8px;
    background: #fbfcff;
    padding: 1rem;
    margin: 0.8rem 0 1rem 0;
}}
.pg-start-panel strong {{
    color: #111827;
}}
.pg-start-panel p {{
    color: #4b5563;
    margin: 0.35rem 0 0 0;
    line-height: 1.5;
}}
.pg-round-brief {{
    border: 1px solid rgba(31, 41, 55, 0.10);
    border-radius: 8px;
    background: #fbfcfd;
    padding: 0.85rem 0.95rem;
    margin: 0.6rem 0 0.85rem 0;
}}
.pg-round-title {{
    color: #111827;
    font-size: 1rem;
    font-weight: 800;
    margin-bottom: 0.25rem;
}}
.pg-round-meta {{
    color: #4b5563;
    font-size: 0.84rem;
    line-height: 1.45;
}}
.pg-speaker-line {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-bottom: 0.32rem;
}}
.pg-speaker-chip {{
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.16rem 0.52rem;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 0.78rem;
    font-weight: 700;
}}
.pg-speaker-chip-user {{
    background: #fff3ed;
    color: #c2410c;
}}
.pg-speaker-chip-summary {{
    background: #eefdf3;
    color: #15803d;
}}
.pg-message-preview {{
    color: #111827;
    font-size: 0.95rem;
    line-height: 1.55;
    margin: 0.42rem 0 0.12rem 0;
}}
.pg-message-roleline {{
    color: #6b7280;
    font-size: 0.82rem;
    line-height: 1.45;
    margin-top: 0.12rem;
}}
.pg-roster-card {{
    min-height: 8.2rem;
}}
.pg-roster-name {{
    color: #111827;
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.35;
    margin-bottom: 0.18rem;
    word-break: keep-all;
    overflow-wrap: anywhere;
}}
.pg-roster-role {{
    display: inline-flex;
    align-items: center;
    max-width: 100%;
    border-radius: 999px;
    padding: 0.16rem 0.54rem;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1.35;
    word-break: keep-all;
}}
.pg-roster-summary {{
    color: #4b5563;
    font-size: 0.82rem;
    line-height: 1.45;
    margin-top: 0.42rem;
}}
.pg-roster-selected {{
    color: #15803d;
    font-size: 0.78rem;
    font-weight: 800;
    margin-top: 0.34rem;
}}
.pg-followup-panel {{
    border: 1px solid rgba(47, 128, 237, 0.18);
    border-radius: 8px;
    background: #fbfcff;
    padding: 0.9rem 1rem;
    margin: 0.6rem 0 1rem 0;
}}
.pg-followup-title {{
    color: #111827;
    font-size: 0.98rem;
    font-weight: 800;
    line-height: 1.35;
}}
.pg-followup-meta {{
    color: #4b5563;
    font-size: 0.84rem;
    line-height: 1.45;
    margin-top: 0.18rem;
}}
.pg-live-head {{
    border: 1px solid rgba(47, 128, 237, 0.18);
    border-radius: 8px;
    background: #fbfcff;
    padding: 0.85rem 0.95rem;
    margin: 0.7rem 0 0.8rem 0;
}}
.pg-live-title {{
    color: #111827;
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.35;
}}
.pg-live-meta {{
    color: #4b5563;
    font-size: 0.84rem;
    line-height: 1.45;
    margin-top: 0.18rem;
}}
.pg-typing-text {{
    color: #2563eb;
    font-size: 0.92rem;
    font-weight: 800;
    line-height: 1.45;
}}
.pg-typing-dots {{
    color: #6b7280;
    font-size: 0.82rem;
    line-height: 1.45;
    margin-top: 0.18rem;
}}
.pg-live-roster-label {{
    color: #111827;
    font-size: 0.92rem;
    font-weight: 800;
    line-height: 1.35;
    margin: 0.15rem 0 0.45rem 0;
}}
.pg-live-roster {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    gap: 0.55rem;
    margin: 0 0 0.85rem 0;
}}
.pg-live-persona {{
    display: flex;
    gap: 0.55rem;
    align-items: flex-start;
    border: 1px solid rgba(31, 41, 55, 0.08);
    border-radius: 8px;
    background: #ffffff;
    padding: 0.55rem;
}}
.pg-live-persona img {{
    width: 2.4rem;
    height: 3.25rem;
    border-radius: 8px;
    object-fit: contain;
    background: #f8f5ef;
    flex: 0 0 auto;
}}
.pg-live-persona-name {{
    color: #111827;
    font-size: 0.86rem;
    font-weight: 800;
    line-height: 1.25;
    word-break: keep-all;
    overflow-wrap: anywhere;
}}
.pg-live-persona-role {{
    color: #2563eb;
    font-size: 0.75rem;
    font-weight: 700;
    line-height: 1.35;
    margin-top: 0.08rem;
}}
.pg-live-persona-summary {{
    color: #4b5563;
    font-size: 0.75rem;
    line-height: 1.35;
    margin-top: 0.2rem;
}}
.pg-live-stream-label {{
    color: #111827;
    font-size: 0.92rem;
    font-weight: 800;
    line-height: 1.35;
    margin: 0.5rem 0 0.45rem 0;
    padding-top: 0.65rem;
    border-top: 1px solid rgba(31, 41, 55, 0.08);
}}
.pg-live-stream-empty {{
    color: #6b7280;
    font-size: 0.84rem;
    line-height: 1.45;
    margin: 0.25rem 0 0.65rem 0;
}}
.pg-live-status {{
    border: 1px dashed rgba(47, 128, 237, 0.28);
    border-radius: 8px;
    background: #f8fbff;
    padding: 0.75rem 0.85rem;
    margin: 0.45rem 0 0.85rem 0;
}}
.pg-live-status strong {{
    color: #1d4ed8;
}}
.pg-topic-card {{
    border: 1px solid rgba(31, 41, 55, 0.10);
    border-radius: 8px;
    background: #fbfcfd;
    padding: 0.8rem 0.95rem;
    margin: 0.4rem 0 0.9rem 0;
}}
.pg-topic-label {{
    color: #2563eb;
    font-size: 0.78rem;
    font-weight: 800;
    margin-bottom: 0.18rem;
}}
.pg-topic-text {{
    color: #111827;
    font-size: 0.95rem;
    line-height: 1.45;
}}
div[data-testid="stAppViewContainer"] .main .block-container {{
    padding-bottom: 4rem;
}}
.pg-agent-name {{
    color: #111827;
    font-size: 0.9rem;
    font-weight: 700;
    line-height: 1.25;
}}
.pg-agent-role {{
    color: #4b5563;
    font-size: 0.76rem;
    line-height: 1.3;
    margin-top: 0.16rem;
}}
.pg-connector {{
    width: 2.3rem;
    height: 1px;
    background: linear-gradient(90deg, rgba(47, 128, 237, 0.25), rgba(244, 143, 116, 0.72));
    position: relative;
}}
.pg-connector:after {{
    content: "";
    position: absolute;
    right: -0.05rem;
    top: -0.18rem;
    width: 0.38rem;
    height: 0.38rem;
    border-radius: 999px;
    background: #f48f74;
}}
.pg-native-connector {{
    height: 1px;
    margin-top: 3rem;
    background: linear-gradient(90deg, rgba(47, 128, 237, 0.25), rgba(244, 143, 116, 0.72));
}}
.pg-native-connector:after {{
    content: "";
    display: block;
    width: 0.38rem;
    height: 0.38rem;
    margin-left: auto;
    margin-top: -0.18rem;
    border-radius: 999px;
    background: #f48f74;
}}
.pg-portrait {{
    width: 7rem;
    height: 10.6rem;
    border-radius: 14px;
    object-fit: contain;
    background: #f8f5ef;
    border: 1px solid rgba(31, 41, 55, 0.10);
    box-shadow: 0 10px 24px rgba(31, 41, 55, 0.10);
}}
@media (max-width: 640px) {{
    .pg-hero {{
        min-height: 7rem;
        background-position: 58% center;
    }}
    .pg-flow-step {{
        font-size: 0.74rem;
    }}
    .pg-agent-node {{
        min-width: 100%;
    }}
    .pg-connector {{
        display: none;
    }}
}}
</style>
<section class="pg-hero">
  <div class="pg-hero-content">
    <div class="pg-hero-kicker">multi-agent persona debate</div>
    <h1>PersonaGraph</h1>
    <p>문제를 입력하면 여러 AI 에이전트가 각자의 페르소나로 토론하고, 비판과 종합을 거쳐 최종 해결안을 만듭니다.</p>
    <div class="pg-flow" aria-label="PersonaGraph flow">
      <span class="pg-flow-step">문제 입력</span>
      <span class="pg-flow-step">페르소나 토론</span>
      <span class="pg-flow-step">비판 검토</span>
      <span class="pg-flow-step">결론 평가</span>
    </div>
  </div>
</section>
""",
        unsafe_allow_html=True,
    )


def render_response(
    response: SolveResponse,
    view_key: str,
    max_reply_agents: int | None = None,
    use_llm: bool = True,
    model: str | None = None,
    temperature: float = 0.35,
    input_key_prefix: str | None = None,
) -> None:
    render_topic_context(response)
    status = "LLM API 사용" if response.used_llm else "로컬 폴백 사용"
    st.caption(f"상태: 토론 완료 · 응답 방식: {status}")
    with st.expander("실행 정보 보기", expanded=False):
        st.markdown(f"- model: `{response.model}`")
        if response.run_id:
            st.markdown(f"- run_id: `{response.run_id}`")
        st.markdown(f"- 사용한 응답 방식: `{status}`")

    render_conversation_room(response)

    with st.expander("Agent 상세 정보", expanded=False):
        selected_agent_id = selected_network_agent_id(response.personas, view_key)
        selected_agent_id = render_agent_network(response.personas, selected_agent_id, view_key)
        render_selected_agent_info(response.personas, selected_agent_id)

    st.divider()
    if max_reply_agents is not None:
        render_discussion_input(
            response=response,
            max_agents=max_reply_agents,
            use_llm=use_llm,
            model=model,
            temperature=temperature,
            key_prefix=input_key_prefix or view_key,
        )

def render_topic_context(response: SolveResponse) -> None:
    st.markdown(
        f"""
<div class="pg-topic-card">
  <div class="pg-topic-label">토론 주제</div>
  <div class="pg-topic-text">{html.escape(trim_summary(response.problem, 220))}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_conversation_room(response: SolveResponse) -> None:
    messages = conversation_room_messages(response.messages)
    st.markdown(
        f"""
<div class="pg-live-head">
  <div class="pg-live-title">대화창</div>
  <div class="pg-live-meta">토론이 끝나도 이 대화창에 전체 흐름이 유지됩니다. 현재 {len(messages)}개 발화가 남아 있습니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    render_live_persona_roster(response.personas)
    st.markdown('<div class="pg-live-stream-label">발화 스트림</div>', unsafe_allow_html=True)

    if not messages:
        st.markdown(
            '<div class="pg-live-stream-empty">아직 표시할 대화가 없습니다.</div>',
            unsafe_allow_html=True,
        )
        return

    personas_by_id = {persona.id: persona for persona in response.personas}
    for message in messages:
        render_live_chat_message(message, personas_by_id)


def conversation_room_messages(messages) -> list:
    return [
        message
        for message in messages
        if message.stage != "persona_generation"
    ]


def render_message_timeline(response: SolveResponse, key_prefix: str) -> None:
    personas_by_id = {persona.id: persona for persona in response.personas}
    chat_rounds = build_chat_rounds(response.messages)

    if not chat_rounds:
        st.info("아직 표시할 대화가 없습니다.")
        return

    st.markdown("#### 대화 라운드")
    selected_label = st.radio(
        "보고 싶은 라운드를 선택하세요",
        [chat_round["label"] for chat_round in chat_rounds],
        index=default_round_index(chat_rounds),
        horizontal=True,
        key=f"{key_prefix}_round_radio",
    )
    selected_round = next(
        chat_round for chat_round in chat_rounds if chat_round["label"] == selected_label
    )

    responders = html.escape(round_responders(selected_round["messages"]))
    st.markdown(
        f"""
<div class="pg-round-brief">
  <div class="pg-round-title">현재 라운드: {html.escape(selected_round['label'])}</div>
  <div class="pg-round-meta">
    {html.escape(selected_round['caption'])}<br>
    이번 라운드 발언 Agent: {responders}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    for message in selected_round["messages"]:
        render_chat_message(message, personas_by_id)

    render_supporting_logs(response.messages)

    fallback_errors = [
        message.metadata.get("error")
        for message in response.messages
        if message.metadata.get("source") == "fallback" and message.metadata.get("error")
    ]
    if fallback_errors:
        st.caption(f"기본 응답 사용 이유: {fallback_errors[0]}")


def build_chat_rounds(messages) -> list[dict]:
    rounds: list[dict] = []

    def ensure_round(round_key: tuple[str, int]) -> dict:
        for chat_round in rounds:
            if chat_round["key"] == round_key:
                return chat_round
        kind, source_round = round_key
        chat_round = {
            "key": round_key,
            "kind": kind,
            "source_round": source_round,
            "raw_messages": [],
        }
        rounds.append(chat_round)
        return chat_round

    for message in messages:
        round_key = message_round_key(message)
        if round_key is None:
            continue
        ensure_round(round_key)["raw_messages"].append(message)

    rounds.sort(key=lambda chat_round: round_sort_key(chat_round["key"]))
    for display_number, chat_round in enumerate(rounds, start=1):
        raw_messages = chat_round["raw_messages"]
        chat_round["messages"] = compact_round_messages(raw_messages)
        chat_round["label"] = round_label(
            display_number,
            raw_messages,
            chat_round["kind"],
        )
        chat_round["caption"] = round_caption(
            chat_round["messages"],
            raw_messages,
            chat_round["kind"],
        )
    return rounds


def message_round_key(message) -> tuple[str, int] | None:
    if message.stage == "specialist":
        return ("initial", 0)
    if message.stage == "user":
        return ("user", safe_round_value(message.metadata.get("round"), default=1))
    if message.stage == "debate" and message.metadata.get("phase") == "user_response":
        return ("user", safe_round_value(message.metadata.get("round"), default=1))
    if message.stage == "synthesizer" and message.metadata.get("phase") == "followup_synthesis":
        return ("user", safe_round_value(message.metadata.get("round"), default=1))
    if message.stage == "debate":
        return ("debate", safe_round_value(message.metadata.get("round"), default=1))
    return None


def safe_round_value(value, default: int) -> int:
    return int(value) if str(value).isdigit() else default


def round_sort_key(round_key: tuple[str, int]) -> tuple[int, int]:
    kind, source_round = round_key
    order = {
        "initial": 0,
        "debate": 1,
        "user": 2,
    }.get(kind, 9)
    return (order, source_round)


def default_round_index(chat_rounds: list[dict]) -> int:
    if any(chat_round["kind"] == "user" for chat_round in chat_rounds):
        return len(chat_rounds) - 1
    return 0


def round_label(round_number: int, raw_messages, kind: str) -> str:
    if kind == "initial":
        return f"{round_number}라운드 · 첫 의견"
    if kind == "user":
        return f"{round_number}라운드 · 사용자 의견 반영"
    return f"{round_number}라운드 · Agent 이어 말하기"


def compact_round_messages(messages) -> list:
    user_messages = [message for message in messages if message.stage == "user"]
    synthesis_messages = [message for message in messages if message.stage == "synthesizer"]
    agent_order: list[str] = []
    latest_agent_message = {}

    for message in messages:
        if message.stage not in {"specialist", "debate"}:
            continue
        if message.agent_id not in agent_order:
            agent_order.append(message.agent_id)
        latest_agent_message[message.agent_id] = message

    compacted = [*user_messages]
    compacted.extend(
        latest_agent_message[agent_id]
        for agent_id in agent_order
        if agent_id in latest_agent_message
    )
    if synthesis_messages:
        compacted.append(synthesis_messages[-1])
    return compacted


def round_caption(messages, raw_messages, kind: str) -> str:
    agent_count = len(
        {
            message.agent_id
            for message in messages
            if message.stage in {"specialist", "debate"}
        }
    )
    hidden_count = max(0, len(raw_messages) - len(messages))
    if kind == "initial":
        caption = f"Agent {agent_count}명 첫 의견 · {len(messages)}개 핵심 발언"
    elif kind == "user":
        caption = f"사용자 의견 포함 · Agent {agent_count}명 응답 · {len(messages)}개 핵심 발언"
    else:
        caption = f"Agent {agent_count}명 이어 말함 · {len(messages)}개 핵심 발언"
    if hidden_count:
        caption = f"{caption} · 이전 발언 {hidden_count}개 압축"
    return caption


def round_responders(messages) -> str:
    responder_names: list[str] = []
    for message in messages:
        if message.stage not in {"specialist", "debate"}:
            continue
        if message.agent_name not in responder_names:
            responder_names.append(message.agent_name)
    if not responder_names:
        return "응답 Agent 없음"
    return ", ".join(responder_names)


def render_chat_message(message, personas_by_id) -> None:
    persona = personas_by_id.get(message.agent_id)
    character = (
        CHARACTERS_BY_ID.get(persona.character.id, persona.character)
        if persona and persona.character
        else None
    )
    avatar = message_avatar(message, character)
    stage_label = chat_stage_label(message)
    meta_label = message_meta_label(message, stage_label)
    preview = preview_message(message.content)
    role_line = message_role_line(message)

    with st.container(border=True):
        avatar_col, content_col = st.columns([0.12, 0.88], gap="small")
        with avatar_col:
            if avatar:
                render_local_image(avatar, message.agent_name, "pg-chat-avatar")
            else:
                st.markdown(f"**{message_avatar_text(message)}**")
        with content_col:
            chip_class = message_chip_class(message)
            st.markdown(
                f"""
<div class="pg-speaker-line">
  <span class="{chip_class}">{html.escape(message.agent_name)}</span>
  <span class="pg-round-meta">{html.escape(meta_label)}</span>
</div>
<div class="pg-message-preview">{html.escape(preview)}</div>
{f'<div class="pg-message-roleline">{html.escape(role_line)}</div>' if role_line else ''}
""",
                unsafe_allow_html=True,
            )
            with st.expander("전체 발언 보기", expanded=False):
                render_message_content(message.content)


def message_chip_class(message) -> str:
    if message.stage == "user":
        return "pg-speaker-chip pg-speaker-chip-user"
    if message.stage == "synthesizer":
        return "pg-speaker-chip pg-speaker-chip-summary"
    return "pg-speaker-chip"


def chat_stage_label(message) -> str:
    if message.stage == "specialist":
        return "첫 의견"
    if message.stage == "debate" and message.metadata.get("phase") == "user_response":
        return "Agent 답변"
    if message.stage == "synthesizer" and message.metadata.get("phase") == "followup_synthesis":
        return "중간 정리"
    if message.stage == "debate":
        return "Agent 대화"
    if message.stage == "user":
        return "내 의견"
    return STAGE_LABELS.get(message.stage, message.stage)


def message_meta_label(message, stage_label: str) -> str:
    source = message.metadata.get("source", "unknown")
    if message.stage == "user":
        return stage_label
    if source == "fallback":
        return f"{stage_label} · 기본 응답"
    return stage_label


def message_role_line(message) -> str:
    if message.stage == "user":
        return ""
    if message.stage == "synthesizer":
        return "현재까지의 흐름을 반영한 정리"
    if not message.role:
        return ""
    return f"관점 · {trim_summary(message.role, 80)}"


def render_supporting_logs(messages) -> None:
    log_messages = [
        message
        for message in messages
        if message.stage in {"persona_generation", "moderator", "critic"}
    ]
    if not log_messages:
        return

    with st.expander("진행/검토 로그", expanded=False):
        for message in log_messages:
            source = message.metadata.get("source", "unknown")
            source_label = SOURCE_LABELS.get(source, source)
            st.markdown(f"**{message.agent_name}**")
            st.caption(f"{STAGE_LABELS.get(message.stage, message.stage)} · {source_label}")
            st.markdown(f"- {html.escape(summarize_message(message.content, 110))}", unsafe_allow_html=True)


def message_section_label(message) -> str:
    if message.stage == "persona_generation":
        return "준비 단계"
    if message.stage == "user":
        round_value = message.metadata.get("round")
        return f"{round_value}라운드 사용자 개입" if round_value else "사용자 개입"
    if message.stage == "moderator" and message.metadata.get("phase") == "opening":
        return "오프닝"
    if message.stage == "specialist":
        return "첫 의견"
    if message.stage == "debate" and message.metadata.get("phase") == "user_response":
        round_value = message.metadata.get("round")
        return f"{round_value}라운드 Agent 응답" if round_value else "Agent 응답"
    if message.stage == "synthesizer" and message.metadata.get("phase") == "followup_synthesis":
        round_value = message.metadata.get("round")
        return f"{round_value}라운드 중간 종합" if round_value else "중간 종합"
    if message.stage in {"moderator", "debate"} and message.metadata.get("round"):
        return f"{message.metadata['round']}라운드 Agent 대화"
    if message.stage == "critic":
        return "비판 검토"
    if message.stage == "synthesizer":
        return "최종 종합"
    return STAGE_LABELS.get(message.stage, message.stage)


def message_avatar(message, character) -> str | None:
    if character:
        image_path = CHARACTER_IMAGE_PATHS.get(character.id)
        if image_path and os.path.exists(image_path):
            return image_path
    return None


def message_avatar_text(message) -> str:
    return {
        "persona_generation": "PG",
        "user": "나",
        "moderator": "MOD",
        "critic": "CR",
        "synthesizer": "FIN",
    }.get(message.stage, message.agent_name[:2].upper())


def preview_message(content: str, max_length: int = 180) -> str:
    lines = [normalize_summary_text(line) for line in content.splitlines() if line.strip()]
    preview_lines: list[str] = []
    for line in lines:
        if not line or is_structural_heading(line):
            continue
        preview_lines.append(line)
        if len(" ".join(preview_lines)) >= max_length * 0.7 or len(preview_lines) >= 2:
            break

    preview = " ".join(preview_lines) or normalize_summary_text(content)
    return trim_summary(preview, max_length)


def summarize_message(content: str, max_length: int = 115) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    for line in lines:
        summary = normalize_summary_text(line)
        if summary and not is_structural_heading(summary):
            return trim_summary(summary, max_length)
    return trim_summary(normalize_summary_text(content), max_length)


def normalize_summary_text(text: str) -> str:
    cleaned = re.sub(r"\*\*([^*]+?)\*\*", r"\1", text)
    cleaned = re.sub(r"^[-*]\s+", "", cleaned)
    cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned)
    cleaned = re.sub(r"^(요약|정리)\s*[:：]\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def is_structural_heading(text: str) -> bool:
    headings = {
        "핵심 판단",
        "근거",
        "실행 제안",
        "주의할 점",
        "모순 또는 충돌",
        "약한 가정",
        "누락된 관점",
        "최종 통합 전에 고쳐야 할 점",
        "최종 결론",
        "선택한 방향",
        "실행 단계",
        "리스크와 대응",
        "다음 24시간 액션",
    }
    return text in headings


def trim_summary(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1].rstrip()}..."


def format_run_label(summary) -> str:
    preview = trim_summary(normalize_summary_text(summary.problem_preview), 80)
    created_at = summary.created_at.strftime("%Y-%m-%d %H:%M:%S")
    return f"{created_at} · {summary.average_score}/5 · {preview}"


def render_local_image(path: str, alt: str, css_class: str) -> None:
    st.markdown(
        f'<img class="{css_class}" src="{image_data_uri(path)}" alt="{html.escape(alt)}">',
        unsafe_allow_html=True,
    )


def render_message_content(content: str) -> None:
    safe_content = html.escape(content)
    safe_content = re.sub(r"\*\*([^*\n]+?)\*\*", r"<strong>\1</strong>", safe_content)
    st.markdown(safe_content, unsafe_allow_html=True)


def consume_live_stream(events, initial_personas=None) -> SolveResponse | None:
    live_messages = []
    live_personas = list(initial_personas or [])
    active_event = None
    final_response = None
    placeholder = st.empty()

    render_live_stream_panel(placeholder, live_messages, live_personas, active_event)
    for event in events:
        event_type = event.get("type")
        if event_type == "personas_ready":
            live_personas = list(event.get("personas", []))
            active_event = None
        elif event_type == "agent_started":
            active_event = event
        elif event_type == "agent_message":
            message = event.get("message")
            if message is not None:
                if message.stage != "persona_generation":
                    for frame in live_message_frames(message.content):
                        preview_message_model = message.model_copy(
                            update={"content": frame}
                        )
                        render_live_stream_panel(
                            placeholder,
                            live_messages,
                            live_personas,
                            None,
                            streaming_message=preview_message_model,
                        )
                        time.sleep(0.025)
                    live_messages.append(message)
            active_event = None
        elif event_type == "final_response":
            final_response = event.get("response")
            active_event = None

        render_live_stream_panel(placeholder, live_messages, live_personas, active_event)

    placeholder.empty()
    return final_response


def render_live_stream_panel(
    placeholder,
    messages,
    personas,
    active_event,
    streaming_message=None,
) -> None:
    placeholder.empty()
    with placeholder.container():
        visible_count = len(messages) + (1 if streaming_message is not None else 0)
        meta = live_panel_meta(personas, visible_count, active_event, streaming_message)
        st.markdown(
            f"""
<div class="pg-live-head">
  <div class="pg-live-title">라이브 토론</div>
  <div class="pg-live-meta">{html.escape(meta)}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        personas_by_id = {persona.id: persona for persona in personas}
        if personas:
            render_live_persona_roster(personas)
        elif active_event is not None and active_event.get("stage") == "persona_generation":
            render_live_setup_status("페르소나를 구성하고 있습니다.")

        st.markdown('<div class="pg-live-stream-label">발화 스트림</div>', unsafe_allow_html=True)
        if not messages and streaming_message is None and active_event is None:
            st.markdown(
                '<div class="pg-live-stream-empty">페르소나 준비가 끝나면 첫 발화가 이어집니다.</div>',
                unsafe_allow_html=True,
            )
        for message in messages:
            render_live_chat_message(message, personas_by_id)
        if streaming_message is not None:
            render_live_chat_message(streaming_message, personas_by_id, is_streaming=True)
        if active_event is not None:
            if active_event.get("stage") == "persona_generation":
                return
            render_typing_indicator(active_event, personas_by_id)


def live_panel_meta(personas, visible_count: int, active_event, streaming_message) -> str:
    if not personas:
        return "먼저 토론에 참여할 페르소나를 만들고 있습니다."
    if streaming_message is not None:
        return f"{streaming_message.agent_name}의 발화가 실시간으로 올라오는 중입니다."
    if active_event is not None:
        return f"{active_event.get('agent_name', 'Agent')}가 다음 발화를 준비하고 있습니다."
    if visible_count == 0:
        return "페르소나 준비 완료. 곧 첫 발화가 시작됩니다."
    return f"페르소나 {len(personas)}명 · 현재 {visible_count}개 발화가 이어졌습니다."


def render_live_setup_status(label: str) -> None:
    st.markdown(
        f"""
<div class="pg-live-status">
  <strong>{html.escape(label)}</strong>
  <div class="pg-typing-dots">토론방에 들어올 Agent들의 역할과 관점을 정리하는 중입니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_live_persona_roster(personas) -> None:
    cards = []
    for persona in personas:
        character = (
            CHARACTERS_BY_ID.get(persona.character.id, persona.character)
            if persona.character
            else None
        )
        image_markup = live_persona_image_markup(persona, character)
        role = character.archetype if character else persona.role
        summary = trim_summary(persona.perspective or persona.role, 78)
        cards.append(
            f"""
<div class="pg-live-persona">
  {image_markup}
  <div>
    <div class="pg-live-persona-name">{html.escape(persona.name)}</div>
    <div class="pg-live-persona-role">{html.escape(role)}</div>
    <div class="pg-live-persona-summary">{html.escape(summary)}</div>
  </div>
</div>
"""
        )

    st.markdown(
        f"""
<div class="pg-live-roster-label">오늘의 페르소나</div>
<div class="pg-live-roster">{''.join(cards)}</div>
""",
        unsafe_allow_html=True,
    )


def live_persona_image_markup(persona, character) -> str:
    if character:
        image_path = CHARACTER_IMAGE_PATHS.get(character.id)
        if image_path and os.path.exists(image_path):
            return (
                f'<img src="{image_data_uri(image_path)}" '
                f'alt="{html.escape(persona.name)}">'
            )
    initials = html.escape(persona.name[:2])
    return (
        '<div class="pg-card-image" '
        'style="width:2.4rem;height:3.25rem;display:flex;align-items:center;'
        'justify-content:center;font-size:0.82rem;font-weight:800;color:#1d4ed8;">'
        f"{initials}</div>"
    )


def render_live_chat_message(message, personas_by_id, is_streaming: bool = False) -> None:
    persona = personas_by_id.get(message.agent_id)
    character = (
        CHARACTERS_BY_ID.get(persona.character.id, persona.character)
        if persona and persona.character
        else None
    )
    avatar = message_avatar(message, character)
    meta_label = message_meta_label(message, chat_stage_label(message))

    with st.container(border=True):
        avatar_col, content_col = st.columns([0.12, 0.88], gap="small")
        with avatar_col:
            if avatar:
                render_local_image(avatar, message.agent_name, "pg-chat-avatar")
            else:
                st.markdown(f"**{message_avatar_text(message)}**")
        with content_col:
            st.markdown(
                f"""
<div class="pg-speaker-line">
  <span class="{message_chip_class(message)}">{html.escape(message.agent_name)}</span>
  <span class="pg-round-meta">{html.escape(meta_label)}</span>
</div>
""",
                unsafe_allow_html=True,
            )
            content = f"{message.content} |" if is_streaming else message.content
            render_message_content(content)


def live_message_frames(content: str) -> list[str]:
    content = content.strip()
    if not content:
        return [""]

    if len(content) <= 70:
        return [content]

    frame_count = min(8, max(2, len(content) // 140))
    step = max(70, len(content) // frame_count)
    frames: list[str] = []
    cursor = step
    while cursor < len(content):
        boundary = max(
            content.rfind("\n", 0, cursor),
            content.rfind(". ", 0, cursor),
            content.rfind("다.", 0, cursor),
            content.rfind("요.", 0, cursor),
            content.rfind(" ", 0, cursor),
        )
        previous_length = len(frames[-1]) if frames else 0
        if boundary > previous_length + 35:
            cursor = sentence_boundary_end(content, boundary)
        frame = content[:cursor].rstrip()
        if not frames or frame != frames[-1]:
            frames.append(frame)
        cursor += step

    if not frames or frames[-1] != content:
        frames.append(content)
    return frames


def sentence_boundary_end(content: str, boundary: int) -> int:
    for marker in ("다.", "요.", ". "):
        if content.startswith(marker, boundary):
            return boundary + len(marker)
    return boundary + 1


def render_typing_indicator(event, personas_by_id) -> None:
    agent_id = str(event.get("agent_id", ""))
    agent_name = str(event.get("agent_name", "Agent"))
    stage = str(event.get("stage", "unknown"))
    persona = personas_by_id.get(agent_id)
    character = (
        CHARACTERS_BY_ID.get(persona.character.id, persona.character)
        if persona and persona.character
        else None
    )
    avatar = None
    if character:
        image_path = CHARACTER_IMAGE_PATHS.get(character.id)
        if image_path and os.path.exists(image_path):
            avatar = image_path

    with st.container(border=True):
        avatar_col, content_col = st.columns([0.12, 0.88], gap="small")
        with avatar_col:
            if avatar:
                render_local_image(avatar, agent_name, "pg-chat-avatar")
            else:
                st.markdown(f"**{agent_avatar_text(agent_id, agent_name, stage)}**")
        with content_col:
            st.markdown(
                f"""
<div class="pg-speaker-line">
  <span class="pg-speaker-chip">{html.escape(agent_name)}</span>
  <span class="pg-round-meta">{html.escape(STAGE_LABELS.get(stage, stage))}</span>
</div>
<div class="pg-typing-text">입력 중...</div>
<div class="pg-typing-dots">생각을 정리하고 있습니다.</div>
""",
                unsafe_allow_html=True,
            )


def agent_avatar_text(agent_id: str, agent_name: str, stage: str) -> str:
    return {
        "persona_generator": "PG",
        "moderator": "MOD",
        "critic": "CR",
        "synthesizer": "FIN",
        "evaluator": "EV",
    }.get(agent_id, agent_name[:2].upper() if agent_name else stage[:2].upper())


def render_discussion_input(
    response: SolveResponse,
    max_agents: int,
    use_llm: bool,
    model: str | None,
    temperature: float,
    key_prefix: str,
) -> None:
    if not response.run_id:
        return

    st.markdown(
        f"""
<div class="pg-followup-panel">
  <div class="pg-followup-title">의견 추가</div>
  <div class="pg-followup-meta">현재 대화방 Agent 중 최대 {max_agents}명이 이어서 답하고, 결론이 다시 갱신됩니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    with st.form(key=f"{key_prefix}_followup_form"):
        prompt = st.text_area(
            "이 라운드에 추가할 의견",
            key=f"{key_prefix}_followup_text",
            height=96,
            placeholder="예: 나는 비용보다 발표 임팩트가 더 중요하다고 봐.",
        )
        submitted = st.form_submit_button(
            "이 의견으로 이어 말하기",
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return

    content = prompt.strip()
    if not content:
        st.warning("의견을 한 글자 이상 입력해주세요.")
        return

    updated = consume_live_stream(
        continue_discussion_stream(
            response=response,
            user_content=content,
            max_agents=max_agents,
            use_llm=use_llm,
            model=model,
            temperature=temperature,
        ),
        initial_personas=response.personas,
    )
    if updated is None:
        st.error("이어 말하기 결과를 만들지 못했습니다.")
        return

    updated = save_run(updated)

    st.session_state["last_response"] = updated
    st.rerun()


def render_start_cta() -> None:
    st.markdown(
        """
<div class="pg-start-panel">
  <strong>바로 시작하기</strong>
  <p>아래 샘플 중 하나를 입력창에 채우거나, 직접 문제를 적은 뒤 Agent 토론을 시작하세요.</p>
</div>
""",
        unsafe_allow_html=True,
    )
    columns = st.columns(len(SAMPLE_PROBLEMS), gap="small")
    for index, (sample_name, sample_problem) in enumerate(SAMPLE_PROBLEMS.items()):
        with columns[index]:
            if st.button(
                f"{sample_name} 채우기",
                key=f"quick_sample_{index}",
                use_container_width=True,
            ):
                st.session_state["problem_text"] = sample_problem
                st.session_state.pop("last_response", None)
                st.rerun()


def render_character(character) -> None:
    display_character = CHARACTERS_BY_ID.get(character.id, character)
    image_path = CHARACTER_IMAGE_PATHS.get(display_character.id)

    if image_path and os.path.exists(image_path):
        image_col, detail_col = st.columns([0.32, 0.68], gap="small")
        with image_col:
            st.markdown(
                f'<img class="pg-portrait" src="{image_data_uri(image_path)}" alt="{html.escape(display_character.name)}">',
                unsafe_allow_html=True,
            )
        with detail_col:
            render_character_summary(display_character)
        return

    render_character_summary(display_character)


def render_character_summary(character) -> None:
    st.markdown(f"**캐릭터: {character.name} · {character.archetype}**")
    st.caption(character.tagline)
    st.markdown(
        f"**소개 요약:** {html.escape(summarize_character(character))}",
        unsafe_allow_html=True,
    )
    with st.expander("캐릭터 소개 자세히", expanded=False):
        render_character_detail(character)


def summarize_character(character, max_length: int = 105) -> str:
    parts = [
        character.symbol,
        character.speech_style,
        character.relationship,
    ]
    summary = " · ".join(part for part in parts if part)
    if not summary:
        summary = character.tagline or character.archetype
    return trim_summary(summary, max_length)


def selected_network_agent_id(personas, view_key: str) -> str | None:
    selected_agent_id = st.session_state.get(agent_selection_key(view_key))
    if any(persona.id == selected_agent_id for persona in personas):
        return selected_agent_id
    if personas:
        return personas[0].id
    return None


def agent_selection_key(view_key: str) -> str:
    return f"{view_key}_selected_agent_id"


def render_agent_network(personas, selected_agent_id: str | None, view_key: str) -> str | None:
    if not personas:
        return None

    st.markdown(f"#### Agent roster · {len(personas)}명")
    for row_start in range(0, len(personas), 2):
        columns = st.columns(2, gap="small")
        for offset, column in enumerate(columns):
            persona_index = row_start + offset
            if persona_index >= len(personas):
                continue
            persona = personas[persona_index]
            with column:
                selected_agent_id = render_agent_roster_card(
                    persona=persona,
                    index=persona_index,
                    selected_agent_id=selected_agent_id,
                    view_key=view_key,
                )

    return selected_agent_id


def render_agent_roster_card(persona, index: int, selected_agent_id: str | None, view_key: str) -> str | None:
    character = (
        CHARACTERS_BY_ID.get(persona.character.id, persona.character)
        if persona.character
        else None
    )
    image_path = CHARACTER_IMAGE_PATHS.get(character.id) if character else None
    role = character.archetype if character else persona.role
    is_selected = persona.id == selected_agent_id
    summary = trim_summary(persona.perspective or persona.role, 118)

    if image_path and os.path.exists(image_path):
        visual = f'<img class="pg-card-image" src="{image_data_uri(image_path)}" alt="{html.escape(persona.name)}">'
    else:
        visual = f'<div class="pg-card-image" style="display:flex;align-items:center;justify-content:center;font-weight:800;color:#1d4ed8;">{html.escape(persona.name[:2])}</div>'

    selected_markup = '<div class="pg-roster-selected">현재 포커스</div>' if is_selected else ""
    card_markup = (
        '<div class="pg-roster-card">'
        '<div style="display:flex; gap:0.78rem; align-items:flex-start;">'
        f'<div>{visual}</div>'
        '<div style="min-width:0;">'
        f'<div class="pg-round-meta">Agent {index + 1}</div>'
        f'<div class="pg-roster-name">{html.escape(persona.name)}</div>'
        f'<div class="pg-roster-role">{html.escape(role)}</div>'
        f'<div class="pg-roster-summary">{html.escape(summary)}</div>'
        f'{selected_markup}'
        '</div>'
        '</div>'
        '</div>'
    )
    with st.container(border=True):
        st.markdown(card_markup, unsafe_allow_html=True)
        button_label = "선택됨" if is_selected else "정보 보기"
        if st.button(
            button_label,
            key=f"{view_key}_agent_select_{persona.id}",
            use_container_width=True,
            help=f"{persona.name}의 역할, 관점, 캐릭터 정보를 확인합니다.",
        ):
            st.session_state[agent_selection_key(view_key)] = persona.id
            st.rerun()
            return persona.id
    return selected_agent_id


def render_selected_agent_info(personas, selected_agent_id: str | None) -> None:
    st.markdown('<div id="agent-info"></div>', unsafe_allow_html=True)
    selected_persona = next(
        (persona for persona in personas if persona.id == selected_agent_id),
        None,
    )
    if not selected_persona:
        st.info("선택한 Agent 없음: 위 `참여 Agent` 영역에서 `정보 보기`를 누르면 해당 Agent의 역할과 캐릭터 정보가 여기에 표시됩니다.")
        return

    character = (
        CHARACTERS_BY_ID.get(selected_persona.character.id, selected_persona.character)
        if selected_persona.character
        else None
    )
    image_path = CHARACTER_IMAGE_PATHS.get(character.id) if character else None

    with st.container(border=True):
        st.markdown(f"#### 선택한 Agent 정보: {selected_persona.name}")
        image_col, detail_col = st.columns([0.12, 0.88], gap="small")
        with image_col:
            if image_path and os.path.exists(image_path):
                render_local_image(image_path, selected_persona.name, "pg-card-image")
            else:
                st.markdown(f"**{selected_persona.name[:2]}**")
        with detail_col:
            st.markdown(f"**토론 역할:** {selected_persona.role}")
            st.markdown(f"**관점:** {selected_persona.perspective}")
            if character:
                st.markdown(f"**캐릭터 요약:** {html.escape(summarize_character(character))}", unsafe_allow_html=True)
            with st.expander("자세한 정보", expanded=False):
                if selected_persona.priority_questions:
                    st.markdown("핵심 질문")
                    for question in selected_persona.priority_questions:
                        st.markdown(f"- {question}")
                if character:
                    render_character_detail(character)


def render_character_detail(character) -> None:
    st.markdown(
        f"""
<div style="
    border-left: 5px solid {character.accent_color};
    background: {character.color};
    padding: 0.75rem;
    border-radius: 0.5rem;
    margin: 0.55rem 0 0.75rem 0;
">
  <div style="display:flex; align-items:center; gap:0.65rem;">
    <div style="
        width:2.4rem;
        height:2.4rem;
        border-radius:50%;
        display:flex;
        align-items:center;
        justify-content:center;
        background:{character.accent_color};
        color:white;
        font-weight:700;
    ">{character.name[:1]}</div>
    <div>
      <div style="font-weight:700;">{character.name} · {character.archetype}</div>
      <div style="font-size:0.88rem;">{character.tagline}</div>
    </div>
  </div>
  <div style="font-size:0.86rem; margin-top:0.55rem;">상징: {character.symbol}</div>
  <div style="font-size:0.86rem; margin-top:0.25rem;">외형: {character.visual}</div>
  <div style="font-size:0.86rem; margin-top:0.25rem;">움직임: {character.motion}</div>
  <div style="font-size:0.86rem; margin-top:0.25rem;">촉감: {character.texture}</div>
  <div style="font-size:0.86rem; margin-top:0.25rem;">관계성: {character.relationship}</div>
  <div style="font-size:0.86rem; margin-top:0.25rem;">말투: {character.speech_style}</div>
</div>
""",
        unsafe_allow_html=True,
    )


render_app_header()

with st.sidebar:
    st.header("실행 설정")
    st.subheader("대화 구성")
    persona_count = st.slider("페르소나 수", min_value=3, max_value=5, value=3)
    debate_rounds = st.slider("Agent 이어 말하기 라운드", min_value=1, max_value=3, value=1)
    max_reply_agents = st.slider("응답 에이전트 수", min_value=1, max_value=3, value=2)

    with st.expander("고급 모델 설정", expanded=False):
        use_llm = st.toggle("LLM API 사용", value=True)
        model = st.text_input("모델명", value=os.getenv("PERSONA_GRAPH_MODEL", "gpt-5.4-mini"))
        temperature = st.slider("응답 다양성", min_value=0.0, max_value=1.2, value=0.35, step=0.05)
        api_status = "설정됨" if os.getenv("OPENAI_API_KEY") else "미설정"
        st.caption(f"OPENAI_API_KEY: {api_status}")

    st.divider()
    selected_sample = st.selectbox("샘플 시나리오", list(SAMPLE_PROBLEMS.keys()))
    load_sample = st.button("샘플을 입력창에 넣기")

if load_sample:
    st.session_state["problem_text"] = SAMPLE_PROBLEMS[selected_sample]
    st.session_state.pop("last_response", None)
    st.session_state["main_view"] = "새 토론 실행"

view = st.radio(
    "화면 선택",
    ["새 토론 실행", "저장된 토론 보기"],
    horizontal=True,
    label_visibility="collapsed",
    key="main_view",
)

if view == "새 토론 실행":
    start_slot = st.empty()
    if not st.session_state.get("last_response") and not st.session_state.get("problem_text"):
        with start_slot.container():
            render_start_cta()
    else:
        start_slot.empty()

    with st.form(key="new_problem_form"):
        problem = st.text_area(
            "해결할 문제",
            key="problem_text",
            height=160,
            placeholder="예: 2주 안에 데모 가능한 다중 에이전트 AI 프로젝트를 만들고 싶다...",
        )
        run = st.form_submit_button(
            "에이전트 토론 시작",
            type="primary",
            use_container_width=True,
        )

    result_slot = st.empty()

    if run:
        if len(problem.strip()) < 5:
            st.warning("문제를 조금 더 구체적으로 입력해주세요.")
            st.stop()

        st.session_state.pop("last_response", None)
        with result_slot.container():
            response = consume_live_stream(
                solve_problem_stream(
                    problem=problem.strip(),
                    persona_count=persona_count,
                    debate_rounds=debate_rounds,
                    use_llm=use_llm,
                    model=model.strip() or None,
                    temperature=temperature,
                )
            )
        if response is None:
            st.error("토론 결과를 만들지 못했습니다.")
            st.stop()

        response = save_run(response)

        st.session_state["last_response"] = response
        with result_slot.container():
            render_response(
                response,
                view_key="new_response",
                max_reply_agents=max_reply_agents,
                use_llm=use_llm,
                model=model.strip() or None,
                temperature=temperature,
                input_key_prefix="new",
            )
    elif st.session_state.get("last_response"):
        last_response = st.session_state["last_response"]
        current_problem = problem.strip()
        if current_problem and current_problem != last_response.problem:
            result_slot.info("입력 내용이 이전 실행 결과와 다릅니다. 현재 입력으로 새 토론을 보려면 `에이전트 토론 시작`을 눌러주세요.")
        else:
            with result_slot.container():
                render_response(
                    last_response,
                    view_key="last_response",
                    max_reply_agents=max_reply_agents,
                    use_llm=use_llm,
                    model=model.strip() or None,
                    temperature=temperature,
                    input_key_prefix="new",
                )
    else:
        if problem.strip():
            result_slot.caption("입력 내용을 확인한 뒤 `에이전트 토론 시작`을 누르세요.")
        else:
            result_slot.caption("샘플을 고르거나 직접 문제를 입력한 뒤 `에이전트 토론 시작`을 누르세요.")

else:
    summaries = list_runs()
    if not summaries:
        st.info("아직 저장된 토론 로그가 없습니다.")
    else:
        labels = {
            format_run_label(summary): summary.run_id
            for summary in summaries
        }
        selected_label = st.selectbox("저장된 실행", list(labels.keys()))
        selected_run_id = labels[selected_label]
        try:
            saved_response = load_run(selected_run_id)
        except FileNotFoundError:
            st.error("선택한 로그를 찾을 수 없습니다.")
        else:
            render_response(
                saved_response,
                view_key=f"saved_{selected_run_id}",
                max_reply_agents=max_reply_agents,
                use_llm=use_llm,
                model=model.strip() or None,
                temperature=temperature,
                input_key_prefix="saved",
            )
