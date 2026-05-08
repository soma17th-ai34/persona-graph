from app.llm import LLMClient
from app.schemas import AgentMessage


class CriticAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def review(self, problem: str, debate_messages: list[AgentMessage]) -> AgentMessage:
        transcript = "\n\n".join(
            f"[{message.agent_name} / {message.role}]\n{message.content}" for message in debate_messages
        )
        prompt = f"""
문제:
{problem}

토론 발언:
{transcript}

토론 전체를 검토하고 최종 종합에 꼭 반영해야 할 위험만 짧게 찾으세요.
반드시 자연스러운 한국어로 작성하고, 고유명사나 기술 약어 외에는 영어를 최소화하세요.
요구사항:
- 3개 불릿 이내로 작성하세요.
- 각 불릿은 한 문장으로 제한하세요.
- 사용자가 볼 보고서가 아니라 최종 종합 에이전트에게 전달할 내부 검토 메모처럼 작성하세요.
"""
        result = self.llm.complete(
            system_prompt="당신은 한국어 다중 에이전트 워크플로의 날카롭지만 건설적인 비판자입니다.",
            user_prompt=prompt,
            temperature=0.2,
        )
        content = result.content if result.used_llm and result.content else self._fallback(debate_messages)
        return AgentMessage(
            stage="critic",
            agent_id="critic",
            agent_name="비판 에이전트",
            role="모순, 약한 가정, 누락된 제약을 찾는 역할",
            content=content,
            metadata={"source": "llm" if result.used_llm and result.content else "fallback", "error": result.error},
        )

    def _fallback(self, debate_messages: list[AgentMessage]) -> str:
        names = ", ".join(
            dict.fromkeys(
                message.agent_name
                for message in debate_messages
                if message.stage in {"specialist", "debate"}
            )
        )
        return f"""- {names}의 의견은 대체로 MVP 축소에는 동의하지만, 품질 욕심과 2주 일정 사이의 긴장을 최종 결론에 반영해야 합니다.
- LLM 응답 실패, 빈 응답, JSON 파싱 실패가 있어도 데모가 이어지는 폴백 기준을 유지해야 합니다.
- 다중 에이전트 구조가 더 낫다는 점은 로그 완성도, 반박 품질, 최종 답변 일관성으로 보여줘야 합니다."""
