from __future__ import annotations

from app.llm import LLMClient, parse_json_object
from app.schemas import AgentMessage, Evaluation


class EvaluatorAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def evaluate(
        self,
        problem: str,
        specialist_messages: list[AgentMessage],
        critique: AgentMessage,
        synthesis: AgentMessage,
    ) -> Evaluation:
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

Final synthesis:
{synthesis.content}

Evaluate the final result. Return only a JSON object with:
- consistency: integer 1-5
- specificity: integer 1-5
- risk_awareness: integer 1-5
- feasibility: integer 1-5
- overall_comment: one concise Korean sentence
- improvement_suggestions: array of 1 to 3 concise Korean strings
"""
        result = self.llm.complete(
            system_prompt="You evaluate multi-agent reasoning quality. Return strict JSON only.",
            user_prompt=prompt,
            temperature=0.15,
        )

        source = "fallback"
        evaluation = self._from_llm(result.content) if result.used_llm else None
        error = result.error
        if result.used_llm and evaluation is not None:
            source = "llm"
        elif result.used_llm:
            error = "Unable to parse LLM evaluation JSON."

        if evaluation is None:
            evaluation = self._fallback(specialist_messages, critique, synthesis)
            evaluation.metadata["error"] = error

        evaluation.metadata["source"] = source
        return evaluation

    def _from_llm(self, raw: str) -> Evaluation | None:
        parsed = parse_json_object(raw)
        if not isinstance(parsed, dict):
            return None

        try:
            return Evaluation(
                consistency=self._score(parsed.get("consistency")),
                specificity=self._score(parsed.get("specificity")),
                risk_awareness=self._score(parsed.get("risk_awareness")),
                feasibility=self._score(parsed.get("feasibility")),
                overall_comment=str(parsed["overall_comment"]).strip(),
                improvement_suggestions=[
                    str(item).strip()
                    for item in parsed.get("improvement_suggestions", [])
                    if str(item).strip()
                ][:3],
                metadata={},
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _fallback(
        self,
        specialist_messages: list[AgentMessage],
        critique: AgentMessage,
        synthesis: AgentMessage,
    ) -> Evaluation:
        final_answer = synthesis.content
        bullet_count = final_answer.count("- ") + final_answer.count("\n1.")
        has_risk = any(keyword in final_answer for keyword in ["리스크", "위험", "주의", "대응"])
        has_next_action = any(keyword in final_answer for keyword in ["다음", "24시간", "실행 단계", "액션"])

        consistency = 4 if len(specialist_messages) >= 3 and critique.content else 3
        specificity = 5 if bullet_count >= 6 else 4 if bullet_count >= 3 else 3
        risk_awareness = 5 if has_risk else 3
        feasibility = 5 if has_next_action else 4

        return Evaluation(
            consistency=consistency,
            specificity=specificity,
            risk_awareness=risk_awareness,
            feasibility=feasibility,
            overall_comment="비판과 종합 흐름이 유지되어 MVP 데모용 문제 해결 로그로 사용하기 좋습니다.",
            improvement_suggestions=[
                "최종 답변에 정량적 성공 기준을 1개 이상 추가하면 설득력이 더 좋아집니다.",
                "발표용 시나리오에서는 Before/After 비교 예시를 함께 준비하는 것이 좋습니다.",
            ],
            metadata={},
        )

    def _score(self, value: object) -> int:
        score = int(value)
        if score < 1:
            return 1
        if score > 5:
            return 5
        return score
