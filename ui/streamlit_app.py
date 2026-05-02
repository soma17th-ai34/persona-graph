import os
import sys

from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st

from app.schemas import Evaluation, SolveResponse
from app.storage import list_runs, load_run, save_run
from app.workflow import solve_problem


load_dotenv(os.path.join(ROOT_DIR, ".env"))

SAMPLE_PROBLEMS = {
    "Software Maestro 프로젝트 선정": "2026 Software Maestro를 목표로 2주 안에 보여줄 수 있는 AI 프로젝트 MVP를 정해야 한다. 포트폴리오 가치, 데모 안정성, 구현 난이도를 함께 고려해줘.",
    "캠퍼스 팀 프로젝트 리스크": "4명 팀이 3주 안에 AI 기반 학습 도우미를 만들어야 한다. 기능 욕심이 많고 역할 분담이 애매하다. 성공 가능성을 높이는 계획을 제안해줘.",
    "Physical AI 아이디어 검증": "저예산으로 Physical AI 프로젝트를 시작하고 싶다. 하드웨어 구매 전에 시뮬레이션과 소프트웨어 MVP로 검증할 방법을 찾아줘.",
}

STAGE_LABELS = {
    "persona_generation": "페르소나 생성",
    "specialist": "전문가 의견",
    "critic": "비판",
    "synthesizer": "최종 종합",
}

SOURCE_LABELS = {
    "llm": "LLM",
    "fallback": "기본 응답",
    "unknown": "알 수 없음",
}


st.set_page_config(page_title="PersonaGraph", page_icon="PG", layout="wide")

st.title("PersonaGraph")
st.caption("문제를 입력하면 여러 AI 에이전트가 각자의 페르소나로 토론하고, 비판과 종합을 거쳐 최종 해결안을 만듭니다.")


def average_score(evaluation: Evaluation) -> float:
    total = (
        evaluation.consistency
        + evaluation.specificity
        + evaluation.risk_awareness
        + evaluation.feasibility
    )
    return round(total / 4, 2)


def render_evaluation(evaluation: Evaluation) -> None:
    st.subheader("평가 요약")
    metric_cols = st.columns(5)
    metric_cols[0].metric("평균", f"{average_score(evaluation)}/5")
    metric_cols[1].metric("일관성", f"{evaluation.consistency}/5")
    metric_cols[2].metric("구체성", f"{evaluation.specificity}/5")
    metric_cols[3].metric("리스크 반영", f"{evaluation.risk_awareness}/5")
    metric_cols[4].metric("실행 가능성", f"{evaluation.feasibility}/5")
    st.markdown(evaluation.overall_comment)
    if evaluation.improvement_suggestions:
        st.markdown("개선 제안")
        for suggestion in evaluation.improvement_suggestions:
            st.markdown(f"- {suggestion}")


def render_response(response: SolveResponse) -> None:
    status = "LLM API 사용" if response.used_llm else "로컬 폴백 사용"
    run_label = f" / run_id={response.run_id}" if response.run_id else ""
    st.success(f"토론 완료: {status} / model={response.model}{run_label}")

    left, right = st.columns([0.38, 0.62], gap="large")

    with left:
        st.subheader("생성된 페르소나")
        for persona in response.personas:
            with st.container(border=True):
                st.markdown(f"**{persona.name}**")
                st.caption(persona.role)
                if persona.character:
                    render_character(persona.character)
                st.write(persona.perspective)
                st.markdown("핵심 질문")
                for question in persona.priority_questions:
                    st.markdown(f"- {question}")

    with right:
        st.subheader("에이전트 발언 흐름")
        for message in response.messages:
            source = message.metadata.get("source", "unknown")
            stage_label = STAGE_LABELS.get(message.stage, message.stage)
            source_label = SOURCE_LABELS.get(source, source)
            title = f"{message.agent_name} · {stage_label} · {source_label}"
            with st.expander(title, expanded=message.stage in {"critic", "synthesizer"}):
                st.caption(message.role)
                st.markdown(message.content)
                if message.metadata.get("error") and source == "fallback":
                    st.caption(f"기본 응답 사용 이유: {message.metadata['error']}")

    st.divider()
    st.subheader("최종 결론")
    st.markdown(response.final_answer)
    st.divider()
    render_evaluation(response.evaluation)


def render_character(character) -> None:
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
  <div style="font-size:0.86rem; margin-top:0.25rem;">말투: {character.speech_style}</div>
</div>
""",
        unsafe_allow_html=True,
    )


tab_new, tab_saved = st.tabs(["새 토론 실행", "저장된 토론 보기"])

with tab_new:
    with st.sidebar:
        st.header("실행 설정")
        persona_count = st.slider("페르소나 수", min_value=3, max_value=5, value=4)
        use_llm = st.toggle("LLM API 사용", value=True)
        model = st.text_input("모델명", value=os.getenv("PERSONA_GRAPH_MODEL", "gpt-5.4-mini"))
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.2, value=0.35, step=0.05)
        api_status = "설정됨" if os.getenv("OPENAI_API_KEY") else "미설정"
        st.info(f"OPENAI_API_KEY: {api_status}")

        st.divider()
        selected_sample = st.selectbox("샘플 시나리오", list(SAMPLE_PROBLEMS.keys()))
        load_sample = st.button("샘플 불러오기")

    if load_sample:
        st.session_state["problem_text"] = SAMPLE_PROBLEMS[selected_sample]

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
                use_llm=use_llm,
                model=model.strip() or None,
                temperature=temperature,
            )
            response = save_run(response)

        st.session_state["last_response"] = response
        render_response(response)
    elif st.session_state.get("last_response"):
        render_response(st.session_state["last_response"])
    else:
        st.info("왼쪽에서 샘플을 불러오거나 직접 문제를 입력한 뒤 에이전트 토론을 시작하세요.")

with tab_saved:
    summaries = list_runs()
    if not summaries:
        st.info("아직 저장된 토론 로그가 없습니다.")
    else:
        labels = {
            f"{summary.created_at.strftime('%Y-%m-%d %H:%M:%S')} · {summary.average_score}/5 · {summary.problem_preview}": summary.run_id
            for summary in summaries
        }
        selected_label = st.selectbox("저장된 실행", list(labels.keys()))
        selected_run_id = labels[selected_label]
        try:
            saved_response = load_run(selected_run_id)
        except FileNotFoundError:
            st.error("선택한 로그를 찾을 수 없습니다.")
        else:
            render_response(saved_response)
