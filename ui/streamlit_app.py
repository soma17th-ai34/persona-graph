from __future__ import annotations

import base64
import html
import os
import re
import sys

from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st

from app.characters import CHARACTER_POOL
from app.schemas import Evaluation, SolveResponse
from app.storage import list_runs, load_run, save_run
from app.workflow import continue_discussion, solve_problem


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
    "debate": "상호 응답",
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


st.set_page_config(page_title="PersonaGraph", page_icon="PG", layout="wide")


def average_score(evaluation: Evaluation) -> float:
    total = (
        evaluation.consistency
        + evaluation.specificity
        + evaluation.risk_awareness
        + evaluation.feasibility
    )
    return round(total / 4, 2)


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
    min-height: 7.5rem;
    border-radius: 8px;
    padding: clamp(1rem, 2.4vw, 1.6rem);
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    background-image:
        linear-gradient(90deg, rgba(255, 255, 255, 0.96) 0%, rgba(255, 255, 255, 0.88) 54%, rgba(255, 255, 255, 0.30) 100%),
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
    width: 3.6rem;
    height: 4.8rem;
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
.pg-decision-bar {{
    border: 1px solid rgba(47, 128, 237, 0.20);
    border-radius: 8px;
    background: linear-gradient(90deg, #f8fbff 0%, #fffaf7 100%);
    padding: 0.85rem 0.95rem;
    margin: 0.55rem 0 1rem 0;
}}
.pg-decision-title {{
    color: #2563eb;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0;
    margin-bottom: 0.2rem;
}}
.pg-decision-text {{
    color: #111827;
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.45;
    margin-bottom: 0.3rem;
}}
.pg-decision-meta {{
    color: #4b5563;
    font-size: 0.82rem;
    line-height: 1.35;
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
.pg-message-summary {{
    color: #111827;
    font-size: 0.95rem;
    line-height: 1.55;
    margin: 0.45rem 0 0.15rem 0;
}}
div[data-testid="stAppViewContainer"] .main .block-container {{
    padding-bottom: 7rem;
}}
div[data-testid="stChatInput"] {{
    position: fixed;
    left: 50%;
    bottom: 1rem;
    transform: translateX(-50%);
    width: min(56rem, calc(100vw - 2rem));
    z-index: 1000;
}}
div[data-testid="stChatInput"] > div {{
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.98);
    box-shadow: 0 16px 38px rgba(31, 41, 55, 0.16);
}}
div[data-testid="stChatInputTextArea"] {{
    font-size: 0.95rem;
}}
button[data-testid="stChatInputSubmitButton"] {{
    border-radius: 12px;
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
  </div>
</section>
""",
        unsafe_allow_html=True,
    )


def render_evaluation(evaluation: Evaluation) -> None:
    st.subheader("평가 요약")
    score = average_score(evaluation)
    with st.container(border=True):
        score_col, verdict_col = st.columns([0.22, 0.78], gap="large")
        with score_col:
            st.metric("평균 점수", f"{score}/5")
        with verdict_col:
            st.markdown(f"**판정:** {score_band_label(score)}")
            st.caption("Evaluator가 일관성, 구체성, 리스크 반영, 실행 가능성을 기준으로 다시 점검한 결과입니다.")

        metric_cols = st.columns(4)
        metric_cols[0].metric("일관성", f"{evaluation.consistency}/5")
        metric_cols[1].metric("구체성", f"{evaluation.specificity}/5")
        metric_cols[2].metric("리스크 반영", f"{evaluation.risk_awareness}/5")
        metric_cols[3].metric("실행 가능성", f"{evaluation.feasibility}/5")

        st.markdown("**평가 한줄**")
        st.info(evaluation.overall_comment)
        if evaluation.improvement_suggestions:
            with st.expander("보완 제안 보기", expanded=False):
                for suggestion in evaluation.improvement_suggestions:
                    st.markdown(f"- {suggestion}")


def score_band_label(score: float) -> str:
    if score >= 4.5:
        return "매우 좋음"
    if score >= 4.0:
        return "좋음"
    if score >= 3.0:
        return "보완 필요"
    return "재검토 필요"


def render_final_answer(response: SolveResponse) -> None:
    st.markdown('<div id="final-answer"></div>', unsafe_allow_html=True)
    st.subheader("최종 결론")
    with st.container(border=True):
        st.markdown("**최종 선택 요약**")
        st.success(summarize_message(response.final_answer, max_length=180))
        st.caption("현재까지의 라운드와 사용자 개입을 Synthesizer Agent가 반영해 갱신한 결론입니다.")
        with st.expander("최종 결론 전문 보기", expanded=False):
            render_message_content(response.final_answer)


def render_quick_decision_bar(response: SolveResponse) -> None:
    score = average_score(response.evaluation)
    decision = html.escape(summarize_message(response.final_answer, max_length=150))
    st.markdown(
        f"""
<div class="pg-decision-bar">
  <div class="pg-decision-title">현재 결론</div>
  <div class="pg-decision-text">{decision}</div>
  <div class="pg-decision-meta">
    평가 {score}/5 · {score_band_label(score)} · <a href="#final-answer">최종 결론으로 이동</a>
  </div>
</div>
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
    status = "LLM API 사용" if response.used_llm else "로컬 폴백 사용"
    st.caption(f"상태: 토론 완료 · 응답 방식: {status}")
    with st.expander("실행 정보 보기", expanded=False):
        st.markdown(f"- model: `{response.model}`")
        if response.run_id:
            st.markdown(f"- run_id: `{response.run_id}`")
        st.markdown(f"- 사용한 응답 방식: `{status}`")
    st.caption("화면 흐름: 참여 Agent 확인 -> Agent 정보 선택 -> 라운드별 대화 확인 -> 하단 입력창으로 의견 추가 -> 결론 확인")
    selected_agent_id = selected_network_agent_id(response.personas, view_key)
    selected_agent_id = render_agent_network(response.personas, selected_agent_id, view_key)
    render_selected_agent_info(response.personas, selected_agent_id)

    st.subheader("에이전트 대화창")
    render_message_timeline(response, key_prefix=view_key)

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
        st.divider()

    render_quick_decision_bar(response)
    render_final_answer(response)
    st.divider()
    render_evaluation(response.evaluation)


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
    return f"{round_number}라운드 · Agent 상호 응답"


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
        caption = f"Agent {agent_count}명 상호 응답 · {len(messages)}개 핵심 발언"
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
    source = message.metadata.get("source", "unknown")
    stage_label = chat_stage_label(message)
    source_label = SOURCE_LABELS.get(source, source)
    summary = summarize_message(message.content, max_length=92)

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
  <span class="{chip_class}">발언자 · {html.escape(message.agent_name)}</span>
  <span class="pg-round-meta">{html.escape(stage_label)} · {html.escape(source_label)}</span>
</div>
<div class="pg-message-summary"><strong>요약:</strong> {html.escape(summary)}</div>
""",
                unsafe_allow_html=True,
            )
            st.caption(f"역할: {message.role}")
            with st.expander("자세히", expanded=False):
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
        return "사용자 의견 응답"
    if message.stage == "synthesizer" and message.metadata.get("phase") == "followup_synthesis":
        return "중간 종합"
    return STAGE_LABELS.get(message.stage, message.stage)


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
        return f"{message.metadata['round']}라운드 상호 응답"
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

    st.caption(f"의견을 보내면 현재 대화방 Agent 중 최대 {max_agents}명이 이어서 답합니다.")
    prompt = st.chat_input(
        "이 라운드에 의견을 추가하세요...",
        key=f"{key_prefix}_chat_input",
    )
    if not prompt:
        return

    content = prompt.strip()
    if not content:
        st.warning("의견을 한 글자 이상 입력해주세요.")
        return

    with st.spinner("Agent들이 현재 의견에 이어서 답변하는 중입니다..."):
        updated = continue_discussion(
            response=response,
            user_content=content,
            max_agents=max_agents,
            use_llm=use_llm,
            model=model,
            temperature=temperature,
        )
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
    return None


def agent_selection_key(view_key: str) -> str:
    return f"{view_key}_selected_agent_id"


def render_agent_network(personas, selected_agent_id: str | None, view_key: str) -> str | None:
    if not personas:
        return None

    st.markdown(f"#### 참여 Agent {len(personas)}명")
    st.caption("각 Agent 카드 아래의 정보 보기 버튼을 누르면 바로 아래에 역할, 관점, 캐릭터 정보가 표시됩니다.")
    column_widths = []
    for index in range(len(personas)):
        column_widths.append(1.0)
        if index < len(personas) - 1:
            column_widths.append(0.14)

    with st.container(border=True):
        columns = st.columns(column_widths, gap="small")

        for index, persona in enumerate(personas):
            character = (
                CHARACTERS_BY_ID.get(persona.character.id, persona.character)
                if persona.character
                else None
            )
            image_path = CHARACTER_IMAGE_PATHS.get(character.id) if character else None
            role = character.archetype if character else persona.role
            is_selected = persona.id == selected_agent_id

            with columns[index * 2]:
                with st.container(border=True):
                    st.caption(f"Agent {index + 1}")
                    image_col, text_col = st.columns([0.38, 0.62], gap="small")
                    with image_col:
                        if image_path and os.path.exists(image_path):
                            render_local_image(image_path, persona.name, "pg-card-image")
                        else:
                            st.markdown(f"**{persona.name[:2]}**")
                    with text_col:
                        st.markdown(f"**{persona.name}**")
                        st.caption(f"역할: {role}")
                    if is_selected:
                        st.success("현재 선택한 Agent")
                    button_label = (
                        f"Agent {index + 1} 선택됨"
                        if is_selected
                        else f"Agent {index + 1} 정보 보기"
                    )
                    if st.button(
                        button_label,
                        key=f"{view_key}_agent_select_{persona.id}",
                        use_container_width=True,
                        help=f"{persona.name}의 역할, 관점, 캐릭터 정보를 확인합니다.",
                    ):
                        st.session_state[agent_selection_key(view_key)] = persona.id
                        st.rerun()

            if index < len(personas) - 1:
                with columns[index * 2 + 1]:
                    st.markdown('<div class="pg-native-connector"></div>', unsafe_allow_html=True)

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

tab_new, tab_saved = st.tabs(["새 토론 실행", "저장된 토론 보기"])

with tab_new:
    with st.sidebar:
        st.header("실행 설정")
        st.subheader("대화 구성")
        persona_count = st.slider("페르소나 수", min_value=3, max_value=5, value=5)
        debate_rounds = st.slider("상호 응답 라운드", min_value=1, max_value=3, value=1)
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

    if not st.session_state.get("last_response"):
        render_start_cta()

    problem = st.text_area(
        "해결할 문제",
        key="problem_text",
        height=160,
        placeholder="예: 2주 안에 데모 가능한 다중 에이전트 AI 프로젝트를 만들고 싶다...",
    )

    run = st.button("에이전트 토론 시작", type="primary", use_container_width=True)

    if run:
        if len(problem.strip()) < 5:
            st.warning("문제를 조금 더 구체적으로 입력해주세요.")
            st.stop()

        with st.spinner("PersonaGraph가 에이전트 토론을 진행 중입니다..."):
            response = solve_problem(
                problem=problem.strip(),
                persona_count=persona_count,
                debate_rounds=debate_rounds,
                use_llm=use_llm,
                model=model.strip() or None,
                temperature=temperature,
            )
            response = save_run(response)

        st.session_state["last_response"] = response
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
        render_response(
            st.session_state["last_response"],
            view_key="last_response",
            max_reply_agents=max_reply_agents,
            use_llm=use_llm,
            model=model.strip() or None,
            temperature=temperature,
            input_key_prefix="new",
        )
    else:
        st.caption("샘플을 고르거나 직접 문제를 입력한 뒤 `에이전트 토론 시작`을 누르세요.")

with tab_saved:
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
