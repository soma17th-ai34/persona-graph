from app.llm import LLMClient
from app.schemas import AgentMessage


class JudgeAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def evaluate_round(
        self,
        problem: str,
        round_messages: list[AgentMessage],
        round_number: int,
    ) -> AgentMessage:
        transcript = "\n\n".join(
            f"[{message.agent_name} / {message.role} / {self._stance_label(message)}]\n{message.content}"
            for message in round_messages
        )
        prompt = f"""
문제:
{problem}

이번 라운드 발언:
{transcript}

당신은 판사입니다. 찬성 측과 반대 측의 주장을 평가하고, 어느 쪽 주장이 더 설득력 있는지 결정하세요.
반드시 자연스러운 한국어로 작성하고, 고유명사나 기술 약어 외에는 영어를 최소화하세요.
요구사항:
- 양측의 가장 강한 논점을 각각 짚으세요.
- 한쪽만 이겼다고 단정하기보다, 최종 결론에 남길 조건을 분명히 하세요.
- 다음 라운드 또는 최종 종합에서 반드시 해결해야 할 쟁점을 1개 남기세요.
- 3~5문장으로 간결하게 작성하세요.
"""
        result = self.llm.complete(
            system_prompt="당신은 한국어 다중 에이전트 토론의 판사입니다. 양측 주장을 공정하게 비교하고 다음 판단 기준을 정하세요.",
            user_prompt=prompt,
            temperature=0.2,
        )
        content = (
            result.content
            if result.used_llm and result.content
            else self._fallback(round_messages, round_number)
        )
        return AgentMessage(
            stage="judge",
            agent_id="judge",
            agent_name="판사 에이전트",
            role="찬성 측과 반대 측의 주장을 비교하고 다음 판단 기준을 정하는 역할",
            content=content,
            metadata={
                "source": "llm" if result.used_llm and result.content else "fallback",
                "error": result.error,
                "round": round_number,
                "phase": "round_judgment",
            },
        )

    def _stance_label(self, message: AgentMessage) -> str:
        return {
            "support": "찬성 측",
            "opposition": "반대 측",
        }.get(str(message.metadata.get("stance", "")), "중립")

    def _fallback(self, round_messages: list[AgentMessage], round_number: int) -> str:
        support_names = self._names_by_stance(round_messages, "support")
        opposition_names = self._names_by_stance(round_messages, "opposition")
        return f"""{round_number}라운드 판정입니다. 찬성 측({support_names})은 현재 방향을 살릴 이유를 제시했고, 반대 측({opposition_names})은 실패 조건과 빠진 제약을 드러냈습니다.
이번 라운드에서는 반대 측의 제약 지적을 최종 결론에 반드시 반영하는 편이 더 안전합니다.
다만 찬성 측이 제시한 실행 가능성은 버리지 말고, 범위를 더 좁히는 조건으로 살려야 합니다.
다음 판단 기준은 이 선택이 데모 안정성과 설득력을 동시에 높이는지입니다."""

    def _names_by_stance(self, round_messages: list[AgentMessage], stance: str) -> str:
        names = [
            message.agent_name
            for message in round_messages
            if message.metadata.get("stance") == stance
        ]
        return ", ".join(names) if names else "없음"
