from app.llm import LLMClient, parse_json_object
from app.schemas import AgentMessage, Persona


DEFAULT_PERSONAS = [
    Persona(
        id="product_strategist",
        name="Product Strategist",
        role="MVP and user-value planner",
        perspective="Focuses on the smallest demo that proves real value.",
        priority_questions=["Who is the first user?", "What is the success moment?", "What can be cut?"],
    ),
    Persona(
        id="systems_engineer",
        name="Systems Engineer",
        role="Architecture and reliability reviewer",
        perspective="Checks feasibility, interfaces, failure modes, and operational simplicity.",
        priority_questions=["Where can the workflow fail?", "What state should be logged?", "How do we test it?"],
    ),
    Persona(
        id="ai_researcher",
        name="AI Researcher",
        role="Reasoning quality and evaluation designer",
        perspective="Improves prompt structure, agent roles, critique loops, and output evaluation.",
        priority_questions=["Does the agent role help reasoning?", "How do we detect weak answers?", "What should be measured?"],
    ),
    Persona(
        id="demo_director",
        name="Demo Director",
        role="Presentation and portfolio storyteller",
        perspective="Shapes the output into a clear, impressive, low-risk demonstration.",
        priority_questions=["What will the audience see first?", "Which scenario sells the idea?", "What screenshots matter?"],
    ),
    Persona(
        id="risk_analyst",
        name="Risk Analyst",
        role="Risk, cost, and scope controller",
        perspective="Finds hidden complexity, schedule traps, and decisions that threaten a 2-week MVP.",
        priority_questions=["What is too broad?", "What depends on external services?", "What must have a fallback?"],
    ),
]


class PersonaGenerator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate(self, problem: str, count: int) -> tuple[list[Persona], AgentMessage]:
        prompt = f"""
Create {count} complementary AI agent personas for solving this problem.

Problem:
{problem}

Return only a JSON array. Each item must include:
- id: snake_case unique id
- name: short agent name
- role: one sentence role
- perspective: one sentence reasoning lens
- priority_questions: 2 to 4 concrete questions
"""
        result = self.llm.complete(
            system_prompt="You design concise, useful multi-agent teams. Return strict JSON only.",
            user_prompt=prompt,
            temperature=0.25,
        )

        personas = self._from_llm(result.content, count) if result.used_llm else []
        if not personas:
            personas = DEFAULT_PERSONAS[:count]

        content = "\n\n".join(
            f"{idx}. {persona.name} ({persona.role})\n- 관점: {persona.perspective}\n- 핵심 질문: "
            + ", ".join(persona.priority_questions)
            for idx, persona in enumerate(personas, start=1)
        )
        message = AgentMessage(
            stage="persona_generation",
            agent_id="persona_generator",
            agent_name="Persona Generator",
            role="Generates a focused agent team",
            content=content,
            metadata={"source": "llm" if result.used_llm and personas else "fallback", "error": result.error},
        )
        return personas, message

    def _from_llm(self, raw: str, count: int) -> list[Persona]:
        parsed = parse_json_object(raw)
        if not isinstance(parsed, list):
            return []

        personas: list[Persona] = []
        for index, item in enumerate(parsed[:count], start=1):
            if not isinstance(item, dict):
                continue
            try:
                personas.append(
                    Persona(
                        id=str(item.get("id") or f"persona_{index}").strip().replace(" ", "_").lower(),
                        name=str(item["name"]).strip(),
                        role=str(item["role"]).strip(),
                        perspective=str(item["perspective"]).strip(),
                        priority_questions=[str(q).strip() for q in item.get("priority_questions", [])][:4],
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return personas
