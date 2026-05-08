from app.llm import LLMClient
from app.schemas import AgentMessage


class SynthesizerAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def synthesize(
        self,
        problem: str,
        debate_messages: list[AgentMessage],
        critique: AgentMessage,
    ) -> AgentMessage:
        transcript = "\n\n".join(
            f"[{message.agent_name} / {message.role}]\n{message.content}" for message in debate_messages
        )
        prompt = f"""
문제:
{problem}

토론 발언:
{transcript}

비판:
{critique.content}

당신은 토론을 마무리하는 사회자입니다.
충돌을 정리하고 사용자가 아래로 읽어 내려간 뒤 자연스럽게 확인할 수 있는 최종 답변을 우리에게 알려주세요.
반드시 자연스러운 한국어로 작성하고, 고유명사나 기술 약어 외에는 영어를 최소화하세요.
다음 구조를 사용하세요.
1. 최종 판단
2. 실행 순서
3. 주의할 점

출력 규칙:
- 전체 9~13줄 정도로 작성하세요.
- 각 문단은 2문장을 넘기지 마세요.
- 실행 순서는 3~4개 불릿으로 작성하세요.
- 비판 내용을 그대로 길게 옮기지 말고 필요한 위험만 반영하세요.
- 판사, 비판 에이전트 같은 내부 Agent 이름은 최종 답변에 직접 쓰지 마세요.
- Markdown 제목 표시인 #, ##, ###를 쓰지 마세요.
- 굵은 글씨나 제목 크기 차이에 의존하지 말고 일반 문장과 불릿만 사용하세요.
- "원하면", "필요하면", "바로 이어서 해줄게" 같은 후속 제안 문장을 쓰지 마세요.
- 사용자가 추가 요청할 일을 제안하지 말고, 현재 질문에 대한 결론으로 끝내세요.
- 사회자가 토론을 마무리하며 알려주는 말투로 작성하되, "여러분" 같은 발표자 호칭은 쓰지 마세요.
- 너무 짧은 슬로건이나 너무 긴 보고서가 아니라, 발표 화면에서 한 번에 훑을 수 있는 길이로 작성하세요.
"""
        result = self.llm.complete(
            system_prompt="당신은 한국어 다중 에이전트 토론의 사회자입니다. 토론을 마무리하며 우리에게 최종 판단과 다음 행동을 정리해 주세요.",
            user_prompt=prompt,
            temperature=0.3,
        )
        content = result.content if result.used_llm and result.content else self._fallback(problem, critique)
        content = self._clean_final_answer(content)
        return AgentMessage(
            stage="synthesizer",
            agent_id="moderator_summary",
            agent_name="사회자 에이전트",
            role="토론을 마무리하고 최종 정리를 전달하는 역할",
            content=content,
            metadata={"source": "llm" if result.used_llm and result.content else "fallback", "error": result.error},
        )

    def _fallback(self, problem: str, critique: AgentMessage) -> str:
        return f"""1. 최종 판단
이번 토론 화면은 기능을 더 늘리기보다, 찬성/반대 토론 흐름이 자연스럽게 이어지도록 안정화하는 쪽이 좋습니다.
결과는 별도 장식 카드보다 기존 대화 흐름 아래에서 바로 읽히는 정리 문단으로 두는 편이 발표 화면에서도 자연스럽습니다.

2. 실행 순서
- 샘플 문제 3개로 페르소나 생성, 찬반 토론, 내부 검토가 끝까지 이어지는지 확인합니다.
- 최종 결과는 결론, 실행 순서, 주의점만 남겨 한 화면에서 훑을 수 있게 유지합니다.
- 내부 검토는 화면에 직접 노출하지 않고 종합 결과의 주의점에만 반영합니다.
- LLM 실패 시에도 같은 흐름과 길이의 폴백 결과가 나오는지 확인합니다.

3. 주의할 점
{self._compact_critique(critique.content)}
결과가 다시 길어지면 사용자는 토론 로그와 최종 결론을 구분하기 어려워지므로, 핵심 판단과 다음 행동만 남겨야 합니다."""

    def _compact_critique(self, content: str) -> str:
        for line in content.splitlines():
            cleaned = line.strip().lstrip("-*0123456789. ")
            cleaned = cleaned.replace("판사 에이전트", "내부 평가")
            cleaned = cleaned.replace("비판 에이전트", "내부 검토")
            if cleaned:
                return cleaned
        return "데모 안정성과 평가 기준이 빠지면 다중 에이전트 구조의 장점이 흐려질 수 있습니다."

    def _clean_final_answer(self, content: str) -> str:
        lines = [
            line.rstrip()
            for line in content.splitlines()
            if not self._is_followup_offer(line)
        ]
        return "\n".join(lines).strip()

    def _is_followup_offer(self, line: str) -> bool:
        normalized = line.strip().lower()
        if not normalized:
            return False
        offer_patterns = (
            "원하면",
            "원하시면",
            "필요하면",
            "필요하시면",
            "궁금하면",
            "궁금하시면",
            "바로 이어서",
            "이어 정리",
            "정리해줄게",
            "정리해드릴게",
            "알려줄게",
            "알려드릴게",
            "도와줄게",
            "도와드릴게",
        )
        return any(pattern in normalized for pattern in offer_patterns)
