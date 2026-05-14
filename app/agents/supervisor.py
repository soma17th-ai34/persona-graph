from __future__ import annotations

import time

from app.agents.critic import CriticAgent
from app.agents.evaluator import EvaluatorAgent
from app.agents.moderator import ModeratorAgent
from app.agents.persona_generator import PersonaGenerator
from app.agents.specialist import SpecialistAgent
from app.agents.synthesizer import SynthesizerAgent
from app.characters import assign_characters
from app.llm import LLMClient
from app.run_memory import RunMemoryClient
from app.schemas import AgentMessage, MemoryRecord, ReasoningRecord, SearchRecord, SolveResponse
from app.search import SearchClient
from app.terminal_logging import terminal_log


StreamEvent = dict[str, object]


class Supervisor:
    QUALITY_THRESHOLD = 4.0
    MAX_EXTRA_EVALUATION_ROUNDS = 1

    def __init__(self, llm: LLMClient):
        self.persona_generator = PersonaGenerator(llm)
        self.moderator = ModeratorAgent(llm)
        self.specialist = SpecialistAgent(llm)
        self.critic = CriticAgent(llm)
        self.synthesizer = SynthesizerAgent(llm)
        self.evaluator = EvaluatorAgent(llm)
        self.llm = llm
        self.search_client = SearchClient()
        self.memory_client = RunMemoryClient()

    def solve(
        self,
        problem: str,
        persona_count: int,
        debate_rounds: int = 1,
        search_mode: str = "auto",
    ) -> SolveResponse:
        final_response = None
        for event in self.solve_stream(problem, persona_count, debate_rounds, search_mode=search_mode):
            if event["type"] == "final_response":
                final_response = event["response"]
        if final_response is None:
            raise RuntimeError("Solve stream ended without a final response.")
        return final_response

    def solve_stream(
        self,
        problem: str,
        persona_count: int,
        debate_rounds: int = 1,
        search_mode: str = "auto",
    ):
        search_context, search_record = yield from self._fetch_search_context_stream(
            text=problem,
            mode=search_mode,
            phase="initial",
        )
        search_records = [search_record]
        research_context = self._merge_search_context(None, search_context)
        memory_context, memory_record = self._fetch_memory_context(problem, "initial")
        yield self._started_event("persona_generator", "페르소나 생성기", "persona_generation")
        personas, persona_message = self.persona_generator.generate(problem, persona_count, search_context=research_context)
        personas = assign_characters(personas)
        yield {"type": "personas_ready", "personas": personas}
        yield self._message_event(persona_message)

        yield self._started_event("moderator", "사회자 에이전트", "moderator")
        opening = self.moderator.open(problem, personas)
        yield self._message_event(opening)

        specialist_messages: list[AgentMessage] = []
        for persona in personas:
            yield self._started_event(persona.id, persona.name, "specialist")
            message = self.specialist.answer(problem, persona, search_context=research_context)
            specialist_messages.append(message)
            yield self._message_event(message)

        discussion_messages: list[AgentMessage] = []

        messages: list[AgentMessage] = [persona_message, opening, *specialist_messages]

        for round_number in range(1, debate_rounds + 1):
            round_context = [*specialist_messages, *discussion_messages]
            round_transcript = self._format_transcript(round_context)
            research_context = yield from self._fetch_round_research_context_stream(
                current_context=research_context,
                search_records=search_records,
                text=self._round_search_text(problem, round_transcript, round_number),
                mode=search_mode,
                phase="debate_round",
                round_number=round_number,
            )
            yield self._started_event("moderator", "사회자 에이전트", "moderator", round_number)
            moderator_note = self.moderator.guide(
                problem=problem,
                personas=personas,
                transcript=round_transcript,
                round_number=round_number,
                search_context=research_context,
            )
            messages.append(moderator_note)
            yield self._message_event(moderator_note)

            round_messages: list[AgentMessage] = []
            for persona in personas:
                yield self._started_event(persona.id, persona.name, "debate", round_number)
                response = self.specialist.respond(
                    problem=problem,
                    persona=persona,
                    transcript=round_transcript,
                    moderator_note=moderator_note.content,
                    round_number=round_number,
                    search_context=research_context,
                )
                round_messages.append(response)
                messages.append(response)
                yield self._message_event(response)
            discussion_messages.extend(round_messages)

        debate_messages = [*specialist_messages, *discussion_messages]
        yield self._started_event("critic", "비판 에이전트", "critic")
        critique = self.critic.review(
            problem,
            debate_messages,
            search_context=research_context,
            memory_context=memory_context,
        )
        critique.metadata["phase"] = "quality_review"
        messages.append(critique)
        yield self._message_event(critique)

        synthesis, critique, evaluation, quality_checks, reasoning_records = yield from self._verified_synthesis_stream(
            problem=problem,
            personas=personas,
            messages=messages,
            critique=critique,
            final_phase="initial_synthesis",
            search_context=research_context,
            memory_context=memory_context,
            search_mode=search_mode,
            search_records=search_records,
        )
        messages.append(synthesis)

        used_llm = self._used_llm(messages, evaluation, quality_checks)
        response = SolveResponse(
            problem=problem,
            personas=personas,
            messages=messages,
            final_answer=synthesis.content,
            evaluation=evaluation,
            search_records=search_records,
            reasoning_records=reasoning_records,
            memory_records=[memory_record],
            used_llm=used_llm,
            model=self.llm.model,
        )
        yield {"type": "final_response", "response": response}

    def continue_discussion(
        self,
        response: SolveResponse,
        user_content: str,
        max_agents: int = 2,
        search_mode: str = "auto",
    ) -> SolveResponse:
        final_response = None
        for event in self.continue_discussion_stream(
            response,
            user_content,
            max_agents,
            search_mode=search_mode,
        ):
            if event["type"] == "final_response":
                final_response = event["response"]
        if final_response is None:
            raise RuntimeError("Discussion stream ended without a final response.")
        return final_response

    def continue_discussion_stream(
        self,
        response: SolveResponse,
        user_content: str,
        max_agents: int = 2,
        search_mode: str = "auto",
    ):
        search_context, search_record = yield from self._fetch_search_context_stream(
            text=user_content,
            mode=search_mode,
            phase="followup",
        )
        previous_search_context = self._context_from_search_records(response.search_records)
        research_context = self._merge_search_context(previous_search_context, search_context)
        search_records = [*response.search_records, search_record]
        memory_context, memory_record = self._fetch_memory_context(
            f"{response.problem}\n{user_content}",
            "followup",
        )
        round_number = self._next_round(response.messages)
        selected_personas = self._select_reply_personas(
            personas=response.personas,
            user_content=user_content,
            max_agents=max_agents,
            round_number=round_number,
        )
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
        yield self._message_event(user_message)

        messages = [*response.messages, user_message]
        round_transcript = self._format_transcript(messages)
        agent_replies: list[AgentMessage] = []
        for persona in selected_personas:
            yield self._started_event(persona.id, persona.name, "debate", round_number)
            reply = self.specialist.reply_to_user(
                problem=response.problem,
                persona=persona,
                transcript=round_transcript,
                user_content=user_content,
                round_number=round_number,
                search_context=research_context,
            )
            agent_replies.append(reply)
            yield self._message_event(reply)

        messages.extend(agent_replies)

        synthesis, critique, evaluation, quality_checks, reasoning_records = yield from self._verified_synthesis_stream(
            problem=response.problem,
            personas=response.personas,
            messages=messages,
            critique=self._latest_critique(messages),
            round_number=round_number,
            final_phase="followup_synthesis",
            search_context=research_context,
            memory_context=memory_context,
            search_mode=search_mode,
            search_records=search_records,
        )
        messages.append(synthesis)
        used_llm = response.used_llm or self._used_llm(messages, evaluation, quality_checks)
        updated = response.model_copy(
            update={
                "messages": messages,
                "final_answer": synthesis.content,
                "evaluation": evaluation,
                "search_records": search_records,
                "reasoning_records": [*response.reasoning_records, *reasoning_records],
                "memory_records": [*response.memory_records, memory_record],
                "used_llm": used_llm,
                "model": self.llm.model,
            }
        )
        yield {"type": "final_response", "response": updated}

    def _verified_synthesis_stream(
        self,
        problem: str,
        personas,
        messages: list[AgentMessage],
        critique: AgentMessage,
        round_number: int | None = None,
        final_phase: str = "initial_synthesis",
        search_context: str | None = None,
        memory_context: str | None = None,
        search_mode: str = "auto",
        search_records: list[SearchRecord] | None = None,
    ):
        quality_checks: list[dict[str, object]] = []
        refine_instruction: str | None = None
        previous_synthesis: str | None = None
        synthesis: AgentMessage | None = None
        evaluation = None
        extra_round_used = False
        max_attempts = self.evaluator.REVERSE_VERIFICATION_MAX_ATTEMPTS
        reasoning_records: list[ReasoningRecord] = []
        reasoning_phase = "followup" if final_phase == "followup_synthesis" else "initial"
        research_context = search_context
        active_search_records = search_records if search_records is not None else []

        for attempt in range(1, max_attempts + 1):
            yield self._started_event("synthesizer", "종합 에이전트", "synthesizer", round_number)
            if attempt == 1 and not previous_synthesis and not refine_instruction and evaluation is None:
                synthesis, reasoning_record = self.synthesizer.synthesize_with_candidates(
                    problem=problem,
                    debate_messages=self._discussion_messages(messages),
                    critique=critique,
                    phase=reasoning_phase,
                    search_context=research_context,
                    memory_context=memory_context,
                )
                reasoning_records.append(reasoning_record)
            else:
                synthesis = self.synthesizer.synthesize(
                    problem,
                    self._discussion_messages(messages),
                    critique,
                    improvement_suggestions=evaluation.improvement_suggestions if evaluation else None,
                    previous_synthesis=previous_synthesis,
                    refine_instruction=refine_instruction,
                    search_context=research_context,
                    memory_context=memory_context,
                )
            synthesis.metadata["evaluation_attempt"] = attempt

            yield self._started_event("evaluator", "평가 에이전트", "evaluator", round_number)
            evaluation = self.evaluator.evaluate(
                problem,
                self._discussion_messages(messages),
                critique,
                synthesis,
            )
            reverse_check = self.evaluator.reverse_verify(
                problem,
                self._discussion_messages(messages),
                critique,
                synthesis,
                search_context=research_context,
                memory_context=memory_context,
            )
            quality_check = self._quality_check(evaluation, reverse_check, attempt)
            quality_checks.append(quality_check)

            if quality_check["passed"] or attempt == max_attempts:
                break

            previous_synthesis = synthesis.content
            refine_instruction = self._quality_refine_instruction(quality_check, evaluation)
            if quality_check.get("needs_extra_round") and not extra_round_used:
                extra_round_used = True
                extra_round_number = self._next_round(messages)
                research_context = yield from self._fetch_round_research_context_stream(
                    current_context=research_context,
                    search_records=active_search_records,
                    text=self._round_search_text(
                        problem=problem,
                        transcript=self._format_transcript(self._discussion_messages(messages)),
                        round_number=extra_round_number,
                        focus=refine_instruction,
                    ),
                    mode=search_mode,
                    phase="evaluation_extra_round",
                    round_number=extra_round_number,
                )
                critique = yield from self._evaluation_extra_round_stream(
                    problem=problem,
                    personas=personas,
                    messages=messages,
                    quality_check=quality_check,
                    search_context=research_context,
                    memory_context=memory_context,
                )

        if synthesis is None or evaluation is None:
            raise RuntimeError("Evaluation-based synthesis ended without a final result.")

        synthesis.metadata["phase"] = final_phase
        synthesis.metadata["round"] = round_number
        synthesis.metadata["quality_check"] = quality_checks[-1] if quality_checks else {}
        synthesis.metadata["quality_check_history"] = quality_checks
        synthesis.metadata["extra_round_used"] = extra_round_used
        evaluation.metadata["quality_check"] = quality_checks[-1] if quality_checks else {}
        evaluation.metadata["quality_check_history"] = quality_checks
        yield self._message_event(synthesis)
        return synthesis, critique, evaluation, quality_checks, reasoning_records

    def _evaluation_extra_round_stream(
        self,
        problem: str,
        personas,
        messages: list[AgentMessage],
        quality_check: dict[str, object],
        search_context: str | None = None,
        memory_context: str | None = None,
    ):
        round_number = self._next_round(messages)
        focus = self._quality_refine_instruction(quality_check, None)
        yield self._started_event("moderator", "사회자 에이전트", "moderator", round_number)
        moderator_note = self.moderator.guide(
            problem=problem,
            personas=personas,
            transcript=self._format_transcript(self._discussion_messages(messages)),
            round_number=round_number,
            focus=focus,
            search_context=search_context,
        )
        moderator_note.metadata["phase"] = "evaluation_extra_round"
        moderator_note.metadata["evaluation_focus"] = focus
        messages.append(moderator_note)
        yield self._message_event(moderator_note)

        round_transcript = self._format_transcript(self._discussion_messages(messages))
        for persona in personas:
            yield self._started_event(persona.id, persona.name, "debate", round_number)
            response = self.specialist.respond(
                problem=problem,
                persona=persona,
                transcript=round_transcript,
                moderator_note=moderator_note.content,
                round_number=round_number,
                search_context=search_context,
            )
            response.metadata["phase"] = "evaluation_extra_round"
            response.metadata["evaluation_focus"] = focus
            messages.append(response)
            yield self._message_event(response)

        yield self._started_event("critic", "비판 에이전트", "critic", round_number)
        critique = self.critic.review(
            problem,
            self._discussion_messages(messages),
            search_context=search_context,
            memory_context=memory_context,
        )
        critique.metadata["phase"] = "evaluation_extra_round"
        messages.append(critique)
        yield self._message_event(critique)
        return critique

    def _started_event(
        self,
        agent_id: str,
        agent_name: str,
        stage: str,
        round_number: int | None = None,
    ) -> StreamEvent:
        event: StreamEvent = {
            "type": "agent_started",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "stage": stage,
        }
        if round_number is not None:
            event["round"] = round_number
        return event

    def _message_event(self, message: AgentMessage) -> StreamEvent:
        return {"type": "agent_message", "message": message}

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

    def _quality_check(
        self,
        evaluation,
        reverse_check: dict[str, object],
        attempt: int,
    ) -> dict[str, object]:
        average_score = self._evaluation_average(evaluation)
        quality_passed = average_score >= self.QUALITY_THRESHOLD
        reverse_passed = bool(reverse_check.get("passed"))
        return {
            **reverse_check,
            "attempt": attempt,
            "average_score": average_score,
            "quality_threshold": self.QUALITY_THRESHOLD,
            "quality_passed": quality_passed,
            "reverse_passed": reverse_passed,
            "passed": quality_passed and reverse_passed,
            "next_action": "finish" if quality_passed and reverse_passed else "refine",
        }

    def _evaluation_average(self, evaluation) -> float:
        total = (
            evaluation.consistency
            + evaluation.specificity
            + evaluation.risk_awareness
            + evaluation.feasibility
        )
        return total / 4

    def _quality_refine_instruction(self, quality_check: dict[str, object], evaluation) -> str:
        explicit_instruction = str(quality_check.get("refine_instruction", "")).strip()
        issues = []
        if explicit_instruction:
            issues.append(explicit_instruction)

        for key in ("missing_points", "unsupported_points", "style_issues"):
            values = quality_check.get(key)
            if isinstance(values, list):
                issues.extend(str(value).strip() for value in values if str(value).strip())

        if evaluation is not None and not quality_check.get("quality_passed"):
            issues.extend(evaluation.improvement_suggestions[:3])

        if issues:
            return " / ".join(issues[:4])
        return "사용자의 원래 질문과 토론 핵심에 더 직접 맞도록 최종 정리를 다시 작성하세요."

    def _used_llm(
        self,
        messages: list[AgentMessage],
        evaluation,
        quality_checks: list[dict[str, object]],
    ) -> bool:
        return (
            any(message.metadata.get("source") == "llm" for message in messages)
            or evaluation.metadata.get("source") == "llm"
            or any(check.get("source") == "llm" for check in quality_checks)
        )

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

    def _select_reply_personas(
        self,
        personas,
        user_content: str,
        max_agents: int,
        round_number: int,
    ):
        if not personas:
            return []

        limit = max(1, min(max_agents, 3, len(personas)))
        start_index = (round_number - 1) % len(personas)
        query_terms = self._keyword_terms(user_content)
        scored = []

        for index, persona in enumerate(personas):
            profile = " ".join(
                [
                    persona.name,
                    persona.role,
                    persona.perspective,
                    *persona.priority_questions,
                ]
            )
            score = self._relevance_score(query_terms, profile)
            rotation_distance = (index - start_index) % len(personas)
            scored.append((score, rotation_distance, index, persona))

        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [persona for _, _, _, persona in scored[:limit]]

    def _relevance_score(self, query_terms: set[str], profile: str) -> int:
        profile_terms = self._keyword_terms(profile)
        profile_text = self._normalized_text(profile)
        score = len(query_terms & profile_terms) * 2
        score += sum(1 for term in query_terms if len(term) >= 2 and term in profile_text)
        return score

    def _keyword_terms(self, text: str) -> set[str]:
        normalized = self._normalized_text(text)
        terms: set[str] = set()
        for term in normalized.split():
            if len(term) < 2 or term.isdigit():
                continue
            terms.add(term)
            stripped = self._strip_korean_suffix(term)
            if len(stripped) >= 2 and not stripped.isdigit():
                terms.add(stripped)
        return terms

    def _normalized_text(self, text: str) -> str:
        return "".join(
            character.lower() if character.isalnum() else " "
            for character in text
        )

    def _fetch_memory_context(self, text: str, phase: str) -> tuple[str | None, MemoryRecord]:
        try:
            return self.memory_client.build_context(text, phase)
        except Exception as exc:
            terminal_log("memory_error", error=type(exc).__name__, detail=str(exc))
            return (
                None,
                MemoryRecord(
                    phase="followup" if phase == "followup" else "initial",
                    enabled=True,
                    status="error",
                    error=str(exc),
                ),
            )

    def _merge_search_context(self, current: str | None, new: str | None) -> str | None:
        lines: list[str] = []
        seen: set[str] = set()
        for block in (current, new):
            if not block:
                continue
            for line in block.splitlines():
                cleaned = " ".join(line.split())
                normalized = cleaned.lower()
                if not cleaned or normalized in seen:
                    continue
                seen.add(normalized)
                lines.append(cleaned)
        return "\n".join(lines) if lines else None

    def _context_from_search_records(self, records: list[SearchRecord]) -> str | None:
        context: str | None = None
        for record in records:
            context = self._merge_search_context(context, record.context)
        return context

    def _round_search_text(
        self,
        problem: str,
        transcript: str,
        round_number: int,
        focus: str | None = None,
    ) -> str:
        trimmed_transcript = transcript[-6000:] if len(transcript) > 6000 else transcript
        focus_block = f"\n이번에 더 확인할 쟁점:\n{focus}\n" if focus else ""
        return f"""원 문제:
{problem}

현재 토론 흐름:
{trimmed_transcript}
{focus_block}
이번은 {round_number}라운드 시작 전 공용 검색입니다. 최신 정보, 비교 기준, 실제 사례, 리스크, 누락 관점을 보완할 검색어를 만드세요."""

    def _fetch_round_research_context_stream(
        self,
        current_context: str | None,
        search_records: list[SearchRecord],
        text: str,
        mode: str,
        phase: str,
        round_number: int,
    ):
        normalized_mode = mode if mode in {"auto", "always", "off"} else "auto"
        if normalized_mode == "off":
            return current_context
        context, record = yield from self._fetch_search_context_stream(
            text=text,
            mode=normalized_mode,
            phase=phase,
            round_number=round_number,
        )
        search_records.append(record)
        return self._merge_search_context(current_context, context)

    def _fetch_search_context(
        self,
        text: str,
        mode: str,
        phase: str,
        round_number: int | None = None,
    ) -> tuple[str | None, SearchRecord]:
        stream = self._fetch_search_context_stream(text, mode, phase, round_number)
        while True:
            try:
                next(stream)
            except StopIteration as done:
                return done.value

    def _fetch_search_context_stream(
        self,
        text: str,
        mode: str,
        phase: str,
        round_number: int | None = None,
    ):
        started_at = time.monotonic()
        normalized_mode = mode if mode in {"auto", "always", "off"} else "auto"
        provider = self.search_client.provider if self.search_client.enabled else None
        yield self._search_event(
            "search_started",
            phase=phase,
            mode=normalized_mode,
            provider=provider,
            round_number=round_number,
        )
        if normalized_mode == "off":
            record = SearchRecord(
                phase=phase,
                round_number=round_number,
                mode="off",
                enabled=self.search_client.enabled,
                needed=False,
                status="off",
                provider=None,
                elapsed_ms=self._elapsed_ms(started_at),
            )
            terminal_log("search_skip", reason="off", mode=normalized_mode)
            yield self._search_event("search_finished", record=record)
            return None, record

        if not self.search_client.enabled:
            record = SearchRecord(
                phase=phase,
                round_number=round_number,
                mode=normalized_mode,
                enabled=False,
                needed=False,
                status="error",
                provider=None,
                error="Search client is disabled.",
                elapsed_ms=self._elapsed_ms(started_at),
            )
            terminal_log("search_error", error="SearchDisabled", detail=record.error)
            yield self._search_event("search_finished", record=record)
            return None, record
        queries: list[str] = []
        try:
            classification = self.search_client.classify(text, self.llm, mode=normalized_mode)
            queries = classification.queries
            if not classification.needs_search:
                record = SearchRecord(
                    phase=phase,
                    round_number=round_number,
                    mode=normalized_mode,
                    enabled=True,
                    needed=False,
                    status="not_needed",
                    provider=provider,
                    queries=queries,
                    elapsed_ms=self._elapsed_ms(started_at),
                )
                terminal_log("search_skip", reason="not_needed", mode=normalized_mode)
                yield self._search_event("search_finished", record=record, reason=classification.reason)
                return None, record
            terminal_log("search_classify", queries=queries)
            yield self._search_event(
                "search_queries",
                phase=phase,
                mode=normalized_mode,
                provider=provider,
                queries=queries,
                reason=classification.reason,
                round_number=round_number,
            )
            if hasattr(self.search_client, "fetch_tree"):
                tree_result = self.search_client.fetch_tree(queries, self.llm)
                context = tree_result.context
                flat_queries = tree_result.queries
                query_tree = tree_result.query_tree
                result_count = tree_result.result_count
            else:
                context = self.search_client.fetch(queries)
                flat_queries = queries
                query_tree = []
                result_count = len(context.splitlines()) if context else 0
            status = "fetched" if context else "no_results"
            terminal_log(
                "search_fetch",
                queries=len(flat_queries),
                provider=provider,
                results="no_results" if context is None else f"{result_count}건",
            )
            record = SearchRecord(
                phase=phase,
                round_number=round_number,
                mode=normalized_mode,
                enabled=True,
                needed=True,
                status=status,
                provider=provider,
                queries=flat_queries,
                query_tree=query_tree,
                result_count=result_count,
                context=context,
                elapsed_ms=self._elapsed_ms(started_at),
            )
            yield self._search_event("search_finished", record=record, reason=classification.reason)
            return context, record
        except Exception as exc:
            terminal_log("search_error", error=type(exc).__name__, detail=str(exc))
            record = SearchRecord(
                phase=phase,
                round_number=round_number,
                mode=normalized_mode,
                enabled=True,
                needed=True,
                status="error",
                provider=provider,
                queries=queries,
                error=str(exc),
                elapsed_ms=self._elapsed_ms(started_at),
            )
            yield self._search_event("search_finished", record=record)
            return None, record

    def _elapsed_ms(self, started_at: float) -> int:
        return max(0, int((time.monotonic() - started_at) * 1000))

    def _search_event(
        self,
        event_type: str,
        phase: str | None = None,
        mode: str | None = None,
        provider: str | None = None,
        queries: list[str] | None = None,
        reason: str | None = None,
        record: SearchRecord | None = None,
        round_number: int | None = None,
    ) -> StreamEvent:
        if record is not None:
            phase = record.phase
            mode = record.mode
            provider = record.provider
            queries = record.queries
            round_number = record.round_number
        root_queries = (
            [node.query for node in record.query_tree[:3]]
            if record is not None and record.query_tree
            else (queries or [])[:3]
        )
        event: StreamEvent = {
            "type": event_type,
            "phase": phase,
            "mode": mode,
            "provider": provider,
            "queries": queries or [],
            "round_number": round_number,
            "query_count": len(queries or []),
            "root_queries": root_queries,
        }
        if reason:
            event["reason"] = reason
        if record is not None:
            event.update(
                {
                    "enabled": record.enabled,
                    "needed": record.needed,
                    "status": record.status,
                    "result_count": record.result_count,
                    "error": record.error,
                    "elapsed_ms": record.elapsed_ms,
                }
            )
        return event

    def _strip_korean_suffix(self, term: str) -> str:
        suffixes = (
            "으로",
            "에서",
            "에게",
            "한테",
            "부터",
            "까지",
            "처럼",
            "보다",
            "라고",
            "이라고",
            "라면",
            "이면",
            "다고",
            "은",
            "는",
            "이",
            "가",
            "을",
            "를",
            "과",
            "와",
            "도",
            "만",
            "로",
        )
        for suffix in suffixes:
            if term.endswith(suffix) and len(term) > len(suffix) + 1:
                return term[: -len(suffix)]
        return term
