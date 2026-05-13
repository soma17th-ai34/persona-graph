from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Persona(BaseModel):
    id: str
    name: str
    role: str
    perspective: str
    priority_questions: list[str] = Field(default_factory=list)
    character: Optional["Character"] = None


class Character(BaseModel):
    id: str
    name: str
    archetype: str
    tagline: str
    visual: str
    speech_style: str
    motion: str = ""
    relationship: str = ""
    texture: str = ""
    color: str
    accent_color: str
    symbol: str


class AgentMessage(BaseModel):
    stage: Literal[
        "persona_generation",
        "user",
        "moderator",
        "specialist",
        "debate",
        "critic",
        "synthesizer",
    ]
    agent_id: str
    agent_name: str
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SolveRequest(BaseModel):
    problem: str = Field(..., min_length=5)
    persona_count: int = Field(default=5, ge=3, le=5)
    debate_rounds: int = Field(default=1, ge=1, le=3)
    use_llm: bool = True
    model: Optional[str] = None
    search_mode: Literal["auto", "always", "off"] = "auto"
    temperature: float = Field(default=0.35, ge=0.0, le=1.2)


class ContinueRequest(BaseModel):
    content: str = Field(..., min_length=1)
    max_agents: int = Field(default=2, ge=1, le=3)
    use_llm: bool = True
    model: Optional[str] = None
    search_mode: Literal["auto", "always", "off"] = "auto"
    temperature: float = Field(default=0.35, ge=0.0, le=1.2)


class ModelOption(BaseModel):
    id: str
    label: str
    provider: Optional[str] = None


class ModelCatalogResponse(BaseModel):
    default_model: str
    models: list[ModelOption]


class Evaluation(BaseModel):
    consistency: int = Field(..., ge=1, le=5)
    specificity: int = Field(..., ge=1, le=5)
    risk_awareness: int = Field(..., ge=1, le=5)
    feasibility: int = Field(..., ge=1, le=5)
    overall_comment: str
    improvement_suggestions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchRecord(BaseModel):
    phase: Literal["initial", "followup"]
    mode: Literal["auto", "always", "off"]
    enabled: bool
    needed: bool
    status: Literal["off", "not_needed", "fetched", "no_results", "error"]
    provider: Optional[str] = None
    queries: list[str] = Field(default_factory=list)
    result_count: int = 0
    context: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReasoningCandidate(BaseModel):
    id: str
    title: str
    answer_preview: str


class ReasoningRecord(BaseModel):
    phase: Literal["initial", "followup"]
    stage: Literal["synthesis"]
    mode: Literal["tree"]
    enabled: bool
    status: Literal["selected", "skipped_no_llm", "fallback", "error"]
    candidate_count: int = 0
    candidates: list[ReasoningCandidate] = Field(default_factory=list)
    selected_id: Optional[str] = None
    selection_summary: Optional[str] = None
    scores: dict[str, int] = Field(default_factory=dict)
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MemoryRecord(BaseModel):
    phase: Literal["initial", "followup"]
    enabled: bool
    status: Literal["selected", "empty", "error"]
    selected_run_ids: list[str] = Field(default_factory=list)
    positive_count: int = 0
    negative_count: int = 0
    context: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SolveResponse(BaseModel):
    run_id: Optional[str] = None
    problem: str
    personas: list[Persona]
    messages: list[AgentMessage]
    final_answer: str
    evaluation: Evaluation
    search_records: list[SearchRecord] = Field(default_factory=list)
    reasoning_records: list[ReasoningRecord] = Field(default_factory=list)
    memory_records: list[MemoryRecord] = Field(default_factory=list)
    used_llm: bool
    model: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RunSummary(BaseModel):
    run_id: str
    problem_preview: str
    created_at: datetime
    used_llm: bool
    model: str
    average_score: float
