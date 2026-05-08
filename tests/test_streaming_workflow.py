import unittest

from app.agents.specialist import SpecialistAgent
from app.agents.synthesizer import SynthesizerAgent
from app.llm import LLMResult
from app.schemas import Persona
from app.workflow import continue_discussion_stream, solve_problem_stream


class FakeLLM:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

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


class StreamingWorkflowTest(unittest.TestCase):
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
        persona_messages = [
            message
            for message in response.messages
            if message.stage in {"specialist", "debate"}
        ]
        self.assertTrue(
            all("self_verification" in message.metadata for message in persona_messages)
        )

    def test_solve_stream_adds_stance_debate_and_judge(self):
        events = list(
            solve_problem_stream(
                problem="2주 안에 보여줄 AI 프로젝트 MVP를 정해야 한다.",
                persona_count=3,
                debate_rounds=1,
                use_llm=False,
            )
        )

        response = events[-1]["response"]
        debate_messages = [message for message in response.messages if message.stage == "debate"]
        judge_messages = [message for message in response.messages if message.stage == "judge"]
        stances = {message.metadata.get("stance") for message in debate_messages}

        self.assertIn("support", stances)
        self.assertIn("opposition", stances)
        self.assertEqual(1, len(judge_messages))
        self.assertEqual(1, judge_messages[0].metadata.get("round"))

    def test_fallback_final_answer_is_balanced_but_keeps_critic(self):
        events = list(
            solve_problem_stream(
                problem="2주 안에 보여줄 AI 프로젝트 MVP를 정해야 한다.",
                persona_count=3,
                debate_rounds=1,
                use_llm=False,
            )
        )

        response = events[-1]["response"]
        final_lines = [line for line in response.final_answer.splitlines() if line.strip()]
        critic_messages = [message for message in response.messages if message.stage == "critic"]

        self.assertGreaterEqual(len(final_lines), 9)
        self.assertLessEqual(len(final_lines), 13)
        self.assertIn("1. 최종 판단", response.final_answer)
        self.assertIn("2. 실행 순서", response.final_answer)
        self.assertIn("3. 주의할 점", response.final_answer)
        self.assertEqual(1, len(critic_messages))

        final_message = [message for message in response.messages if message.stage == "synthesizer"][-1]
        self.assertEqual("moderator_summary", final_message.agent_id)
        self.assertEqual("사회자 에이전트", final_message.agent_name)

    def test_synthesizer_removes_followup_offer_lines(self):
        synthesizer = SynthesizerAgent.__new__(SynthesizerAgent)
        cleaned = synthesizer._clean_final_answer(
            """1. 최종 판단
지금은 말파이트보다 가렌이 더 단순합니다.
원하면 내가 바로 이어서 선픽용 / 후픽용 / 초보용으로 탑 챔프 3개씩 정리해줄게.
2. 실행 순서
- 가렌을 먼저 써보고 답답하면 말파이트로 바꿉니다."""
        )

        self.assertNotIn("원하면", cleaned)
        self.assertNotIn("정리해줄게", cleaned)
        self.assertIn("1. 최종 판단", cleaned)
        self.assertIn("2. 실행 순서", cleaned)

    def test_specialist_refines_until_self_verification_passes(self):
        llm = FakeLLM(
            [
                LLMResult(content="너무 짧음", used_llm=True),
                LLMResult(content='{"score": 2, "issue": "구체적인 판단 기준이 부족합니다."}', used_llm=True),
                LLMResult(
                    content="먼저 예산 기준을 고정하는 쪽이 좋습니다. 데모 안정성을 해치지 않는 범위에서 기능을 줄이고, 발표에서 보일 한 장면을 먼저 정해야 합니다.",
                    used_llm=True,
                ),
                LLMResult(content='{"score": 3, "issue": "실행 기준은 좋지만 선택 기준이 더 필요합니다."}', used_llm=True),
                LLMResult(
                    content="먼저 예산 기준과 발표 장면을 함께 고정하는 쪽이 좋습니다. 기능은 줄이되 데모 안정성을 해치지 않는 범위에서 핵심 화면 하나를 정하고, 실패하면 바로 보여줄 폴백 흐름까지 같이 준비해야 합니다.",
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
        self.assertIn("폴백 흐름", message.content)
        self.assertEqual(3, verification["attempts"])
        self.assertEqual(5, verification["score"])
        self.assertTrue(verification["passed"])
        self.assertIn("기준 미달 이유", llm.calls[2]["user_prompt"])
        self.assertIn("기준 미달 이유", llm.calls[4]["user_prompt"])

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


if __name__ == "__main__":
    unittest.main()
