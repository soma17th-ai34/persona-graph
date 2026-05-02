from app.agents.critic import CriticAgent
from app.agents.evaluator import EvaluatorAgent
from app.agents.persona_generator import PersonaGenerator
from app.agents.specialist import SpecialistAgent
from app.agents.synthesizer import SynthesizerAgent
from app.llm import LLMClient
from app.schemas import AgentMessage, SolveResponse


class Supervisor:
    def __init__(self, llm: LLMClient):
        self.persona_generator = PersonaGenerator(llm)
        self.specialist = SpecialistAgent(llm)
        self.critic = CriticAgent(llm)
        self.synthesizer = SynthesizerAgent(llm)
        self.evaluator = EvaluatorAgent(llm)
        self.llm = llm

    def solve(self, problem: str, persona_count: int) -> SolveResponse:
        personas, persona_message = self.persona_generator.generate(problem, persona_count)
        specialist_messages = [self.specialist.answer(problem, persona) for persona in personas]
        critique = self.critic.review(problem, specialist_messages)
        synthesis = self.synthesizer.synthesize(problem, specialist_messages, critique)
        evaluation = self.evaluator.evaluate(problem, specialist_messages, critique, synthesis)

        messages: list[AgentMessage] = [
            persona_message,
            *specialist_messages,
            critique,
            synthesis,
        ]
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
