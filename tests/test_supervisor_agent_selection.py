import unittest

from app.agents.supervisor import Supervisor
from app.schemas import Persona


class SupervisorAgentSelectionTest(unittest.TestCase):
    def setUp(self):
        self.supervisor = Supervisor.__new__(Supervisor)
        self.personas = [
            Persona(
                id="demo",
                name="데모 설계자",
                role="발표 장면과 시연 흐름을 설계하는 역할",
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
            Persona(
                id="user",
                name="사용자 관찰자",
                role="사용자 반응과 불편을 살피는 역할",
                perspective="실제 사용자의 행동과 피드백을 봅니다.",
                priority_questions=["사용자가 어디서 멈추는가?"],
            ),
        ]

    def test_user_content_selects_relevant_agents_first(self):
        selected = self.supervisor._select_reply_personas(
            personas=self.personas,
            user_content="예산은 100만 원 정도라 비용을 먼저 줄이고 싶어.",
            max_agents=2,
            round_number=1,
        )

        self.assertEqual("budget", selected[0].id)
        self.assertEqual(2, len(selected))

    def test_korean_topic_markers_do_not_hide_relevance(self):
        selected = self.supervisor._select_reply_personas(
            personas=self.personas,
            user_content="예산은 100만 원이야.",
            max_agents=1,
            round_number=1,
        )

        self.assertEqual(["budget"], [persona.id for persona in selected])

    def test_tie_break_rotates_by_round(self):
        selected = self.supervisor._select_reply_personas(
            personas=self.personas,
            user_content="아직 기준을 못 정했어.",
            max_agents=2,
            round_number=3,
        )

        self.assertEqual(["risk", "user"], [persona.id for persona in selected])


if __name__ == "__main__":
    unittest.main()
