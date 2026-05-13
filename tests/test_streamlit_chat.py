import unittest

from ui.streamlit_chat import moderator_message_html, moderator_summary


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
