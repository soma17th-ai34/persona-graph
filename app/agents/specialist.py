from __future__ import annotations

from app.llm import LLMClient, parse_json_object
from app.schemas import AgentMessage, Persona


class SpecialistAgent:
    SELF_VERIFICATION_THRESHOLD = 4
    SELF_VERIFICATION_MAX_ATTEMPTS = 3

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def answer(self, problem: str, persona: Persona) -> AgentMessage:
        prompt = f"""
문제:
{problem}

페르소나:
- 이름: {persona.name}
- 역할: {persona.role}
- 관점: {persona.perspective}
- 핵심 질문: {", ".join(persona.priority_questions)}

이 페르소나의 관점에서 실용적인 의견을 작성하세요.
반드시 자연스러운 한국어로 작성하고, 고유명사나 기술 약어 외에는 영어를 최소화하세요.
단체 대화방의 첫 발언처럼 작성하세요.
요구사항:
- 첫 문장에 자기 판단을 바로 말하세요.
- 번호 목록이나 "핵심 판단/근거/실행 제안" 같은 보고서 제목을 쓰지 마세요.
- 자기 관점에서 중요한 이유와 바로 해볼 수 있는 제안을 자연스럽게 이어 말하세요.
- 다른 Agent에게 넘기는 질문으로 끝낼 필요는 없습니다.
- 3~5문장으로 짧고 구체적으로 작성하세요.
"""
        completion = self._complete_with_self_verification(
            system_prompt="당신은 한국어 단체 대화방에 함께 있는 전문가 Agent입니다. 보고서가 아니라 채팅방 발언처럼 짧고 자연스럽게 말하세요.",
            user_prompt=prompt,
            fallback_content=self._fallback(problem, persona),
            verification_goal="페르소나 역할과 관점이 드러나고, 사용자 질문에 직접 답하며, 실행 가능한 제안을 포함한 3~5문장 답변",
        )
        return AgentMessage(
            stage="specialist",
            agent_id=persona.id,
            agent_name=persona.name,
            role=persona.role,
            content=str(completion["content"]),
            metadata={
                "source": completion["source"],
                "error": completion["error"],
                "self_verification": completion["self_verification"],
            },
        )

    def respond(
        self,
        problem: str,
        persona: Persona,
        transcript: str,
        moderator_note: str,
        round_number: int,
    ) -> AgentMessage:
        prompt = f"""
문제:
{problem}

페르소나:
- 이름: {persona.name}
- 역할: {persona.role}
- 관점: {persona.perspective}
- 핵심 질문: {", ".join(persona.priority_questions)}

진행 메모:
{moderator_note}

지금까지의 토론:
{transcript}

{persona.name}의 관점에서 지금 흐름에 자연스럽게 이어 말하세요.
반드시 자연스러운 한국어로 작성하고, 고유명사나 기술 약어 외에는 영어를 최소화하세요.
요구사항:
- 첫 문장은 바로 자신의 판단이나 보완점으로 시작하세요.
- 다른 Agent 이름은 꼭 필요할 때만 자연스럽게 언급하세요.
- "동의합니다", "좋습니다", "~님 말처럼" 같은 시작을 반복하지 마세요.
- 질문으로 끝내야 한다는 규칙은 없습니다. 필요한 경우에만 짧게 물어보세요.
- 2~4문장으로, 실제 단체 대화방에서 말하듯 작성하세요.
"""
        completion = self._complete_with_self_verification(
            system_prompt="당신은 한국어 단체 대화방에 참여한 전문가 Agent입니다. 정해진 토론 대본처럼 말하지 말고, 현재 흐름에 짧게 이어 말하세요.",
            user_prompt=prompt,
            fallback_content=self._response_fallback(persona, round_number),
            verification_goal="앞선 토론 흐름에 직접 반응하고, 자신의 관점에서 근거 있는 판단을 남기는 2~4문장 답변",
            temperature=0.45,
        )
        return AgentMessage(
            stage="debate",
            agent_id=persona.id,
            agent_name=persona.name,
            role=persona.role,
            content=str(completion["content"]),
            metadata={
                "source": completion["source"],
                "error": completion["error"],
                "round": round_number,
                "self_verification": completion["self_verification"],
            },
        )

    def reply_to_user(
        self,
        problem: str,
        persona: Persona,
        transcript: str,
        user_content: str,
        round_number: int,
    ) -> AgentMessage:
        prompt = f"""
문제:
{problem}

페르소나:
- 이름: {persona.name}
- 역할: {persona.role}
- 관점: {persona.perspective}
- 핵심 질문: {", ".join(persona.priority_questions)}

지금까지의 대화:
{transcript}

사용자의 새 의견:
{user_content}

{persona.name}의 관점에서 사용자의 새 의견에 바로 답하세요.
반드시 자연스러운 한국어로 작성하고, 고유명사나 기술 약어 외에는 영어를 최소화하세요.
요구사항:
- 사용자의 말을 다시 길게 정리하지 말고 바로 답하세요.
- 첫 문장에 추천, 우려, 보완점 중 하나를 분명히 말하세요.
- 이전 Agent의 주장은 꼭 필요할 때만 짧게 연결하세요.
- "좋습니다. 지금 질문은..." 같은 상담원식 시작을 피하세요.
- 마지막은 질문보다 다음 행동이나 판단 기준으로 끝내는 편을 우선하세요.
- 2~4문장으로, 단체 대화방에서 말하듯 작성하세요.
"""
        completion = self._complete_with_self_verification(
            system_prompt="당신은 한국어 단체 대화방에 참여한 전문가 Agent입니다. 사용자의 말에 바로 반응하고, 짧고 실제적인 다음 판단을 제안하세요.",
            user_prompt=prompt,
            fallback_content=self._user_reply_fallback(persona, user_content, round_number),
            verification_goal="사용자의 새 의견에 직접 답하고, 추천/우려/보완점과 다음 판단 기준을 포함한 2~4문장 답변",
            temperature=0.45,
        )
        return AgentMessage(
            stage="debate",
            agent_id=persona.id,
            agent_name=persona.name,
            role=persona.role,
            content=str(completion["content"]),
            metadata={
                "source": completion["source"],
                "error": completion["error"],
                "round": round_number,
                "phase": "user_response",
                "responds_to": "user",
                "self_verification": completion["self_verification"],
            },
        )

    def _complete_with_self_verification(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback_content: str,
        verification_goal: str,
        temperature: float | None = None,
    ) -> dict[str, object]:
        result = self.llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
        if not result.used_llm or not result.content:
            verification = self._local_verification(fallback_content, attempts=1)
            return {
                "content": fallback_content,
                "source": "fallback",
                "error": result.error,
                "self_verification": verification,
            }

        content = result.content
        verification = self._local_verification(content, attempts=1)
        for attempt in range(1, self.SELF_VERIFICATION_MAX_ATTEMPTS + 1):
            verification = self._verify_draft(content, verification_goal, attempt)
            if verification["passed"] or attempt == self.SELF_VERIFICATION_MAX_ATTEMPTS:
                break

            refined = self.llm.complete(
                system_prompt=system_prompt,
                user_prompt=self._refine_prompt(user_prompt, content, str(verification.get("issue", ""))),
                temperature=0.25,
            )
            if not refined.used_llm or not refined.content:
                verification["error"] = refined.error
                break
            content = refined.content

        return {
            "content": content,
            "source": "llm",
            "error": result.error,
            "self_verification": verification,
        }

    def _verify_draft(self, content: str, verification_goal: str, attempt: int) -> dict[str, object]:
        prompt = f"""
검증 목표:
{verification_goal}

검증할 답변:
{content}

답변이 검증 목표를 만족하는지 평가하세요. 반드시 JSON 객체만 반환하세요.
- score: integer 1-5
- issue: 부족한 점을 한국어 한 문장으로 작성. 충분하면 빈 문자열
"""
        result = self.llm.complete(
            system_prompt="당신은 한국어 다중 에이전트 발언을 검증하는 평가자입니다. 엄격한 JSON만 반환하세요.",
            user_prompt=prompt,
            temperature=0.05,
        )
        parsed = parse_json_object(result.content) if result.used_llm else None
        if not isinstance(parsed, dict):
            verification = self._local_verification(content, attempts=attempt)
            verification["method"] = "local"
            verification["error"] = result.error or "Unable to parse self verification JSON."
            return verification

        score = self._verification_score(parsed.get("score"))
        return {
            "score": score,
            "passed": score >= self.SELF_VERIFICATION_THRESHOLD,
            "threshold": self.SELF_VERIFICATION_THRESHOLD,
            "attempts": attempt,
            "method": "llm",
            "issue": str(parsed.get("issue", "")).strip(),
            "error": result.error,
        }

    def _refine_prompt(self, original_prompt: str, draft: str, issue: str) -> str:
        return f"""
원래 요청:
{original_prompt}

기준 미달 이유:
{issue or "검증 기준을 충분히 만족하지 못했습니다."}

초안:
{draft}

위 문제만 고쳐서 같은 형식과 비슷한 길이로 다시 작성하세요.
새 주제를 추가하지 말고, 사용자 질문과 현재 토론 맥락에 더 직접 맞추세요.
"""

    def _local_verification(self, content: str, attempts: int) -> dict[str, object]:
        sentences = [part.strip() for part in content.replace("\n", " ").split(".") if part.strip()]
        has_decision = any(keyword in content for keyword in ["좋", "우려", "먼저", "기준", "확인", "실행", "판단"])
        score = 4 if len(sentences) >= 2 and has_decision else 3
        return {
            "score": score,
            "passed": score >= self.SELF_VERIFICATION_THRESHOLD,
            "threshold": self.SELF_VERIFICATION_THRESHOLD,
            "attempts": attempts,
            "method": "local",
            "issue": "" if score >= self.SELF_VERIFICATION_THRESHOLD else "답변의 판단 근거가 부족합니다.",
            "error": None,
        }

    def _verification_score(self, value: object) -> int:
        try:
            score = int(value)
        except (TypeError, ValueError):
            return 3
        if score < 1:
            return 1
        if score > 5:
            return 5
        return score

    def _fallback(self, problem: str, persona: Persona) -> str:
        first_question = persona.priority_questions[0] if persona.priority_questions else "가장 먼저 검증할 기준을 정해야 합니다."
        return f"""{persona.name} 입장에서는 "{first_question}"부터 확인하고 싶습니다.
이 문제는 '{persona.perspective}' 쪽으로 좁힐수록 2주 안에 보여줄 수 있는 결과가 선명해집니다.
범위가 넓어질수록 구현보다 조율 비용이 커지기 때문에, 한 번의 입력에서 관점 제시와 비판, 종합이 끝까지 이어지는지 먼저 확인해야 합니다.
초기 MVP에서는 자동화 범위를 늘리기보다 로그 품질, 재현성, 실패 시 폴백을 우선하는 편이 안전합니다."""

    def _response_fallback(self, persona: Persona, round_number: int) -> str:
        first_question = persona.priority_questions[0] if persona.priority_questions else "실행 기준"
        return f"""{persona.name} 쪽에서는 지금 먼저 확인할 기준을 "{first_question}"로 잡는 게 좋아 보입니다.
"{persona.perspective}" 기준이 빠지면 결론이 좋아 보여도 실제 선택으로 이어지기 어렵습니다.
이번 라운드에서는 범위, 성공 기준, 데모 실패 시 대안 중 하나를 먼저 고정하면 다음 판단이 훨씬 쉬워집니다."""

    def _user_reply_fallback(self, persona: Persona, user_content: str, round_number: int) -> str:
        first_question = persona.priority_questions[0] if persona.priority_questions else "우선순위"
        return f"""그 의견을 넣는다면 먼저 "{first_question}" 기준으로 기능 후보를 걸러보는 게 좋겠습니다.
{persona.name} 관점에서는 "{user_content}"가 실제 결정으로 이어지려면 남길 범위와 버릴 범위가 같이 정해져야 합니다.
다음 판단 기준은 이 의견을 넣었을 때 데모 안정성, 구현 난이도, 설득력이 함께 좋아지는지입니다."""
