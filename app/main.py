from __future__ import annotations

import json
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.model_catalog import model_catalog, resolve_model
from app.schemas import ContinueRequest, ModelCatalogResponse, RunSummary, SolveRequest, SolveResponse
from app.storage import list_runs, load_run, save_run
from app.workflow import (
    continue_discussion,
    continue_discussion_stream,
    solve_problem,
    solve_problem_stream,
)


load_dotenv()

app = FastAPI(
    title="PersonaGraph API",
    description="Multi-agent persona debate and synthesis MVP.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "PersonaGraph"}


@app.get("/models", response_model=ModelCatalogResponse)
def models() -> ModelCatalogResponse:
    return model_catalog()


@app.post("/solve", response_model=SolveResponse)
def solve(request: SolveRequest) -> SolveResponse:
    model = _resolve_request_model(request.model)
    response = solve_problem(
        problem=request.problem,
        persona_count=request.persona_count,
        debate_rounds=request.debate_rounds,
        use_llm=request.use_llm,
        model=model,
        temperature=request.temperature,
    )
    return save_run(response)


@app.post("/solve/stream")
def solve_stream(request: SolveRequest) -> StreamingResponse:
    model = _resolve_request_model(request.model)
    return StreamingResponse(
        _stream_solve_events(request, model),
        media_type="application/x-ndjson",
    )


@app.get("/runs", response_model=list[RunSummary])
def runs() -> list[RunSummary]:
    return list_runs()


@app.get("/runs/{run_id}", response_model=SolveResponse)
def run_detail(run_id: str) -> SolveResponse:
    try:
        return load_run(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.post("/runs/{run_id}/messages", response_model=SolveResponse)
def continue_run(run_id: str, request: ContinueRequest) -> SolveResponse:
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content is required")
    model = _resolve_request_model(request.model)

    try:
        response = load_run(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found") from None

    updated = continue_discussion(
        response=response,
        user_content=content,
        max_agents=request.max_agents,
        use_llm=request.use_llm,
        model=model,
        temperature=request.temperature,
    )
    return save_run(updated)


@app.post("/runs/{run_id}/messages/stream")
def continue_run_stream(run_id: str, request: ContinueRequest) -> StreamingResponse:
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content is required")
    model = _resolve_request_model(request.model)

    try:
        response = load_run(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found") from None

    return StreamingResponse(
        _stream_followup_events(response, request, content, model),
        media_type="application/x-ndjson",
    )


def _stream_solve_events(request: SolveRequest, model: str):
    for event in solve_problem_stream(
        problem=request.problem,
        persona_count=request.persona_count,
        debate_rounds=request.debate_rounds,
        use_llm=request.use_llm,
        model=model,
        temperature=request.temperature,
    ):
        if event.get("type") == "final_response":
            event = dict(event)
            event["response"] = save_run(event["response"])
        yield _json_line(event)


def _stream_followup_events(
    response: SolveResponse,
    request: ContinueRequest,
    content: str,
    model: str,
):
    for event in continue_discussion_stream(
        response=response,
        user_content=content,
        max_agents=request.max_agents,
        use_llm=request.use_llm,
        model=model,
        temperature=request.temperature,
    ):
        if event.get("type") == "final_response":
            event = dict(event)
            event["response"] = save_run(event["response"])
        yield _json_line(event)


def _json_line(event: dict[str, Any]) -> str:
    return json.dumps(_serialize_event(event), ensure_ascii=False) + "\n"


def _resolve_request_model(model: str | None) -> str:
    try:
        return resolve_model(model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _serialize_event(event: dict[str, Any]) -> dict[str, Any]:
    return {key: _serialize_value(value) for key, value in event.items()}


def _serialize_value(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value
