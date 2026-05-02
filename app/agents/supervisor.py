from app.agents.critic import CriticAgent
from app.agents.evaluator import EvaluatorAgent
from app.agents.moderator import ModeratorAgent
from app.agents.persona_generator import PersonaGenerator
from app.agents.specialist import SpecialistAgent
from app.agents.synthesizer import SynthesizerAgent
from app.characters import assign_characters
from app.llm import LLMClient
from app.schemas import AgentMessage, SolveResponse


class Supervisor:
    def __init__(self, llm: LLMClient):
        self.persona_generator = PersonaGenerator(llm)
        self.moderator = ModeratorAgent(llm)
        self.specialist = SpecialistAgent(llm)
        self.critic = CriticAgent(llm)
        self.synthesizer = SynthesizerAgent(llm)
        self.evaluator = EvaluatorAgent(llm)
        self.llm = llm

    def solve(self, problem: str, persona_count: int, debate_rounds: int = 1) -> SolveResponse:
        personas, persona_message = self.persona_generator.generate(problem, persona_count)
        personas = assign_characters(personas)
        opening = self.moderator.open(problem, personas)
        specialist_messages = [self.specialist.answer(problem, persona) for persona in personas]
        discussion_messages: list[AgentMessage] = []

        messages: list[AgentMessage] = [persona_message, opening, *specialist_messages]

        for round_number in range(1, debate_rounds + 1):
            moderator_note = self.moderator.guide(
                problem=problem,
                personas=personas,
                transcript=self._format_transcript([*specialist_messages, *discussion_messages]),
                round_number=round_number,
            )
            messages.append(moderator_note)

            for persona in personas:
                response = self.specialist.respond(
                    problem=problem,
                    persona=persona,
                    transcript=self._format_transcript([*specialist_messages, *discussion_messages]),
                    moderator_note=moderator_note.content,
                    round_number=round_number,
                )
                discussion_messages.append(response)
                messages.append(response)

        debate_messages = [*specialist_messages, *discussion_messages]
        critique = self.critic.review(problem, debate_messages)
        synthesis = self.synthesizer.synthesize(problem, debate_messages, critique)
        evaluation = self.evaluator.evaluate(problem, debate_messages, critique, synthesis)

        messages.extend([critique, synthesis])
        used_llm = any(message.metadata.get("source") == "llm" for message in messages)
        return SolveResponse(
            problem=problem,
            personas=personas,
            messages=messages,
            final_answer=synthesis.content,
            evaluation=evaluation,
            used_llm=used_llm,
            model=self.llm.model,
        )

    def continue_discussion(
        self,
        response: SolveResponse,
        user_content: str,
        max_agents: int = 2,
    ) -> SolveResponse:
        round_number = self._next_round(response.messages)
        selected_personas = response.personas[: max(1, min(max_agents, 3))]
        user_message = AgentMessage(
            stage="user",
            agent_id="user",
            agent_name="현재",
            role="토론에 직접 의견을 추가하는 사용자",
            content=user_content,
            metadata={
                "source": "user",
                "phase": "user_intervention",
                "round": round_number,
            },
        )

        messages = [*response.messages, user_message]
        agent_replies: list[AgentMessage] = []
        for persona in selected_personas:
            reply = self.specialist.reply_to_user(
                problem=response.problem,
                persona=persona,
                transcript=self._format_transcript(messages + agent_replies),
                user_content=user_content,
                round_number=round_number,
            )
            agent_replies.append(reply)

        messages.extend(agent_replies)

        synthesis = self.synthesizer.synthesize(
            response.problem,
            self._discussion_messages(messages),
            self._latest_critique(messages),
        )
        synthesis.metadata["round"] = round_number
        synthesis.metadata["phase"] = "followup_synthesis"
        messages.append(synthesis)

        evaluation = self.evaluator.evaluate(
            response.problem,
            self._discussion_messages(messages),
            self._latest_critique(messages),
            synthesis,
        )
        used_llm = response.used_llm or any(message.metadata.get("source") == "llm" for message in messages)
        return response.model_copy(
            update={
                "messages": messages,
                "final_answer": synthesis.content,
                "evaluation": evaluation,
                "used_llm": used_llm,
                "model": self.llm.model,
            }
        )

    def _format_transcript(self, messages: list[AgentMessage]) -> str:
        if not messages:
            return "아직 발언이 없습니다."
        return "\n\n".join(
            f"[{message.agent_name} / {message.role}]\n{message.content}"
            for message in messages
        )

    def _next_round(self, messages: list[AgentMessage]) -> int:
        rounds = [
            int(message.metadata["round"])
            for message in messages
            if str(message.metadata.get("round", "")).isdigit()
        ]
        return max(rounds, default=0) + 1

    def _discussion_messages(self, messages: list[AgentMessage]) -> list[AgentMessage]:
        return [
            message
            for message in messages
            if message.stage in {"user", "specialist", "debate"}
        ]

    def _latest_critique(self, messages: list[AgentMessage]) -> AgentMessage:
        for message in reversed(messages):
            if message.stage == "critic":
                return message
        return AgentMessage(
            stage="critic",
            agent_id="critic",
            agent_name="비판 에이전트",
            role="모순, 약한 가정, 누락된 제약을 찾는 역할",
            content="아직 별도의 비판 메시지가 없습니다. 최신 사용자 의견과 에이전트 응답을 기준으로 실행 가능성을 점검하세요.",
            metadata={"source": "fallback", "phase": "implicit"},
        )
