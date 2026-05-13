from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from app.run_memory import RunMemoryClient


class RunMemoryTest(unittest.TestCase):
    def setUp(self):
        self.previous_memory_dir = os.environ.get("PERSONA_GRAPH_MEMORY_RUNS_DIR")
        self.previous_runs_dir = os.environ.get("PERSONA_GRAPH_RUNS_DIR")
        self.tempdir = tempfile.TemporaryDirectory()
        self.memory_dir = Path(self.tempdir.name) / "memory_runs"
        os.environ["PERSONA_GRAPH_MEMORY_RUNS_DIR"] = str(self.memory_dir)

    def tearDown(self):
        if self.previous_memory_dir is None:
            os.environ.pop("PERSONA_GRAPH_MEMORY_RUNS_DIR", None)
        else:
            os.environ["PERSONA_GRAPH_MEMORY_RUNS_DIR"] = self.previous_memory_dir
        if self.previous_runs_dir is None:
            os.environ.pop("PERSONA_GRAPH_RUNS_DIR", None)
        else:
            os.environ["PERSONA_GRAPH_RUNS_DIR"] = self.previous_runs_dir
        self.tempdir.cleanup()

    def test_missing_or_empty_memory_dir_returns_empty_record(self):
        context, record = RunMemoryClient().build_context("Physical AI MVP 검증", "initial")

        self.assertIsNone(context)
        self.assertEqual("initial", record.phase)
        self.assertEqual("empty", record.status)
        self.assertEqual([], record.selected_run_ids)

        self.memory_dir.mkdir()

        context, record = RunMemoryClient().build_context("Physical AI MVP 검증", "initial")

        self.assertIsNone(context)
        self.assertEqual("empty", record.status)

    def test_selects_relevant_positive_and_negative_fixtures_only(self):
        self.memory_dir.mkdir()
        self._write_run(
            "20260513-010101-aaaaaaaa",
            problem="Physical AI MVP를 저예산으로 검증한다.",
            average=5,
            passed=True,
            overall_comment="결론, 근거, 실행 순서가 현재 제약에 맞게 압축되었습니다.",
        )
        self._write_run(
            "20260513-010102-bbbbbbbb",
            problem="Physical AI MVP 검증 장면을 정한다.",
            average=3,
            passed=False,
            missing_points=["예산 제약이 빠졌습니다."],
            unsupported_points=["근거 없이 하드웨어 구매를 전제했습니다."],
            style_issues=["답변이 길고 반복됩니다."],
        )
        self._write_run(
            "20260513-010103-cccccccc",
            problem="저녁 메뉴를 추천한다.",
            average=5,
            passed=True,
            overall_comment="메뉴 추천은 간결했습니다.",
        )
        self._write_run(
            "20260513-010104-dddddddd",
            problem="Physical AI 데모 발표 흐름을 정한다.",
            average=4,
            passed=True,
            overall_comment="발표 장면과 실패 조건이 균형 있게 정리되었습니다.",
        )
        self._write_run(
            "20260513-010105-eeeeeeee",
            problem="Physical AI 로봇 검증 로그를 남긴다.",
            average=4,
            passed=True,
            overall_comment="로그 기준이 잘 드러났습니다.",
        )
        (self.memory_dir / "broken.json").write_text("{", encoding="utf-8")

        context, record = RunMemoryClient().build_context("Physical AI MVP 검증을 하고 싶다.", "initial")

        self.assertEqual("selected", record.status)
        self.assertLessEqual(len(record.selected_run_ids), 3)
        self.assertNotIn("20260513-010103-cccccccc", record.selected_run_ids)
        self.assertGreaterEqual(record.positive_count, 1)
        self.assertGreaterEqual(record.negative_count, 1)
        self.assertIn("선별 품질 메모리", context)
        self.assertIn("좋은 예시에서 참고할 점", context)
        self.assertIn("피해야 할 실패 패턴", context)
        self.assertIn("근거 없이 하드웨어 구매", context)
        self.assertNotIn("최종 답변입니다", context)

    def test_broken_json_only_returns_error_record(self):
        self.memory_dir.mkdir()
        (self.memory_dir / "broken.json").write_text("{", encoding="utf-8")

        context, record = RunMemoryClient().build_context("Physical AI MVP 검증", "initial")

        self.assertIsNone(context)
        self.assertEqual("error", record.status)
        self.assertIn("broken.json", record.error)

    def test_loader_does_not_read_data_runs_directory(self):
        runs_dir = Path(self.tempdir.name) / "runs"
        runs_dir.mkdir()
        os.environ["PERSONA_GRAPH_RUNS_DIR"] = str(runs_dir)
        self._write_run(
            "20260513-020101-aaaaaaaa",
            problem="Physical AI MVP 검증을 data runs에만 둔다.",
            average=5,
            passed=True,
            directory=runs_dir,
        )
        self.memory_dir.mkdir()

        context, record = RunMemoryClient().build_context("Physical AI MVP 검증", "initial")

        self.assertIsNone(context)
        self.assertEqual("empty", record.status)

    def _write_run(
        self,
        run_id: str,
        problem: str,
        average: int,
        passed: bool,
        overall_comment: str = "테스트 평가입니다.",
        missing_points: list[str] | None = None,
        unsupported_points: list[str] | None = None,
        style_issues: list[str] | None = None,
        directory: Path | None = None,
    ) -> None:
        target = directory or self.memory_dir
        target.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run_id,
            "problem": problem,
            "personas": [],
            "messages": [],
            "final_answer": "최종 답변입니다. 이 문장은 메모리 context에 그대로 들어가면 안 됩니다.",
            "evaluation": {
                "consistency": average,
                "specificity": average,
                "risk_awareness": average,
                "feasibility": average,
                "overall_comment": overall_comment,
                "improvement_suggestions": [],
                "metadata": {
                    "quality_check": {
                        "passed": passed,
                        "missing_points": missing_points or [],
                        "unsupported_points": unsupported_points or [],
                        "style_issues": style_issues or [],
                    }
                },
            },
            "used_llm": True,
            "model": "test",
            "created_at": "2026-05-13T00:00:00",
        }
        (target / f"{run_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
