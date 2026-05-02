from app.llm import LLMClient
from app.schemas import AgentMessage


class SynthesizerAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def synthesize(
        self,
        problem: str,
        specialist_messages: list[AgentMessage],
        critique: AgentMessage,
    ) -> AgentMessage:
        transcript = "\n\n".join(
            f"[{message.agent_name} / {message.role}]\n{message.content}" for message in specialist_messages
        )
        prompt = f"""
Problem:
{problem}

Specialist opinions:
{transcript}

Critique:
{critique.content}

Synthesize a final answer that resolves conflicts and turns the discussion into an actionable plan.
Write in Korean with:
1. 최종 결론
2. 선택한 방향
3. 실행 단계
4. 리스크와 대응
5. 다음 24시간 액션
"""
        result = self.llm.complete(
            system_prompt="You synthesize multi-agent debate into clear final decisions and next actions.",
            user_prompt=prompt,
            temperature=0.3,
        )
        content = result.content if result.used_llm and result.content else self._fallback(problem, critique)
        return AgentMessage(
            stage="synthesizer",
            agent_id="synthesizer",
            agent_name="Synthesizer Agent",
            role="Integrates the debate into a final answer",
            content=content,
            metadata={"source": "llm" if result.used_llm and result.content else "fallback", "error": result.error},
        )

    def _fallback(self, problem: str, critique: AgentMessage) -> str:
        return f"""1. 최종 결론
입력된 문제는 한 번에 거대한 자동화 시스템으로 만들기보다, 관점 생성 -> 역할별 의견 -> 비판 -> 종합이 안정적으로 보이는 MVP로 구현하는 것이 가장 좋습니다.

2. 선택한 방향
문제: {problem}

핵심 방향은 API 기반 LLM 호출을 사용하되, 실패 시에도 같은 형식의 결과가 나오는 폴백을 유지하는 것입니다.

3. 실행 단계
- 문제 입력 폼과 에이전트 수 설정을 만든다.
- Persona Generator가 3~5개 역할을 만든다.
- Specialist Agent들이 각자 의견을 낸다.
- Critic Agent가 모순, 약한 가정, 누락을 지적한다.
- Synthesizer Agent가 최종 결론과 다음 액션으로 정리한다.

4. 리스크와 대응
{critique.content}

5. 다음 24시간 액션
샘플 문제 3개로 로그가 끝까지 생성되는지 확인하고, 발표용으로 가장 설득력 있는 시나리오 하나를 고릅니다."""
