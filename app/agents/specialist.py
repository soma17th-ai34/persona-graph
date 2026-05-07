import re

from app.llm import LLMClient
from app.schemas import AgentMessage, Persona


class SpecialistAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def answer(self, problem: str, persona: Persona) -> AgentMessage:
        prompt = self._build_prompt(
            problem=problem,
            persona=persona,
            mode="initial",
            transcript="아직 발언이 없습니다.",
        )
        result = self.llm.complete(
            system_prompt="당신은 한국어 단체 대화방에 참여한 전문가 Agent입니다. 근거가 드러나는 짧은 답변을 작성하세요.",
            user_prompt=prompt,
        )
        content = result.content if result.used_llm and result.content else self._fallback(problem, persona)
        return AgentMessage(
            stage="specialist",
            agent_id=persona.id,
            agent_name=persona.name,
            role=persona.role,
            content=content,
            metadata={
                "source": "llm" if result.used_llm and result.content else "fallback",
                "error": result.error,
                "response_mode": "initial",
                "reasoning_basis": ["problem", "persona_profile"],
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
        prompt = self._build_prompt(
            problem=problem,
            persona=persona,
            mode="debate",
            transcript=transcript,
            moderator_note=moderator_note,
            round_number=round_number,
        )
        result = self.llm.complete(
            system_prompt="당신은 한국어 단체 대화방에 참여한 전문가 Agent입니다. 앞선 주장에 반응하면서 근거와 다음 행동을 함께 제시하세요.",
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
                "response_mode": "debate",
                "reasoning_basis": ["problem", "transcript", "moderator_note"],
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
        prompt = self._build_prompt(
            problem=problem,
            persona=persona,
            mode="user_response",
            transcript=transcript,
            user_content=user_content,
            round_number=round_number,
        )
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
                "response_mode": "user_response",
                "reasoning_basis": ["problem", "transcript", "user_content"],
            },
        )

    def _build_prompt(
        self,
        problem: str,
        persona: Persona,
        mode: str,
        transcript: str,
        moderator_note: str | None = None,
        user_content: str | None = None,
        round_number: int | None = None,
    ) -> str:
        context_block = self._context_block(
            problem=problem,
            transcript=transcript,
            user_content=user_content,
        )
        mode_guide = {
            "initial": "첫 발언입니다. 관점을 분명히 밝히고 바로 실행 가능한 제안을 하나 남기세요.",
            "debate": "이어 말하기 라운드입니다. 앞선 주장 중 하나에 반응하면서 충돌을 좁히세요.",
            "user_response": "사용자 개입 라운드입니다. 사용자 의견을 실행 판단으로 바꾸는 답변을 하세요.",
        }[mode]
        optional_block = ""
        if moderator_note:
            optional_block += f"\n사회자 메모:\n{moderator_note}\n"
        if user_content:
            optional_block += f"\n사용자 새 의견:\n{user_content}\n"
        round_line = f"\n현재 라운드: {round_number}" if round_number is not None else ""
        return f"""
문제 컨텍스트:
{context_block}
{round_line}

페르소나 프로필:
- 이름: {persona.name}
- 역할: {persona.role}
- 관점: {persona.perspective}
- 핵심 질문: {", ".join(persona.priority_questions)}
{optional_block}
최근 토론 핵심:
{transcript}

작성 지침:
- {mode_guide}
- 반드시 자연스러운 한국어로 작성하고, 고유명사나 기술 약어 외에는 영어를 최소화하세요.
- 아래 형식을 지키되 항목 제목은 쓰지 마세요.
  1) 판단 1문장
  2) 이유 1~2문장(위 컨텍스트를 근거로)
  3) 다음 행동 1문장
- 총 3~4문장으로 짧고 구체적으로 작성하세요.
""".strip()

    def _context_block(self, problem: str, transcript: str, user_content: str | None) -> str:
        problem_summary = self._summarize(problem, limit=110)
        transcript_summary = (
            "이전 라운드 핵심 없음"
            if not transcript or transcript.strip() == "아직 발언이 없습니다."
            else self._summarize(transcript, limit=170)
        )
        constraint_source = f"{problem}\n{user_content or ''}"
        constraints = self._extract_constraints(constraint_source)
        return (
            f"- 문제 요약: {problem_summary}\n"
            f"- 이전 라운드 핵심: {transcript_summary}\n"
            f"- 제약조건: {constraints}"
        )

    def _extract_constraints(self, text: str) -> str:
        compact = " ".join(text.split())
        segments = re.split(r"[.!?]\s*", compact)
        keywords = ("주", "일", "마감", "예산", "비용", "시간", "인원", "리스크", "안정성")
        hits = [segment.strip() for segment in segments if any(keyword in segment for keyword in keywords)]
        if hits:
            return "; ".join(hits[:2])
        return "명시된 제약 없음"

    def _summarize(self, text: str, limit: int) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return f"{compact[: limit - 1].rstrip()}..."

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
