from app.llm import LLMClient
from app.schemas import AgentMessage


class CriticAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def review(self, problem: str, specialist_messages: list[AgentMessage]) -> AgentMessage:
        transcript = "\n\n".join(
            f"[{message.agent_name} / {message.role}]\n{message.content}" for message in specialist_messages
        )
        prompt = f"""
Problem:
{problem}

Specialist opinions:
{transcript}

Review the discussion. Find contradictions, weak assumptions, missing constraints, and next questions.
Return a concise critique in Korean with:
1. 모순 또는 충돌
2. 약한 가정
3. 누락된 관점
4. 최종 통합 전에 고쳐야 할 점
"""
        result = self.llm.complete(
            system_prompt="You are a sharp but constructive critic in a multi-agent workflow.",
            user_prompt=prompt,
            temperature=0.2,
        )
        content = result.content if result.used_llm and result.content else self._fallback(specialist_messages)
        return AgentMessage(
            stage="critic",
            agent_id="critic",
            agent_name="Critic Agent",
            role="Finds contradictions, weak assumptions, and missing constraints",
            content=content,
            metadata={"source": "llm" if result.used_llm and result.content else "fallback", "error": result.error},
        )

    def _fallback(self, specialist_messages: list[AgentMessage]) -> str:
        names = ", ".join(message.agent_name for message in specialist_messages)
        return f"""1. 모순 또는 충돌
{names}의 의견은 대체로 MVP 축소에는 동의하지만, 품질을 높이려는 요구와 2주 일정 사이에 긴장이 있습니다.

2. 약한 가정
LLM 응답이 항상 구조화되어 나온다는 가정은 위험합니다. JSON 파싱 실패, 빈 응답, API 오류에 대비해야 합니다.

3. 누락된 관점
평가 기준이 없으면 다중 에이전트 구조가 실제로 더 나은지 설명하기 어렵습니다. 최소한 로그 완성도, 비판 품질, 최종 답변 일관성을 확인해야 합니다.

4. 최종 통합 전에 고쳐야 할 점
첫 버전은 에이전트 수, 모델명, API 사용 여부를 조절할 수 있어야 하고, 실패해도 데모가 이어져야 합니다."""
