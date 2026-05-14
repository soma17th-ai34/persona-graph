import unittest

from app.schemas import (
    AgentMessage,
    Evaluation,
    Persona,
    SearchQueryNode,
    SearchRecord,
    SolveResponse,
)
from ui.streamlit_chat import (
    chat_thread_items,
    moderator_message_html,
    moderator_summary,
    search_record_activity_item,
)


class StreamlitChatRenderingTest(unittest.TestCase):
    def test_moderator_summary_prefers_sentence_boundary(self):
        content = (
            "이번 라운드에서는 이전 발언의 충돌 지점을 먼저 좁히겠습니다. "
            "각 Agent는 새 아이디어를 늘리기보다 하나의 주장에 직접 반응해야 합니다. "
            "마지막에는 다음 결정에 필요한 조건만 남기겠습니다."
        )

        self.assertEqual(
            "이번 라운드에서는 이전 발언의 충돌 지점을 먼저 좁히겠습니다.",
            moderator_summary(content, max_length=80),
        )

    def test_moderator_message_html_keeps_full_text_collapsible(self):
        content = (
            "이번 라운드에서는 이전 발언의 충돌 지점을 먼저 좁히겠습니다. "
            "각 Agent는 새 아이디어를 늘리기보다 하나의 주장에 직접 반응해야 합니다. "
            "마지막에는 다음 결정에 필요한 조건만 남기겠습니다."
        )

        markup = moderator_message_html(content)

        self.assertIn("pg-moderator-preview", markup)
        self.assertIn("전문 보기", markup)
        self.assertIn("각 Agent는 새 아이디어", markup)

    def test_search_records_are_inserted_at_conversation_positions(self):
        response = SolveResponse(
            problem="검색 위치를 확인한다.",
            personas=[
                Persona(
                    id="demo",
                    name="데모 설계자",
                    role="데모 흐름을 보는 역할",
                    perspective="보이는 흐름을 중시합니다.",
                )
            ],
            messages=[
                AgentMessage(
                    stage="moderator",
                    agent_id="moderator",
                    agent_name="사회자 에이전트",
                    role="진행자",
                    content="opening",
                    metadata={"phase": "opening"},
                ),
                AgentMessage(
                    stage="moderator",
                    agent_id="moderator",
                    agent_name="사회자 에이전트",
                    role="진행자",
                    content="round one",
                    metadata={"phase": "response_round", "round": 1},
                ),
                AgentMessage(
                    stage="debate",
                    agent_id="demo",
                    agent_name="데모 설계자",
                    role="데모 흐름을 보는 역할",
                    content="round one reply",
                    metadata={"round": 1},
                ),
                AgentMessage(
                    stage="user",
                    agent_id="user",
                    agent_name="현재",
                    role="사용자",
                    content="후속 의견",
                    metadata={"round": 2},
                ),
                AgentMessage(
                    stage="debate",
                    agent_id="demo",
                    agent_name="데모 설계자",
                    role="데모 흐름을 보는 역할",
                    content="followup reply",
                    metadata={"phase": "user_response", "round": 2},
                ),
            ],
            final_answer="final",
            evaluation=Evaluation(
                consistency=5,
                specificity=5,
                risk_awareness=5,
                feasibility=5,
                overall_comment="ok",
            ),
            search_records=[
                SearchRecord(
                    phase="initial",
                    mode="auto",
                    enabled=True,
                    needed=True,
                    status="fetched",
                    queries=["초기 검색"],
                ),
                SearchRecord(
                    phase="debate_round",
                    round_number=1,
                    mode="auto",
                    enabled=True,
                    needed=True,
                    status="fetched",
                    queries=["라운드 검색"],
                ),
                SearchRecord(
                    phase="followup",
                    mode="auto",
                    enabled=True,
                    needed=True,
                    status="fetched",
                    queries=["후속 검색"],
                ),
            ],
            used_llm=False,
            model="test",
        )

        items = chat_thread_items(response)
        initial_search_index = self._activity_index(items, "initial")
        debate_search_index = self._activity_index(items, "debate_round")
        followup_search_index = self._activity_index(items, "followup")
        round_moderator_index = self._content_index(items, "round one")
        user_index = self._content_index(items, "후속 의견")
        followup_reply_index = self._content_index(items, "followup reply")

        self.assertGreater(initial_search_index, 0)
        self.assertLess(debate_search_index, round_moderator_index)
        self.assertGreater(followup_search_index, user_index)
        self.assertLess(followup_search_index, followup_reply_index)

    def test_search_activity_summary_uses_root_queries_without_tree_details(self):
        item = search_record_activity_item(
            SearchRecord(
                phase="debate_round",
                round_number=1,
                mode="auto",
                enabled=True,
                needed=True,
                status="fetched",
                queries=["root query", "child query"],
                query_tree=[
                    SearchQueryNode(
                        query="root query",
                        result_count=2,
                        status="fetched",
                        children=[
                            SearchQueryNode(
                                query="child query",
                                result_count=1,
                                status="fetched",
                            )
                        ],
                    )
                ],
                result_count=3,
            )
        )

        self.assertEqual(2, item["query_count"])
        self.assertEqual(["root query"], item["root_queries"])

    def _activity_index(self, items: list[dict], phase: str) -> int:
        return next(
            index
            for index, item in enumerate(items)
            if item.get("kind") == "activity" and item.get("phase") == phase
        )

    def _content_index(self, items: list[dict], content: str) -> int:
        return next(index for index, item in enumerate(items) if item.get("content") == content)
