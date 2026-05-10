from __future__ import annotations

import json
import os
import re
from pathlib import Path
from uuid import uuid4

from app.schemas import RunSummary, SolveResponse
from app.terminal_logging import terminal_log


RUN_ID_PATTERN = re.compile(r"^[0-9]{8}-[0-9]{6}-[a-f0-9]{8}$")


def runs_dir() -> Path:
    configured = os.getenv("PERSONA_GRAPH_RUNS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "data" / "runs"


def save_run(response: SolveResponse) -> SolveResponse:
    directory = runs_dir()
    directory.mkdir(parents=True, exist_ok=True)

    run_id = response.run_id or _make_run_id(response)
    stored = response.model_copy(update={"run_id": run_id})
    path = directory / f"{run_id}.json"
    terminal_log(
        "run_save_start",
        run_id=run_id,
        messages=len(stored.messages),
        path=str(path),
    )
    payload = json.dumps(stored.model_dump(mode="json"), ensure_ascii=False, indent=2)
    terminal_log("run_save_serialized", run_id=run_id, bytes=len(payload.encode("utf-8")))
    path.write_text(payload, encoding="utf-8")
    terminal_log(
        "run_saved",
        run_id=run_id,
        messages=len(stored.messages),
        bytes=path.stat().st_size,
        path=str(path),
    )
    return stored


def list_runs(limit: int = 30) -> list[RunSummary]:
    directory = runs_dir()
    if not directory.exists():
        return []

    summaries: list[RunSummary] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        try:
            run = _load_path(path)
        except (OSError, ValueError):
            continue
        summaries.append(
            RunSummary(
                run_id=run.run_id or path.stem,
                problem_preview=_preview(run.problem),
                created_at=run.created_at,
                used_llm=run.used_llm,
                model=run.model,
                average_score=_average_score(run),
            )
        )
        if len(summaries) >= limit:
            break
    return summaries


def load_run(run_id: str) -> SolveResponse:
    if not RUN_ID_PATTERN.match(run_id):
        raise FileNotFoundError(run_id)

    path = runs_dir() / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(run_id)
    return _load_path(path)


def _load_path(path: Path) -> SolveResponse:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("run_id"):
        data["run_id"] = path.stem
    return SolveResponse.model_validate(data)


def _make_run_id(response: SolveResponse) -> str:
    timestamp = response.created_at.strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{uuid4().hex[:8]}"


def _preview(problem: str, max_length: int = 80) -> str:
    collapsed = " ".join(problem.split())
    if len(collapsed) <= max_length:
        return collapsed
    return f"{collapsed[: max_length - 1]}..."


def _average_score(response: SolveResponse) -> float:
    evaluation = response.evaluation
    total = (
        evaluation.consistency
        + evaluation.specificity
        + evaluation.risk_awareness
        + evaluation.feasibility
    )
    return round(total / 4, 2)
