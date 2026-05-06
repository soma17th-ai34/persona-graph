import unittest

from app.workflow import continue_discussion_stream, solve_problem_stream


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
