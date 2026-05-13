from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.schemas import MemoryRecord, SolveResponse
from app.terminal_logging import terminal_log


MEMORY_RUNS_ENV = "PERSONA_GRAPH_MEMORY_RUNS_DIR"
MAX_SELECTED_RUNS = 3
QUALITY_THRESHOLD = 4.0
CONTEXT_LIMIT = 1800


@dataclass
class MemoryExample:
    run_id: str
    problem: str
    average_score: float
    positive: bool
    relevance: int
    overall_comment: str
    missing_points: list[str]
    unsupported_points: list[str]
    style_issues: list[str]


class RunMemoryClient:
    def build_context(self, problem: str, phase: str) -> tuple[str | None, MemoryRecord]:
        normalized_phase = "followup" if phase == "followup" else "initial"
        directory = memory_runs_dir()
        if not directory.exists():
            return self._empty_record(normalized_phase)

        files = sorted(directory.glob("*.json"), reverse=True)
        if not files:
            return self._empty_record(normalized_phase)

        query_terms = _keyword_terms(problem)
        examples: list[MemoryExample] = []
        errors: list[str] = []
        for path in files:
            try:
                example = self._load_example(path, query_terms)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{path.name}: {exc}")
                continue
            if example is not None:
                examples.append(example)

        selected = self._select_examples(examples)
        if not selected:
            if errors and len(errors) == len(files):
                return (
                    None,
                    MemoryRecord(
                        phase=normalized_phase,
                        enabled=True,
                        status="error",
                        error="; ".join(errors[:3]),
                    ),
                )
            return self._empty_record(normalized_phase)

        context = self._format_context(selected)
        positive_count = sum(1 for example in selected if example.positive)
        negative_count = len(selected) - positive_count
        record = MemoryRecord(
            phase=normalized_phase,
            enabled=True,
            status="selected",
            selected_run_ids=[example.run_id for example in selected],
            positive_count=positive_count,
            negative_count=negative_count,
            context=context,
            error="; ".join(errors[:3]) if errors else None,
        )
        terminal_log(
            "memory_selected",
            phase=normalized_phase,
            selected=len(selected),
            positive=positive_count,
            negative=negative_count,
        )
        return context, record

    def _load_example(self, path: Path, query_terms: set[str]) -> MemoryExample | None:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get("run_id"):
            data["run_id"] = path.stem
        run = SolveResponse.model_validate(data)
        relevance = self._relevance(query_terms, run)
        if relevance <= 0:
            return None

        quality_check = _latest_quality_check(run)
        missing_points = _string_list(quality_check.get("missing_points"))
        unsupported_points = _string_list(quality_check.get("unsupported_points"))
        style_issues = _string_list(quality_check.get("style_issues"))
        average_score = _average_score(run)
        quality_passed = quality_check.get("passed")
        positive = average_score >= QUALITY_THRESHOLD and quality_passed is not False
        if missing_points or unsupported_points:
            positive = False

        return MemoryExample(
            run_id=run.run_id or path.stem,
            problem=run.problem,
            average_score=average_score,
            positive=positive,
            relevance=relevance,
            overall_comment=run.evaluation.overall_comment,
            missing_points=missing_points,
            unsupported_points=unsupported_points,
            style_issues=style_issues,
        )

    def _select_examples(self, examples: list[MemoryExample]) -> list[MemoryExample]:
        return sorted(
            examples,
            key=lambda example: (
                -example.relevance,
                0 if example.positive else 1,
                -example.average_score,
                example.run_id,
            ),
        )[:MAX_SELECTED_RUNS]

    def _format_context(self, examples: list[MemoryExample]) -> str:
        positives = [example for example in examples if example.positive]
        negatives = [example for example in examples if not example.positive]
        lines = [
            "선별 품질 메모리입니다. 과거 답변 문장을 복사하지 말고, 현재 문제와 토론/검색 근거를 우선하세요.",
        ]
        if positives:
            lines.append("좋은 예시에서 참고할 점:")
            for example in positives:
                lines.append(
                    f"- {example.run_id}: 문제 유형 '{_preview(example.problem)}', "
                    f"평균 {example.average_score:.2f}. {_preview(example.overall_comment, 100)}"
                )
        if negatives:
            lines.append("피해야 할 실패 패턴:")
            for example in negatives:
                issue = self._issue_summary(example)
                lines.append(f"- {example.run_id}: 문제 유형 '{_preview(example.problem)}'. {issue}")
        context = "\n".join(lines).strip()
        if len(context) <= CONTEXT_LIMIT:
            return context
        return context[: CONTEXT_LIMIT - 1].rstrip() + "..."

    def _issue_summary(self, example: MemoryExample) -> str:
        issues = []
        if example.missing_points:
            issues.append(f"누락: {_preview('; '.join(example.missing_points[:2]), 160)}")
        if example.unsupported_points:
            issues.append(f"근거 없음: {_preview('; '.join(example.unsupported_points[:2]), 160)}")
        if example.style_issues:
            issues.append(f"문체: {_preview('; '.join(example.style_issues[:2]), 120)}")
        if not issues:
            issues.append(f"평균 점수 {example.average_score:.2f}로 품질 기준 미달")
        return " / ".join(issues)

    def _relevance(self, query_terms: set[str], run: SolveResponse) -> int:
        if not query_terms:
            return 0
        profile = " ".join(
            [
                run.problem,
                run.final_answer,
                run.evaluation.overall_comment,
            ]
        )
        profile_terms = _keyword_terms(profile)
        profile_text = _normalized_text(profile)
        score = len(query_terms & profile_terms) * 2
        score += sum(1 for term in query_terms if len(term) >= 2 and term in profile_text)
        return score

    def _empty_record(self, phase: str) -> tuple[str | None, MemoryRecord]:
        terminal_log("memory_skip", phase=phase, reason="empty")
        return (
            None,
            MemoryRecord(
                phase="followup" if phase == "followup" else "initial",
                enabled=True,
                status="empty",
            ),
        )


def memory_runs_dir() -> Path:
    configured = os.getenv(MEMORY_RUNS_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "data" / "memory_runs"


def _latest_quality_check(run: SolveResponse) -> dict[str, object]:
    metadata = run.evaluation.metadata
    quality_check = metadata.get("quality_check")
    if isinstance(quality_check, dict):
        return quality_check
    history = metadata.get("quality_check_history")
    if isinstance(history, list):
        for item in reversed(history):
            if isinstance(item, dict):
                return item
    return {}


def _average_score(run: SolveResponse) -> float:
    evaluation = run.evaluation
    return (
        evaluation.consistency
        + evaluation.specificity
        + evaluation.risk_awareness
        + evaluation.feasibility
    ) / 4


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:4]


def _keyword_terms(text: str) -> set[str]:
    normalized = _normalized_text(text)
    terms = set(re.findall(r"[0-9a-z가-힣]{2,}", normalized))
    return {term for term in terms if not term.isdigit()}


def _normalized_text(text: str) -> str:
    return "".join(character.lower() if character.isalnum() else " " for character in text)


def _preview(text: str, max_length: int = 80) -> str:
    collapsed = " ".join(str(text).split())
    if len(collapsed) <= max_length:
        return collapsed
    return f"{collapsed[: max_length - 1]}..."
