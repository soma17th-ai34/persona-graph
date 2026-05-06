from __future__ import annotations

from app.agents.supervisor import Supervisor
from app.llm import LLMClient
from app.schemas import SolveResponse


def solve_problem(
    problem: str,
    persona_count: int = 5,
    debate_rounds: int = 1,
    use_llm: bool = True,
    model: str | None = None,
    temperature: float = 0.35,
) -> SolveResponse:
    llm = LLMClient(model=model, temperature=temperature, enabled=use_llm)
    supervisor = Supervisor(llm)
    return supervisor.solve(
        problem=problem,
        persona_count=persona_count,
        debate_rounds=debate_rounds,
    )


def solve_problem_stream(
    problem: str,
    persona_count: int = 5,
    debate_rounds: int = 1,
    use_llm: bool = True,
    model: str | None = None,
    temperature: float = 0.35,
):
    llm = LLMClient(model=model, temperature=temperature, enabled=use_llm)
    supervisor = Supervisor(llm)
    yield from supervisor.solve_stream(
        problem=problem,
        persona_count=persona_count,
        debate_rounds=debate_rounds,
    )


def continue_discussion(
    response: SolveResponse,
    user_content: str,
    max_agents: int = 2,
    use_llm: bool = True,
    model: str | None = None,
    temperature: float = 0.35,
) -> SolveResponse:
    llm = LLMClient(model=model, temperature=temperature, enabled=use_llm)
    supervisor = Supervisor(llm)
    return supervisor.continue_discussion(
        response=response,
        user_content=user_content,
        max_agents=max_agents,
    )


def continue_discussion_stream(
    response: SolveResponse,
    user_content: str,
    max_agents: int = 2,
    use_llm: bool = True,
    model: str | None = None,
    temperature: float = 0.35,
):
    llm = LLMClient(model=model, temperature=temperature, enabled=use_llm)
    supervisor = Supervisor(llm)
    yield from supervisor.continue_discussion_stream(
        response=response,
        user_content=user_content,
        max_agents=max_agents,
    )
