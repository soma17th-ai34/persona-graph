from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.schemas import (
    AgentMessage,
    ContinueRequest,
    ModelCatalogResponse,
    Persona,
    RunSummary,
    SolveRequest,
    SolveResponse,
)


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


class PersonaGraphAPIError(RuntimeError):
    pass


def api_base_url() -> str:
    return os.getenv("PERSONA_GRAPH_API_URL", DEFAULT_API_BASE_URL).rstrip("/")


def list_run_summaries() -> list[RunSummary]:
    payload = _json_request("GET", "/runs")
    return [RunSummary.model_validate(item) for item in payload]


def load_run_detail(run_id: str) -> SolveResponse:
    return SolveResponse.model_validate(_json_request("GET", f"/runs/{run_id}"))


def load_model_catalog() -> ModelCatalogResponse:
    return ModelCatalogResponse.model_validate(_json_request("GET", "/models"))


def stream_solve_problem(
    *,
    problem: str,
    persona_count: int,
    debate_rounds: int,
    use_llm: bool,
    model: str | None,
    temperature: float,
):
    request = SolveRequest(
        problem=problem,
        persona_count=persona_count,
        debate_rounds=debate_rounds,
        use_llm=use_llm,
        model=model,
        temperature=temperature,
    )
    yield from _stream_request("/solve/stream", request.model_dump(mode="json"))


def stream_continue_discussion(
    *,
    run_id: str,
    content: str,
    max_agents: int,
    use_llm: bool,
    model: str | None,
    temperature: float,
):
    request = ContinueRequest(
        content=content,
        max_agents=max_agents,
        use_llm=use_llm,
        model=model,
        temperature=temperature,
    )
    yield from _stream_request(
        f"/runs/{run_id}/messages/stream",
        request.model_dump(mode="json"),
    )


def _json_request(method: str, path: str, payload: dict[str, Any] | None = None):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        _url(path),
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=_timeout_seconds()) as response:
            body = response.read()
    except HTTPError as exc:
        raise PersonaGraphAPIError(_http_error_message(exc)) from exc
    except URLError as exc:
        raise PersonaGraphAPIError(f"백엔드에 연결할 수 없습니다: {exc.reason}") from exc

    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _stream_request(path: str, payload: dict[str, Any]):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        _url(path),
        data=data,
        headers={
            "Accept": "application/x-ndjson",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=_timeout_seconds()) as response:
            while True:
                line = response.readline()
                if not line:
                    break
                decoded = line.decode("utf-8").strip()
                if decoded:
                    yield _parse_stream_event(json.loads(decoded))
    except HTTPError as exc:
        raise PersonaGraphAPIError(_http_error_message(exc)) from exc
    except URLError as exc:
        raise PersonaGraphAPIError(f"백엔드에 연결할 수 없습니다: {exc.reason}") from exc


def _parse_stream_event(event: dict[str, Any]) -> dict[str, Any]:
    event_type = event.get("type")
    if event_type == "personas_ready":
        event["personas"] = [Persona.model_validate(item) for item in event.get("personas", [])]
    elif event_type == "agent_message" and event.get("message") is not None:
        event["message"] = AgentMessage.model_validate(event["message"])
    elif event_type == "final_response" and event.get("response") is not None:
        event["response"] = SolveResponse.model_validate(event["response"])
    return event


def _http_error_message(exc: HTTPError) -> str:
    body = exc.read().decode("utf-8", errors="replace")
    try:
        detail = json.loads(body).get("detail")
    except json.JSONDecodeError:
        detail = body
    if detail:
        return f"백엔드 요청 실패 ({exc.code}): {detail}"
    return f"백엔드 요청 실패 ({exc.code})"


def _timeout_seconds() -> float:
    return float(os.getenv("PERSONA_GRAPH_API_TIMEOUT", "300"))


def _url(path: str) -> str:
    return f"{api_base_url()}{path}"
