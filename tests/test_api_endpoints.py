import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.llm import LLMClient
from app.main import app


class APIEndpointTest(unittest.TestCase):
    def setUp(self):
        self.runs_dir = tempfile.TemporaryDirectory()
        self.previous_env = {
            key: os.environ.get(key)
            for key in (
                "PERSONA_GRAPH_RUNS_DIR",
                "PERSONA_GRAPH_MODEL",
                "PERSONA_GRAPH_AVAILABLE_MODELS",
                "PERSONA_GRAPH_DEFAULT_PROVIDER",
                "OPENAI_API_KEY",
                "OPENAI_BASE_URL",
                "UPSTAGE_API_KEY",
                "UPSTAGE_BASE_URL",
            )
        }
        os.environ["PERSONA_GRAPH_RUNS_DIR"] = self.runs_dir.name
        os.environ["PERSONA_GRAPH_MODEL"] = "openai:test-default"
        os.environ["PERSONA_GRAPH_AVAILABLE_MODELS"] = "openai:test-default,upstage:solar-pro3"
        self.client = TestClient(app)

    def tearDown(self):
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.runs_dir.cleanup()

    def test_models_endpoint_exposes_server_catalog(self):
        response = self.client.get("/models")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("openai:test-default", payload["default_model"])
        self.assertEqual(
            ["openai:test-default", "upstage:solar-pro3"],
            [model["id"] for model in payload["models"]],
        )
        self.assertEqual(
            ["OpenAI · test-default", "Upstage · solar-pro3"],
            [model["label"] for model in payload["models"]],
        )
        self.assertEqual(
            ["openai", "upstage"],
            [model["provider"] for model in payload["models"]],
        )

    def test_models_endpoint_includes_default_when_available_list_omits_it(self):
        os.environ["PERSONA_GRAPH_AVAILABLE_MODELS"] = "upstage:solar-pro3"

        response = self.client.get("/models")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            ["openai:test-default", "upstage:solar-pro3"],
            [model["id"] for model in response.json()["models"]],
        )

    def test_llm_client_routes_prefixed_upstage_model(self):
        os.environ["UPSTAGE_API_KEY"] = "test-upstage-key"
        os.environ.pop("OPENAI_API_KEY", None)

        client = LLMClient(model="upstage:solar-pro3", enabled=False)

        self.assertEqual("upstage:solar-pro3", client.model)
        self.assertEqual("solar-pro3", client.api_model)
        self.assertEqual("upstage", client.provider)
        self.assertEqual("test-upstage-key", client.api_key)
        self.assertEqual("https://api.upstage.ai/v1", client.base_url)

    def test_solve_stream_saves_selected_allowed_model(self):
        with self.client.stream(
            "POST",
            "/solve/stream",
            json={
                "problem": "2주 안에 보여줄 AI 프로젝트 MVP를 정해야 한다.",
                "persona_count": 3,
                "debate_rounds": 1,
                "use_llm": False,
                "model": "upstage:solar-pro3",
            },
        ) as response:
            self.assertEqual(200, response.status_code)
            events = self._read_events(response)

        self.assertEqual("final_response", events[-1]["type"])
        self.assertEqual("upstage:solar-pro3", events[-1]["response"]["model"])
        run_id = events[-1]["response"]["run_id"]

        detail = self.client.get(f"/runs/{run_id}")

        self.assertEqual(200, detail.status_code)
        self.assertEqual("upstage:solar-pro3", detail.json()["model"])

    def test_solve_rejects_unavailable_model(self):
        response = self.client.post(
            "/solve",
            json={
                "problem": "2주 안에 보여줄 AI 프로젝트 MVP를 정해야 한다.",
                "persona_count": 3,
                "debate_rounds": 1,
                "use_llm": False,
                "model": "unknown-model",
            },
        )

        self.assertEqual(422, response.status_code)
        self.assertIn("unknown-model", response.json()["detail"])

    def test_solve_stream_saves_final_response(self):
        with self.client.stream(
            "POST",
            "/solve/stream",
            json={
                "problem": "2주 안에 보여줄 AI 프로젝트 MVP를 정해야 한다.",
                "persona_count": 3,
                "debate_rounds": 1,
                "use_llm": False,
            },
        ) as response:
            self.assertEqual(200, response.status_code)
            self.assertEqual(
                "application/x-ndjson",
                response.headers["content-type"].split(";")[0],
            )
            events = self._read_events(response)

        self.assertIn("personas_ready", [event["type"] for event in events])
        self.assertEqual("final_response", events[-1]["type"])
        run_id = events[-1]["response"]["run_id"]

        detail = self.client.get(f"/runs/{run_id}")

        self.assertEqual(200, detail.status_code)
        self.assertEqual(run_id, detail.json()["run_id"])

    def test_followup_stream_loads_and_updates_saved_run(self):
        created = self.client.post(
            "/solve",
            json={
                "problem": "저예산 Physical AI 프로젝트를 검증하고 싶다.",
                "persona_count": 3,
                "debate_rounds": 1,
                "use_llm": False,
            },
        ).json()
        run_id = created["run_id"]

        with self.client.stream(
            "POST",
            f"/runs/{run_id}/messages/stream",
            json={
                "content": "예산은 100만 원이고 발표 장면이 중요하다.",
                "max_agents": 2,
                "use_llm": False,
            },
        ) as response:
            self.assertEqual(200, response.status_code)
            events = self._read_events(response)

        self.assertEqual("agent_message", events[0]["type"])
        self.assertEqual("user", events[0]["message"]["stage"])
        self.assertEqual("final_response", events[-1]["type"])
        self.assertEqual(run_id, events[-1]["response"]["run_id"])

        detail = self.client.get(f"/runs/{run_id}")

        self.assertEqual(200, detail.status_code)
        stages = [message["stage"] for message in detail.json()["messages"]]
        self.assertIn("user", stages)

    def test_followup_stream_uses_selected_allowed_model(self):
        created = self.client.post(
            "/solve",
            json={
                "problem": "저예산 Physical AI 프로젝트를 검증하고 싶다.",
                "persona_count": 3,
                "debate_rounds": 1,
                "use_llm": False,
            },
        ).json()
        run_id = created["run_id"]

        with self.client.stream(
            "POST",
            f"/runs/{run_id}/messages/stream",
            json={
                "content": "모델 선택이 저장되는지 확인하고 싶다.",
                "max_agents": 2,
                "use_llm": False,
                "model": "upstage:solar-pro3",
            },
        ) as response:
            self.assertEqual(200, response.status_code)
            events = self._read_events(response)

        self.assertEqual("final_response", events[-1]["type"])
        self.assertEqual("upstage:solar-pro3", events[-1]["response"]["model"])

        detail = self.client.get(f"/runs/{run_id}")

        self.assertEqual(200, detail.status_code)
        self.assertEqual("upstage:solar-pro3", detail.json()["model"])

    def _read_events(self, response):
        events = []
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            events.append(json.loads(line))
        return events


if __name__ == "__main__":
    unittest.main()
