from __future__ import annotations

import os
import tempfile
import unittest

from app.agents.evaluator import EvaluatorAgent
from app.agents.moderator import ModeratorAgent
from app.agents.specialist import SpecialistAgent
from app.agents.supervisor import Supervisor
from app.llm import LLMClient, LLMResult
from app.schemas import AgentMessage, Evaluation, MemoryRecord, Persona, ReasoningRecord, SearchRecord, SolveResponse
from app.search import Classification
from app.workflow import continue_discussion_stream, solve_problem_stream


class FakeLLM:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []
        self.model = "test"
        self.enabled = True

    def complete(self, system_prompt: str, user_prompt: str, temperature=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "temperature": temperature,
            }
        )
        if not self.results:
            raise AssertionError("FakeLLM received more calls than expected")
        return self.results.pop(0)


class ExtraRoundEvaluator:
    REVERSE_VERIFICATION_MAX_ATTEMPTS = 3

    def __init__(self):
        self.reverse_calls = 0

    def evaluate(self, problem, debate_messages, critique, synthesis):
        return Evaluation(
            consistency=5,
            specificity=5,
            risk_awareness=5,
            feasibility=5,
            overall_comment="평가 기준을 만족합니다.",
            improvement_suggestions=[],
            metadata={"source": "test"},
        )

    def reverse_verify(
        self,
        problem,
        debate_messages,
        critique,
        synthesis,
        search_context=None,
        memory_context=None,
    ):
        self.reverse_calls += 1
        if self.reverse_calls == 1:
            return {
                "score": 2,
                "passed": False,
                "threshold": 4,
                "missing_points": ["선택 기준이 부족합니다."],
                "unsupported_points": [],
                "style_issues": [],
                "needs_extra_round": True,
                "refine_instruction": "선택 기준을 한 번 더 좁히세요.",
                "source": "test",
            }
        return {
            "score": 5,
            "passed": True,
            "threshold": 4,
            "missing_points": [],
            "unsupported_points": [],
            "style_issues": [],
            "needs_extra_round": False,
            "refine_instruction": "",
            "source": "test",
        }


class TranscriptRecordingSpecialist:
    def __init__(self):
        self.respond_transcripts = []
        self.reply_transcripts = []

    def answer(
        self,
        problem: str,
        persona: Persona,
        search_context: str | None = None,
    ) -> AgentMessage:
        return AgentMessage(
            stage="specialist",
            agent_id=persona.id,
            agent_name=persona.name,
            role=persona.role,
            content=f"initial {persona.id}",
            metadata={"source": "test"},
        )

    def respond(
        self,
        problem: str,
        persona: Persona,
        transcript: str,
        moderator_note: str,
        round_number: int,
    ) -> AgentMessage:
        self.respond_transcripts.append((persona.id, round_number, transcript))
        return AgentMessage(
            stage="debate",
            agent_id=persona.id,
            agent_name=persona.name,
            role=persona.role,
            content=f"debate {persona.id} round {round_number}",
            metadata={"source": "test", "round": round_number},
        )

    def reply_to_user(
        self,
        problem: str,
        persona: Persona,
        transcript: str,
        user_content: str,
        round_number: int,
        search_context: str | None = None,
    ) -> AgentMessage:
        self.reply_transcripts.append((persona.id, round_number, transcript))
        return AgentMessage(
            stage="debate",
            agent_id=persona.id,
            agent_name=persona.name,
            role=persona.role,
            content=f"reply {persona.id} round {round_number}",
            metadata={
                "source": "test",
                "round": round_number,
                "phase": "user_response",
                "responds_to": "user",
            },
        )


class FakeSearchClient:
    enabled = True
    provider = "fake"

    def __init__(self, classification: Classification, context: str | None):
        self.classification = classification
        self.context = context
        self.classify_calls = []
        self.fetch_calls = []

    def classify(self, text: str, llm, mode: str = "auto") -> Classification:
        self.classify_calls.append((text, mode))
        return self.classification

    def fetch(self, queries: list[str]) -> str | None:
        self.fetch_calls.append(queries)
        return self.context


class FakeMemoryClient:
    def __init__(self, context: str | None, status: str = "selected"):
        self.context = context
        self.status = status
        self.calls = []

    def build_context(self, problem: str, phase: str):
        self.calls.append((problem, phase))
        return self.context, MemoryRecord(
            phase="followup" if phase == "followup" else "initial",
            enabled=True,
            status=self.status,
            selected_run_ids=["20260513-010101-aaaaaaaa"] if self.context else [],
            positive_count=1 if self.context else 0,
            negative_count=0,
            context=self.context,
        )


class FixedPersonaGenerator:
    def __init__(self, personas: list[Persona]):
        self.personas = personas

    def generate(self, problem: str, count: int, search_context: str | None = None):
        return self.personas[:count], AgentMessage(
            stage="persona_generation",
            agent_id="persona_generator",
            agent_name="페르소나 생성기",
            role="문제에 맞는 에이전트 팀을 생성하는 역할",
            content="fixed personas",
            metadata={"source": "test"},
        )


class FixedModerator:
    def open(self, problem: str, personas: list[Persona]) -> AgentMessage:
        return AgentMessage(
            stage="moderator",
            agent_id="moderator",
            agent_name="사회자 에이전트",
            role="토론을 여는 역할",
            content="fixed opening",
            metadata={"source": "test", "phase": "opening"},
        )

    def guide(self, problem, personas, transcript, round_number, focus=None) -> AgentMessage:
        return AgentMessage(
            stage="moderator",
            agent_id="moderator",
            agent_name="사회자 에이전트",
            role="상호 응답 라운드를 여는 역할",
            content="fixed guide",
            metadata={"source": "test", "phase": "response_round", "round": round_number},
        )


class FixedCritic:
    def review(
        self,
        problem: str,
        debate_messages: list[AgentMessage],
        search_context: str | None = None,
        memory_context: str | None = None,
    ) -> AgentMessage:
        return AgentMessage(
            stage="critic",
            agent_id="critic",
            agent_name="비판 에이전트",
            role="누락을 찾는 역할",
            content="검증 기준과 사용자 제약을 빠뜨리면 안 됩니다.",
            metadata={"source": "test"},
        )


class PassingEvaluator:
    REVERSE_VERIFICATION_MAX_ATTEMPTS = 3

    def evaluate(self, problem, debate_messages, critique, synthesis):
        return Evaluation(
            consistency=5,
            specificity=5,
            risk_awareness=5,
            feasibility=5,
            overall_comment="평가 기준을 만족합니다.",
            improvement_suggestions=[],
            metadata={"source": "test"},
        )

    def reverse_verify(
        self,
        problem,
        debate_messages,
        critique,
        synthesis,
        search_context=None,
        memory_context=None,
    ):
        return {
            "score": 5,
            "passed": True,
            "threshold": 4,
            "missing_points": [],
            "unsupported_points": [],
            "style_issues": [],
            "needs_extra_round": False,
            "refine_instruction": "",
            "source": "test",
        }


class RecordingCritic:
    def __init__(self):
        self.memory_contexts = []
        self.search_contexts = []

    def review(
        self,
        problem: str,
        debate_messages: list[AgentMessage],
        search_context: str | None = None,
        memory_context: str | None = None,
    ) -> AgentMessage:
        self.search_contexts.append(search_context)
        self.memory_contexts.append(memory_context)
        return AgentMessage(
            stage="critic",
            agent_id="critic",
            agent_name="비판 에이전트",
            role="누락을 찾는 역할",
            content="선별 메모리를 반영해 근거 없는 전제를 줄입니다.",
            metadata={"source": "test"},
        )


class RecordingSynthesizer:
    def __init__(self):
        self.memory_contexts = []
        self.search_contexts = []

    def synthesize_with_candidates(
        self,
        problem: str,
        debate_messages: list[AgentMessage],
        critique: AgentMessage,
        phase: str,
        search_context: str | None = None,
        memory_context: str | None = None,
    ):
        self.search_contexts.append(search_context)
        self.memory_contexts.append(memory_context)
        record = ReasoningRecord(
            phase="followup" if phase == "followup" else "initial",
            stage="synthesis",
            mode="tree",
            enabled=False,
            status="skipped_no_llm",
        )
        return (
            AgentMessage(
                stage="synthesizer",
                agent_id="synthesizer",
                agent_name="종합 에이전트",
                role="토론을 최종 답변으로 통합하는 역할",
                content="선별 메모리 기준으로 현재 문제에만 맞춰 답합니다.",
                metadata={"source": "test"},
            ),
            record,
        )

    def synthesize(
        self,
        problem: str,
        debate_messages: list[AgentMessage],
        critique: AgentMessage,
        improvement_suggestions=None,
        previous_synthesis=None,
        refine_instruction=None,
        search_context: str | None = None,
        memory_context: str | None = None,
    ):
        self.search_contexts.append(search_context)
        self.memory_contexts.append(memory_context)
        return AgentMessage(
            stage="synthesizer",
            agent_id="synthesizer",
            agent_name="종합 에이전트",
            role="토론을 최종 답변으로 통합하는 역할",
            content="보완된 답변입니다.",
            metadata={"source": "test"},
        )


class RecordingEvaluator(PassingEvaluator):
    def __init__(self):
        self.memory_contexts = []
        self.search_contexts = []

    def reverse_verify(
        self,
        problem,
        debate_messages,
        critique,
        synthesis,
        search_context=None,
        memory_context=None,
    ):
        self.search_contexts.append(search_context)
        self.memory_contexts.append(memory_context)
        return super().reverse_verify(
            problem,
            debate_messages,
            critique,
            synthesis,
            search_context=search_context,
            memory_context=memory_context,
        )


class StreamingWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.previous_memory_dir = os.environ.get("PERSONA_GRAPH_MEMORY_RUNS_DIR")
        self.memory_dir = tempfile.TemporaryDirectory()
        os.environ["PERSONA_GRAPH_MEMORY_RUNS_DIR"] = self.memory_dir.name

    def tearDown(self):
        if self.previous_memory_dir is None:
            os.environ.pop("PERSONA_GRAPH_MEMORY_RUNS_DIR", None)
        else:
            os.environ["PERSONA_GRAPH_MEMORY_RUNS_DIR"] = self.previous_memory_dir
        self.memory_dir.cleanup()

    def test_solve_stream_emits_messages_and_final_response(self):
        events = list(
            solve_problem_stream(
                problem="2주 안에 보여줄 AI 프로젝트 MVP를 정해야 한다.",
                persona_count=3,
                debate_rounds=1,
                use_llm=False,
            )
        )

        event_types = [event["type"] for event in events]
        self.assertIn("personas_ready", event_types)
        self.assertIn("agent_started", event_types)
        self.assertIn("agent_message", event_types)
        self.assertEqual("final_response", events[-1]["type"])

        response = events[-1]["response"]
        self.assertEqual(3, len(response.personas))
        self.assertGreater(len(response.messages), 0)

    def test_initial_solve_records_search_not_needed(self):
        events = list(
            solve_problem_stream(
                problem="2주 안에 보여줄 AI 프로젝트 MVP를 정해야 한다.",
                persona_count=3,
                debate_rounds=1,
                use_llm=False,
            )
        )

        record = events[-1]["response"].search_records[0]

        self.assertEqual("initial", record.phase)
        self.assertEqual("auto", record.mode)
        self.assertEqual("not_needed", record.status)
        self.assertFalse(record.needed)

    def test_initial_solve_records_fetched_search_context(self):
        supervisor = Supervisor(LLMClient(enabled=False))
        supervisor.search_client = FakeSearchClient(
            Classification(needs_search=True, queries=["테스트 검색"], reason="test"),
            "[테스트 결과] 검색 context\n[두 번째 결과] 추가 context",
        )

        events = list(
            supervisor.solve_stream(
                problem="검색 기록을 확인한다.",
                persona_count=3,
                debate_rounds=1,
                search_mode="auto",
            )
        )

        record = events[-1]["response"].search_records[0]

        self.assertEqual("fetched", record.status)
        self.assertEqual(["테스트 검색"], record.queries)
        self.assertEqual(2, record.result_count)
        self.assertEqual("fake", record.provider)
        self.assertIn("검색 context", record.context)

    def test_initial_solve_records_memory_and_passes_context_to_quality_agents(self):
        memory_context = "선별 품질 메모리: 근거 없는 하드웨어 구매 전제를 피하세요."
        supervisor = self._recording_supervisor(memory_context)

        events = list(
            supervisor.solve_stream(
                problem="Physical AI MVP를 하드웨어 구매 전 검증하고 싶다.",
                persona_count=3,
                debate_rounds=1,
                search_mode="off",
            )
        )

        response = events[-1]["response"]

        self.assertEqual("selected", response.memory_records[0].status)
        self.assertEqual(memory_context, response.memory_records[0].context)
        self.assertEqual([memory_context], supervisor.critic.memory_contexts)
        self.assertEqual([memory_context], supervisor.synthesizer.memory_contexts)
        self.assertEqual([memory_context], supervisor.evaluator.memory_contexts)

    def test_initial_solve_selects_synthesis_candidate_and_records_reasoning(self):
        llm = FakeLLM(
            [
                LLMResult(
                    content="""[
                        {"id": "candidate_1", "title": "검색 강화안", "answer": "검색어를 먼저 다듬는 방향입니다. 근거 품질을 높이는 데 집중합니다."},
                        {"id": "candidate_2", "title": "시뮬레이션 검증안", "answer": "하드웨어 구매 전에는 시뮬레이션 루프를 먼저 고정하는 편이 좋습니다. 입력과 상태 전이를 로그로 남기면 발표 전에 실패 조건을 확인할 수 있습니다."},
                        {"id": "candidate_3", "title": "역할 분담안", "answer": "팀 역할을 먼저 나누는 방향입니다. 구현 속도는 빨라지지만 검증 장면이 약할 수 있습니다."}
                    ]""",
                    used_llm=True,
                ),
                LLMResult(
                    content="""{
                        "selected_id": "candidate_2",
                        "selection_summary": "사용자의 하드웨어 구매 전 검증 의도에 가장 직접적으로 답합니다.",
                        "scores": {"candidate_1": 3, "candidate_2": 5, "candidate_3": 4}
                    }""",
                    used_llm=True,
                ),
            ]
        )
        supervisor = self._candidate_supervisor(llm)

        events = list(
            supervisor.solve_stream(
                problem="하드웨어 구매 전에 Physical AI MVP를 검증하고 싶다.",
                persona_count=3,
                debate_rounds=1,
                search_mode="off",
            )
        )

        response = events[-1]["response"]
        record = response.reasoning_records[0]

        self.assertIn("시뮬레이션 루프", response.final_answer)
        self.assertEqual("selected", record.status)
        self.assertEqual(3, record.candidate_count)
        self.assertEqual("candidate_2", record.selected_id)
        self.assertEqual(5, record.scores["candidate_2"])
        self.assertIn("검증 의도", record.selection_summary)

    def test_reasoning_record_skips_when_llm_disabled(self):
        events = list(
            solve_problem_stream(
                problem="2주 안에 보여줄 AI 프로젝트 MVP를 정해야 한다.",
                persona_count=3,
                debate_rounds=1,
                use_llm=False,
            )
        )

        response = events[-1]["response"]
        record = response.reasoning_records[0]

        self.assertEqual("skipped_no_llm", record.status)
        self.assertFalse(record.enabled)
        self.assertEqual(0, record.candidate_count)
        self.assertIn("결론은", response.final_answer)

    def test_fallback_final_answer_is_short_plain_text(self):
        events = list(
            solve_problem_stream(
                problem="2주 안에 보여줄 AI 프로젝트 MVP를 정해야 한다.",
                persona_count=3,
                debate_rounds=1,
                use_llm=False,
            )
        )

        final_answer = events[-1]["response"].final_answer
        final_lines = [line for line in final_answer.splitlines() if line.strip()]

        self.assertLessEqual(len(final_lines), 6)
        self.assertTrue(all(not line.startswith(("#", "-", "*")) for line in final_lines))
        self.assertTrue(all(not line[:2].replace(".", "").isdigit() for line in final_lines))
        self.assertNotIn("**", final_answer)

    def test_moderator_strips_markdown_from_llm_output(self):
        llm = FakeLLM(
            [
                LLMResult(
                    content="""### 핵심 진행
1. **하늘**은 먼저 기준을 좁혀주세요.
- `노리`는 앞선 발언에 바로 반응해주세요.""",
                    used_llm=True,
                )
            ]
        )
        moderator = ModeratorAgent(llm)
        personas = [
            Persona(
                id="demo",
                name="하늘",
                role="발표 흐름을 설계하는 역할",
                perspective="청중이 바로 이해할 수 있는 장면을 중시합니다.",
                priority_questions=["첫 화면에서 무엇을 보여줄 것인가?"],
            )
        ]

        message = moderator.open("데모 흐름을 정해야 한다.", personas)

        self.assertNotIn("###", message.content)
        self.assertNotIn("**", message.content)
        self.assertNotIn("`", message.content)
        self.assertFalse(any(line.startswith(("1.", "- ")) for line in message.content.splitlines()))
        self.assertIn("하늘은 먼저 기준을 좁혀주세요.", message.content)

    def test_continue_stream_starts_with_user_message(self):
        initial_events = list(
            solve_problem_stream(
                problem="저예산 Physical AI 프로젝트를 검증하고 싶다.",
                persona_count=3,
                debate_rounds=1,
                use_llm=False,
            )
        )
        response = initial_events[-1]["response"]

        events = list(
            continue_discussion_stream(
                response=response,
                user_content="예산은 100만 원이고 발표 장면이 중요하다.",
                max_agents=2,
                use_llm=False,
            )
        )

        first_message = events[0]["message"]
        self.assertEqual("agent_message", events[0]["type"])
        self.assertEqual("user", first_message.stage)
        self.assertEqual("final_response", events[-1]["type"])

    def test_debate_round_context_updates_only_after_round_ends(self):
        supervisor = Supervisor(LLMClient(enabled=False))
        specialist = TranscriptRecordingSpecialist()
        supervisor.specialist = specialist

        list(
            supervisor.solve_stream(
                problem="라운드 컨텍스트 업데이트 방식을 확인한다.",
                persona_count=3,
                debate_rounds=2,
            )
        )

        round_one = [
            transcript
            for _, round_number, transcript in specialist.respond_transcripts
            if round_number == 1
        ]
        round_two = [
            transcript
            for _, round_number, transcript in specialist.respond_transcripts
            if round_number == 2
        ]

        self.assertEqual(3, len(round_one))
        self.assertEqual(3, len(round_two))
        self.assertEqual(1, len(set(round_one)))
        self.assertEqual(1, len(set(round_two)))
        self.assertNotIn("debate product_strategist round 1", round_one[0])
        self.assertIn("debate product_strategist round 1", round_two[0])
        self.assertIn("debate systems_engineer round 1", round_two[0])
        self.assertIn("debate ai_researcher round 1", round_two[0])
        self.assertNotIn("debate product_strategist round 2", round_two[0])

    def test_followup_context_updates_only_after_reply_round_ends(self):
        personas = [
            Persona(
                id="demo",
                name="데모 설계자",
                role="발표 흐름을 설계하는 역할",
                perspective="청중이 바로 이해할 수 있는 발표 임팩트를 중시합니다.",
                priority_questions=["첫 화면에서 무엇을 보여줄 것인가?"],
            ),
            Persona(
                id="budget",
                name="예산 관리자",
                role="비용과 구매 우선순위를 조정하는 역할",
                perspective="예산, 부품 비용, 지출 순서를 먼저 좁힙니다.",
                priority_questions=["얼마까지 쓸 수 있는가?"],
            ),
            Persona(
                id="risk",
                name="리스크 분석가",
                role="실패 조건과 안전 범위를 점검하는 역할",
                perspective="위험, 일정, 실패 가능성을 먼저 봅니다.",
                priority_questions=["어디서 실패할 수 있는가?"],
            ),
        ]
        response = self._response_for_followup_context_test(personas)
        supervisor = Supervisor(LLMClient(enabled=False))
        specialist = TranscriptRecordingSpecialist()
        supervisor.specialist = specialist

        list(
            supervisor.continue_discussion_stream(
                response=response,
                user_content="발표 임팩트를 우선하고 싶다.",
                max_agents=3,
            )
        )

        transcripts = [transcript for _, _, transcript in specialist.reply_transcripts]

        self.assertEqual(3, len(transcripts))
        self.assertEqual(1, len(set(transcripts)))
        self.assertIn("previous debate", transcripts[0])
        self.assertIn("발표 임팩트를 우선하고 싶다.", transcripts[0])
        self.assertNotIn("reply demo round 2", transcripts[0])
        self.assertNotIn("reply budget round 2", transcripts[0])

    def test_followup_appends_search_record(self):
        personas = [
            Persona(
                id="demo",
                name="데모 설계자",
                role="발표 흐름을 설계하는 역할",
                perspective="청중이 바로 이해할 수 있는 발표 임팩트를 중시합니다.",
                priority_questions=["첫 화면에서 무엇을 보여줄 것인가?"],
            )
        ]
        response = self._response_for_followup_context_test(personas).model_copy(
            update={
                "search_records": [
                    SearchRecord(
                        phase="initial",
                        mode="auto",
                        enabled=True,
                        needed=False,
                        status="not_needed",
                    )
                ]
            }
        )
        supervisor = Supervisor(LLMClient(enabled=False))
        supervisor.search_client = FakeSearchClient(
            Classification(needs_search=True, queries=["후속 검색"], reason="test"),
            "[후속 결과] 저장될 context",
        )

        events = list(
            supervisor.continue_discussion_stream(
                response=response,
                user_content="요즘 사례도 반영해줘.",
                max_agents=1,
                search_mode="auto",
            )
        )

        records = events[-1]["response"].search_records

        self.assertEqual(2, len(records))
        self.assertEqual("not_needed", records[0].status)
        self.assertEqual("followup", records[1].phase)
        self.assertEqual("fetched", records[1].status)
        self.assertEqual(["후속 검색"], records[1].queries)
        self.assertIn("저장될 context", records[1].context)

    def test_followup_appends_memory_record(self):
        personas = [
            Persona(
                id="demo",
                name="데모 설계자",
                role="발표 흐름을 설계하는 역할",
                perspective="청중이 바로 이해할 수 있는 발표 임팩트를 중시합니다.",
                priority_questions=["첫 화면에서 무엇을 보여줄 것인가?"],
            )
        ]
        response = self._response_for_followup_context_test(personas).model_copy(
            update={
                "memory_records": [
                    MemoryRecord(
                        phase="initial",
                        enabled=True,
                        status="empty",
                    )
                ]
            }
        )
        memory_context = "선별 품질 메모리: 발표 장면은 근거와 실패 조건을 같이 보여주세요."
        supervisor = self._recording_supervisor(memory_context, personas=personas)

        events = list(
            supervisor.continue_discussion_stream(
                response=response,
                user_content="발표 임팩트를 더 키워줘.",
                max_agents=1,
                search_mode="off",
            )
        )

        records = events[-1]["response"].memory_records

        self.assertEqual(2, len(records))
        self.assertEqual("initial", records[0].phase)
        self.assertEqual("followup", records[1].phase)
        self.assertEqual("selected", records[1].status)
        self.assertEqual(memory_context, supervisor.synthesizer.memory_contexts[-1])

    def test_followup_appends_reasoning_record(self):
        personas = [
            Persona(
                id="demo",
                name="데모 설계자",
                role="발표 흐름을 설계하는 역할",
                perspective="청중이 바로 이해할 수 있는 발표 임팩트를 중시합니다.",
                priority_questions=["첫 화면에서 무엇을 보여줄 것인가?"],
            )
        ]
        response = self._response_for_followup_context_test(personas).model_copy(
            update={
                "reasoning_records": [
                    ReasoningRecord(
                        phase="initial",
                        stage="synthesis",
                        mode="tree",
                        enabled=False,
                        status="skipped_no_llm",
                    )
                ]
            }
        )
        llm = FakeLLM(
            [
                LLMResult(
                    content="""[
                        {"id": "candidate_1", "title": "작은 보완", "answer": "후속 답변은 기존 결론을 조금만 보완하는 편이 좋습니다."},
                        {"id": "candidate_2", "title": "발표 장면 강화", "answer": "후속 답변은 발표에서 보일 장면을 먼저 고정해야 합니다. 사용자 의견이 발표 임팩트를 요구하므로 데모 장면과 실패 조건을 같이 좁히는 편이 좋습니다."},
                        {"id": "candidate_3", "title": "범위 축소", "answer": "후속 답변은 범위를 줄이는 쪽으로 정리할 수 있습니다."}
                    ]""",
                    used_llm=True,
                ),
                LLMResult(
                    content="""{
                        "selected_id": "candidate_2",
                        "selection_summary": "후속 사용자 의견의 발표 임팩트 요구를 가장 잘 반영합니다.",
                        "scores": {"candidate_1": 3, "candidate_2": 5, "candidate_3": 4}
                    }""",
                    used_llm=True,
                ),
            ]
        )
        supervisor = self._candidate_supervisor(llm, personas=personas)

        events = list(
            supervisor.continue_discussion_stream(
                response=response,
                user_content="발표 임팩트를 더 키워줘.",
                max_agents=1,
                search_mode="off",
            )
        )

        records = events[-1]["response"].reasoning_records

        self.assertEqual(2, len(records))
        self.assertEqual("initial", records[0].phase)
        self.assertEqual("followup", records[1].phase)
        self.assertEqual("selected", records[1].status)
        self.assertEqual("candidate_2", records[1].selected_id)

    def _response_for_followup_context_test(self, personas: list[Persona]) -> SolveResponse:
        return SolveResponse(
            run_id="20260510-000000-00000000",
            problem="후속 라운드 컨텍스트를 확인한다.",
            personas=personas,
            messages=[
                AgentMessage(
                    stage="debate",
                    agent_id="demo",
                    agent_name="데모 설계자",
                    role="발표 흐름을 설계하는 역할",
                    content="previous debate",
                    metadata={"source": "test", "round": 1},
                )
            ],
            final_answer="previous final",
            evaluation=Evaluation(
                consistency=5,
                specificity=5,
                risk_awareness=5,
                feasibility=5,
                overall_comment="테스트 응답입니다.",
            ),
            used_llm=False,
            model="test",
        )

    def _candidate_supervisor(self, llm, personas: list[Persona] | None = None) -> Supervisor:
        selected_personas = personas or [
            Persona(
                id="product",
                name="제품 전략가",
                role="MVP 범위를 정리하는 역할",
                perspective="가장 작은 검증 루프를 중시합니다.",
                priority_questions=["무엇을 먼저 검증할 것인가?"],
            ),
            Persona(
                id="systems",
                name="시스템 엔지니어",
                role="구현 가능성을 점검하는 역할",
                perspective="상태와 로그를 중시합니다.",
                priority_questions=["어디서 실패할 수 있는가?"],
            ),
            Persona(
                id="demo",
                name="데모 설계자",
                role="발표 장면을 설계하는 역할",
                perspective="보이는 증거를 중시합니다.",
                priority_questions=["어떤 장면을 보여줄 것인가?"],
            ),
        ]
        supervisor = Supervisor(llm)
        supervisor.persona_generator = FixedPersonaGenerator(selected_personas)
        supervisor.moderator = FixedModerator()
        supervisor.specialist = TranscriptRecordingSpecialist()
        supervisor.critic = FixedCritic()
        supervisor.evaluator = PassingEvaluator()
        return supervisor

    def _recording_supervisor(self, memory_context: str, personas: list[Persona] | None = None) -> Supervisor:
        selected_personas = personas or [
            Persona(
                id="product",
                name="제품 전략가",
                role="MVP 범위를 정리하는 역할",
                perspective="가장 작은 검증 루프를 중시합니다.",
                priority_questions=["무엇을 먼저 검증할 것인가?"],
            ),
            Persona(
                id="systems",
                name="시스템 엔지니어",
                role="구현 가능성을 점검하는 역할",
                perspective="상태와 로그를 중시합니다.",
                priority_questions=["어디서 실패할 수 있는가?"],
            ),
            Persona(
                id="demo",
                name="데모 설계자",
                role="발표 장면을 설계하는 역할",
                perspective="보이는 증거를 중시합니다.",
                priority_questions=["어떤 장면을 보여줄 것인가?"],
            ),
        ]
        supervisor = Supervisor(LLMClient(enabled=False))
        supervisor.persona_generator = FixedPersonaGenerator(selected_personas)
        supervisor.moderator = FixedModerator()
        supervisor.specialist = TranscriptRecordingSpecialist()
        supervisor.critic = RecordingCritic()
        supervisor.synthesizer = RecordingSynthesizer()
        supervisor.evaluator = RecordingEvaluator()
        supervisor.memory_client = FakeMemoryClient(memory_context)
        return supervisor

    def test_specialist_refines_until_self_verification_passes(self):
        llm = FakeLLM(
            [
                LLMResult(content="너무 짧음", used_llm=True),
                LLMResult(content='{"score": 2, "issue": "구체적인 판단 기준이 부족합니다."}', used_llm=True),
                LLMResult(
                    content="먼저 예산 기준을 고정하는 쪽이 좋습니다. 데모 안정성을 해치지 않는 범위에서 기능을 줄이고, 발표에서 보일 한 장면을 먼저 정해야 합니다.",
                    used_llm=True,
                ),
                LLMResult(content='{"score": 5, "issue": ""}', used_llm=True),
            ]
        )
        specialist = SpecialistAgent(llm)
        persona = Persona(
            id="budget",
            name="예산 관리자",
            role="비용과 구매 우선순위를 조정하는 역할",
            perspective="예산, 부품 비용, 지출 순서를 먼저 좁힙니다.",
            priority_questions=["얼마까지 쓸 수 있는가?"],
        )

        message = specialist.answer("2주 안에 보여줄 AI 프로젝트 MVP를 정해야 한다.", persona)

        verification = message.metadata["self_verification"]
        self.assertIn("발표에서 보일 한 장면", message.content)
        self.assertEqual(2, verification["attempts"])
        self.assertEqual(5, verification["score"])
        self.assertTrue(verification["passed"])
        self.assertIn("기준 미달 이유", llm.calls[2]["user_prompt"])

    def test_specialist_prompt_varies_opening_rhythm_by_persona(self):
        llm = FakeLLM(
            [
                LLMResult(content="첫 사용자를 기준으로 범위를 줄이는 편이 좋습니다. 바로 검증할 장면이 선명해집니다.", used_llm=True),
                LLMResult(content='{"score": 5, "issue": ""}', used_llm=True),
                LLMResult(content="구현 위험을 먼저 줄이는 편이 안전합니다. 작은 흐름부터 끝까지 확인해야 합니다.", used_llm=True),
                LLMResult(content='{"score": 5, "issue": ""}', used_llm=True),
            ]
        )
        specialist = SpecialistAgent(llm)
        first = Persona(
            id="product_strategist",
            name="제품 전략가",
            role="MVP 범위를 정리하는 역할",
            perspective="작은 데모로 가치를 증명합니다.",
            priority_questions=["첫 사용자는 누구인가?"],
        )
        second = Persona(
            id="systems_engineer",
            name="시스템 엔지니어",
            role="아키텍처 안정성을 검토하는 역할",
            perspective="실패 지점을 먼저 봅니다.",
            priority_questions=["어디서 실패하는가?"],
        )

        specialist.answer("3주 안에 AI MVP를 만들어야 한다.", first)
        specialist.answer("3주 안에 AI MVP를 만들어야 한다.", second)

        first_prompt = llm.calls[0]["user_prompt"]
        second_prompt = llm.calls[2]["user_prompt"]

        self.assertIn("첫 문장 리듬:", first_prompt)
        self.assertIn("첫 문장 리듬:", second_prompt)
        self.assertIn(SpecialistAgent.REPEATED_OPENERS, first_prompt)
        self.assertNotIn("예:", first_prompt)
        self.assertNotIn("예:", second_prompt)
        self.assertIn("그대로 복사하지 말고", first_prompt)
        self.assertNotEqual(
            specialist._opening_guide(first),
            specialist._opening_guide(second),
        )

    def test_specialist_fallback_openings_avoid_repeated_demo_phrases(self):
        specialist = SpecialistAgent(LLMClient(enabled=False))
        personas = [
            Persona(
                id="product_strategist",
                name="제품 전략가",
                role="MVP 범위를 정리하는 역할",
                perspective="작은 데모로 가치를 증명합니다.",
                priority_questions=["첫 사용자는 누구인가?"],
            ),
            Persona(
                id="systems_engineer",
                name="시스템 엔지니어",
                role="아키텍처 안정성을 검토하는 역할",
                perspective="실패 지점을 먼저 봅니다.",
                priority_questions=["어디서 실패하는가?"],
            ),
            Persona(
                id="risk_guardian",
                name="리스크 관리자",
                role="위험과 실패 조건을 점검하는 역할",
                perspective="시연 중 깨질 수 있는 조건을 먼저 봅니다.",
                priority_questions=["무엇이 깨질 수 있는가?"],
            ),
            Persona(
                id="demo_director",
                name="데모 연출가",
                role="발표와 데모 흐름을 조율하는 역할",
                perspective="청중이 바로 이해할 장면을 중시합니다.",
                priority_questions=["어떤 장면을 먼저 보여줄 것인가?"],
            ),
            Persona(
                id="ai_researcher",
                name="AI 검증가",
                role="평가 기준과 품질을 확인하는 역할",
                perspective="답변 품질과 검증 가능성을 봅니다.",
                priority_questions=["어떻게 검증할 것인가?"],
            ),
        ]
        forbidden_openers = (
            "지금은",
            "완성도보다",
            "기능을 줄이는 쪽",
            "성공 기준은",
            "가장 큰 위험은",
        )

        openings = [
            specialist._fallback_opening(persona, persona.priority_questions[0])
            for persona in personas
        ]

        self.assertTrue(all(not opening.startswith(forbidden_openers) for opening in openings))

    def test_evaluator_reverse_verification_parses_llm_feedback(self):
        llm = FakeLLM(
            [
                LLMResult(
                    content="""{
                        "score": 2,
                        "missing_points": ["선픽 기준이 빠졌습니다."],
                        "unsupported_points": ["토론에 없던 추천을 추가했습니다."],
                        "style_issues": ["후속 제안 문장이 있습니다."],
                        "needs_extra_round": true,
                        "refine_instruction": "선픽 기준과 근거를 다시 확인하세요."
                    }""",
                    used_llm=True,
                )
            ]
        )
        evaluator = EvaluatorAgent(llm)
        debate = [
            AgentMessage(
                stage="debate",
                agent_id="top",
                agent_name="탑 코치",
                role="챔피언 선택 기준을 제시하는 역할",
                content="선픽이면 말파이트보다 오른이 안정적입니다.",
            )
        ]
        critique = AgentMessage(
            stage="critic",
            agent_id="critic",
            agent_name="비판 에이전트",
            role="누락을 찾는 역할",
            content="선픽 기준이 빠지면 결론이 약해질 수 있습니다.",
        )
        synthesis = AgentMessage(
            stage="synthesizer",
            agent_id="synthesizer",
            agent_name="종합 에이전트",
            role="최종 정리",
            content="가렌을 추천합니다.",
        )

        verification = evaluator.reverse_verify("탑 챔피언을 선픽 기준으로 추천해줘.", debate, critique, synthesis)

        self.assertEqual(2, verification["score"])
        self.assertFalse(verification["passed"])
        self.assertTrue(verification["needs_extra_round"])
        self.assertIn("선픽 기준이 빠졌습니다.", verification["missing_points"])
        self.assertEqual("llm", verification["source"])

    def test_evaluation_system_can_trigger_one_extra_round(self):
        supervisor = Supervisor(LLMClient(enabled=False))
        evaluator = ExtraRoundEvaluator()
        supervisor.evaluator = evaluator

        events = list(
            supervisor.solve_stream(
                problem="탑 챔피언을 선픽 기준과 초보자 기준으로 추천해줘.",
                persona_count=3,
                debate_rounds=1,
                search_mode="off",
            )
        )

        response = events[-1]["response"]
        extra_round_messages = [
            message
            for message in response.messages
            if message.stage == "debate"
            and message.metadata.get("phase") == "evaluation_extra_round"
        ]
        final_message = [message for message in response.messages if message.stage == "synthesizer"][-1]

        self.assertEqual(2, evaluator.reverse_calls)
        self.assertEqual(3, len(extra_round_messages))
        self.assertTrue(final_message.metadata["extra_round_used"])
        self.assertEqual(2, len(final_message.metadata["quality_check_history"]))
        self.assertTrue(response.evaluation.metadata["quality_check"]["passed"])


if __name__ == "__main__":
    unittest.main()
