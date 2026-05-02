from app.llm import LLMClient
from app.schemas import AgentMessage, Persona


class SpecialistAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def answer(self, problem: str, persona: Persona) -> AgentMessage:
        prompt = f"""
Problem:
{problem}

Persona:
- Name: {persona.name}
- Role: {persona.role}
- Perspective: {persona.perspective}
- Priority questions: {", ".join(persona.priority_questions)}

Write a practical opinion from this persona's point of view.
Use this structure:
1. 핵심 판단
2. 근거
3. 실행 제안
4. 주의할 점
Keep it concise and specific.
"""
        result = self.llm.complete(
            system_prompt="You are one specialist in a multi-agent problem-solving discussion.",
            user_prompt=prompt,
        )
        content = result.content if result.used_llm and result.content else self._fallback(problem, persona)
        return AgentMessage(
            stage="specialist",
            agent_id=persona.id,
            agent_name=persona.name,
            role=persona.role,
            content=content,
            metadata={"source": "llm" if result.used_llm and result.content else "fallback", "error": result.error},
        )

    def _fallback(self, problem: str, persona: Persona) -> str:
        questions = "\n".join(f"- {question}" for question in persona.priority_questions)
        return f"""1. 핵심 판단
{persona.name} 관점에서는 이 문제를 '{persona.perspective}' 기준으로 좁혀야 합니다.

2. 근거
현재 문제는 범위가 넓어질수록 구현보다 조율 비용이 커집니다. 먼저 한 번의 입력에서 관점, 비판, 종합이 끝까지 이어지는지 확인하는 것이 중요합니다.

3. 실행 제안
{questions}

4. 주의할 점
초기 MVP에서는 자동화 범위를 늘리기보다 로그 품질, 재현성, 실패 시 폴백을 우선해야 합니다."""
