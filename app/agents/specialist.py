from app.llm import LLMClient
from app.schemas import AgentMessage, Persona


class SpecialistAgent:
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
        result = self.llm.complete(
            system_prompt="당신은 한국어 단체 대화방에 함께 있는 전문가 Agent입니다. 보고서가 아니라 채팅방 발언처럼 짧고 자연스럽게 말하세요.",
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
        result = self.llm.complete(
            system_prompt="당신은 한국어 단체 대화방에 참여한 전문가 Agent입니다. 정해진 토론 대본처럼 말하지 말고, 현재 흐름에 짧게 이어 말하세요.",
            user_prompt=prompt,
            temperature=0.45,
        )
        content = (
            result.content
            if result.used_llm and result.content
            else self._response_fallback(persona, round_number)
        )
        return AgentMessage(
            stage="debate",
            agent_id=persona.id,
            agent_name=persona.name,
            role=persona.role,
            content=content,
            metadata={
                "source": "llm" if result.used_llm and result.content else "fallback",
                "error": result.error,
                "round": round_number,
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
        result = self.llm.complete(
            system_prompt="당신은 한국어 단체 대화방에 참여한 전문가 Agent입니다. 사용자의 말에 바로 반응하고, 짧고 실제적인 다음 판단을 제안하세요.",
            user_prompt=prompt,
            temperature=0.45,
        )
        content = (
            result.content
            if result.used_llm and result.content
            else self._user_reply_fallback(persona, user_content, round_number)
        )
        return AgentMessage(
            stage="debate",
            agent_id=persona.id,
            agent_name=persona.name,
            role=persona.role,
            content=content,
            metadata={
                "source": "llm" if result.used_llm and result.content else "fallback",
                "error": result.error,
                "round": round_number,
                "phase": "user_response",
                "responds_to": "user",
            },
        )

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
