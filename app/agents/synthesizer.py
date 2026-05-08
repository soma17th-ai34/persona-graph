from __future__ import annotations

import re

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
        improvement_suggestions: list[str] | None = None,
        previous_synthesis: str | None = None,
        refine_instruction: str | None = None,
    ) -> AgentMessage:
        transcript = "\n\n".join(
            f"[{message.agent_name} / {message.role}]\n{message.content}" for message in debate_messages
        )
        refine_block = ""
        if previous_synthesis or improvement_suggestions or refine_instruction:
            suggestion_text = "\n".join(f"- {item}" for item in (improvement_suggestions or []))
            refine_block = f"""

이전 최종 정리:
{previous_synthesis or "없음"}

평가 기반 개선 제안:
{suggestion_text or "- 별도 개선 제안 없음"}

역방향 검증 피드백:
{refine_instruction or "없음"}
"""
        prompt = f"""
문제:
{problem}

토론 발언:
{transcript}

비판:
{critique.content}
{refine_block}

충돌을 정리하고 토론을 실행 가능한 계획으로 통합한 최종 답변을 작성하세요.
반드시 자연스러운 한국어로 작성하고, 고유명사나 기술 약어 외에는 영어를 최소화하세요.
한 페이지 안에서 바로 읽히도록 5~6줄로만 작성하세요.
다음 의미가 자연스럽게 드러나야 합니다.
결론, 이유, 실행 순서, 주의할 점, 바로 할 일

출력 규칙:
- 평가 기반 개선 제안이나 역방향 검증 피드백이 있으면 그 부족분만 보완하세요.
- 토론에 없던 새 주제를 임의로 추가하지 마세요.
- Markdown 문법을 쓰지 마세요. 번호 목록, 불릿, 제목 기호, 굵은 글씨 표시를 모두 쓰지 마세요.
- 각 줄은 한 문장으로 짧게 작성하세요.
- "원하면", "필요하면", "바로 이어서" 같은 후속 제안 문장으로 끝내지 마세요.
"""
        result = self.llm.complete(
            system_prompt="당신은 한국어 다중 에이전트 토론을 명확한 최종 결정과 다음 행동으로 통합합니다.",
            user_prompt=prompt,
            temperature=0.3,
        )
        content = (
            result.content
            if result.used_llm and result.content
            else self._fallback(problem, critique, improvement_suggestions, refine_instruction)
        )
        content = self._clean_final_answer(content)
        return AgentMessage(
            stage="synthesizer",
            agent_id="synthesizer",
            agent_name="종합 에이전트",
            role="토론을 최종 답변으로 통합하는 역할",
            content=content,
            metadata={
                "source": "llm" if result.used_llm and result.content else "fallback",
                "error": result.error,
                "phase": "refine" if (improvement_suggestions or refine_instruction) else "initial",
            },
        )

    def _fallback(
        self,
        problem: str,
        critique: AgentMessage,
        improvement_suggestions: list[str] | None = None,
        refine_instruction: str | None = None,
    ) -> str:
        suggestion_line = ""
        if improvement_suggestions or refine_instruction:
            items = [*list(improvement_suggestions or [])]
            if refine_instruction:
                items.append(refine_instruction)
            suggestion_line = f"\n보완할 점은 {items[0]}입니다."
        return f"""결론은 지금 문제를 한 번에 크게 넓히기보다, 가장 설득력 있는 한 가지 실행 방향으로 좁히는 것입니다.
이유는 관점 생성, 토론, 내부 검토, 최종 정리가 끊기지 않고 이어져야 결과를 믿고 읽을 수 있기 때문입니다.
실행은 먼저 핵심 질문을 정하고, 그다음 에이전트 의견을 비교한 뒤, 마지막에 하나의 행동 계획으로 묶으면 됩니다.
주의할 점은 내부 비판을 그대로 길게 노출하면 읽는 흐름이 무거워진다는 것입니다.
바로 할 일은 샘플 문제 하나로 전체 흐름이 끝까지 자연스럽게 보이는지 확인하는 것입니다.{suggestion_line}"""

    def _clean_final_answer(self, content: str) -> str:
        lines = []
        for line in content.splitlines():
            cleaned = self._strip_markdown(line)
            if not cleaned or self._is_followup_offer(cleaned):
                continue
            if self._is_structural_heading(cleaned):
                continue
            lines.append(cleaned)
        return "\n".join(lines[:6]).strip()

    def _strip_markdown(self, line: str) -> str:
        cleaned = line.strip()
        cleaned = cleaned.replace("**", "")
        cleaned = cleaned.replace("__", "")
        cleaned = re.sub(r"^#{1,6}\s*", "", cleaned)
        cleaned = re.sub(r"^[-*+]\s+", "", cleaned)
        cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned)
        return cleaned.strip()

    def _is_structural_heading(self, line: str) -> bool:
        normalized = line.strip().rstrip(":：")
        headings = {
            "최종 결론",
            "최종 판단",
            "선택한 방향",
            "실행 단계",
            "실행 순서",
            "리스크와 대응",
            "주의할 점",
            "다음 24시간 액션",
            "바로 할 일",
            "보완 포인트 반영",
        }
        return normalized in headings

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
