from __future__ import annotations

from app.agents.supervisor import Supervisor
from app.llm import LLMClient
from app.schemas import SolveResponse
from app.terminal_logging import preview, terminal_log


def solve_problem(
    problem: str,
    persona_count: int = 5,
    debate_rounds: int = 1,
    use_llm: bool = True,
    model: str | None = None,
    search_mode: str = "auto",
    temperature: float = 0.35,
) -> SolveResponse:
    final_response = None
    for event in solve_problem_stream(
        problem=problem,
        persona_count=persona_count,
        debate_rounds=debate_rounds,
        use_llm=use_llm,
        model=model,
        search_mode=search_mode,
        temperature=temperature,
    ):
        if event["type"] == "final_response":
            final_response = event["response"]
    if final_response is None:
        raise RuntimeError("Solve stream ended without a final response.")
    return final_response


def solve_problem_stream(
    problem: str,
    persona_count: int = 5,
    debate_rounds: int = 1,
    use_llm: bool = True,
    model: str | None = None,
    search_mode: str = "auto",
    temperature: float = 0.35,
):
    llm = LLMClient(model=model, temperature=temperature, enabled=use_llm)
    supervisor = Supervisor(llm)
    terminal_log(
        "run_start",
        mode="initial",
        persona_count=persona_count,
        debate_rounds=debate_rounds,
        use_llm=use_llm,
        model=llm.model,
        search_mode=search_mode,
        search_enabled=supervisor.search_client.enabled,
        problem=problem,
    )
    try:
        yield from _log_stream_events(
            supervisor.solve_stream(
                problem=problem,
                persona_count=persona_count,
                debate_rounds=debate_rounds,
                search_mode=search_mode,
            )
        )
    except Exception as exc:
        terminal_log("run_error", error=type(exc).__name__, detail=str(exc))
        raise


def continue_discussion(
    response: SolveResponse,
    user_content: str,
    max_agents: int = 2,
    use_llm: bool = True,
    model: str | None = None,
    search_mode: str = "auto",
    temperature: float = 0.35,
) -> SolveResponse:
    final_response = None
    for event in continue_discussion_stream(
        response=response,
        user_content=user_content,
        max_agents=max_agents,
        use_llm=use_llm,
        model=model,
        search_mode=search_mode,
        temperature=temperature,
    ):
        if event["type"] == "final_response":
            final_response = event["response"]
    if final_response is None:
        raise RuntimeError("Discussion stream ended without a final response.")
    return final_response


def continue_discussion_stream(
    response: SolveResponse,
    user_content: str,
    max_agents: int = 2,
    use_llm: bool = True,
    model: str | None = None,
    search_mode: str = "auto",
    temperature: float = 0.35,
):
    llm = LLMClient(model=model, temperature=temperature, enabled=use_llm)
    supervisor = Supervisor(llm)
    terminal_log(
        "followup_start",
        run_id=response.run_id or "unsaved",
        max_agents=max_agents,
        use_llm=use_llm,
        model=llm.model,
        search_mode=search_mode,
        user_content=user_content,
    )
    try:
        yield from _log_stream_events(
            supervisor.continue_discussion_stream(
                response=response,
                user_content=user_content,
                max_agents=max_agents,
                search_mode=search_mode,
            )
        )
    except Exception as exc:
        terminal_log("followup_error", error=type(exc).__name__, detail=str(exc))
        raise


def _log_stream_events(events):
    for event in events:
        _log_stream_event(event)
        yield event


def _log_stream_event(event: dict[str, object]) -> None:
    event_type = str(event.get("type", "unknown"))
    if event_type == "personas_ready":
        personas = event.get("personas", [])
        terminal_log("personas_ready", count=len(personas) if hasattr(personas, "__len__") else "?")
        return
    if event_type == "agent_started":
        terminal_log(
            "agent_started",
            stage=event.get("stage"),
            agent=event.get("agent_name"),
            round=event.get("round"),
        )
        return
    if event_type == "agent_message":
        message = event.get("message")
        if message is None:
            terminal_log("agent_message", detail="missing_message")
            return
        terminal_log(
            "agent_message",
            stage=message.stage,
            agent=message.agent_name,
            round=message.metadata.get("round"),
            phase=message.metadata.get("phase"),
            chars=len(message.content),
            content=preview(message.content),
        )
        return
    if event_type == "final_response":
        response = event.get("response")
        if response is None:
            terminal_log("final_response", detail="missing_response")
            return
        terminal_log(
            "final_response",
            messages=len(response.messages),
            used_llm=response.used_llm,
            model=response.model,
            final_answer=preview(response.final_answer),
        )
        return
    terminal_log(event_type)
