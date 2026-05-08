from __future__ import annotations

import base64
import html
import os
import re

import streamlit as st

from app.characters import CHARACTER_POOL


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SAMPLE_PROBLEMS = {
    "Software Maestro 프로젝트 선정": "2026 Software Maestro를 목표로 2주 안에 보여줄 수 있는 AI 프로젝트 MVP를 정해야 한다. 포트폴리오 가치, 데모 안정성, 구현 난이도를 함께 고려해줘.",
    "캠퍼스 팀 프로젝트 리스크": "4명 팀이 3주 안에 AI 기반 학습 도우미를 만들어야 한다. 기능 욕심이 많고 역할 분담이 애매하다. 성공 가능성을 높이는 계획을 제안해줘.",
    "Physical AI 아이디어 검증": "저예산으로 Physical AI 프로젝트를 시작하고 싶다. 하드웨어 구매 전에 시뮬레이션과 소프트웨어 MVP로 검증할 방법을 찾아줘.",
}

STAGE_LABELS = {
    "persona_generation": "페르소나 생성",
    "user": "사용자 의견",
    "moderator": "사회자 진행",
    "specialist": "전문가 의견",
    "debate": "Agent 대화",
    "critic": "비판",
    "synthesizer": "최종 종합",
    "evaluator": "내부 검증",
}

SOURCE_LABELS = {
    "llm": "LLM",
    "fallback": "기본 응답",
    "user": "사용자",
    "unknown": "알 수 없음",
}

HERO_IMAGE_PATH = os.path.join(
    ROOT_DIR, "assets", "hero", "personagraph-agent-network.png"
)
PERSONA_IMAGE_DIR = os.path.join(ROOT_DIR, "assets", "personas")
CHARACTER_IMAGE_PATHS = {
    "nori": os.path.join(PERSONA_IMAGE_DIR, "nori.png"),
    "orbit": os.path.join(PERSONA_IMAGE_DIR, "orbit.png"),
    "milmil": os.path.join(PERSONA_IMAGE_DIR, "milmil.png"),
    "sori": os.path.join(PERSONA_IMAGE_DIR, "sori.png"),
    "mori": os.path.join(PERSONA_IMAGE_DIR, "mori.png"),
    "gyeol": os.path.join(PERSONA_IMAGE_DIR, "gyeol.png"),
    "jari": os.path.join(PERSONA_IMAGE_DIR, "jari.png"),
    "sallycore": os.path.join(PERSONA_IMAGE_DIR, "sallycore.png"),
    "lumi": os.path.join(PERSONA_IMAGE_DIR, "lumi.png"),
    "haneul": os.path.join(PERSONA_IMAGE_DIR, "haneul.png"),
}
CHARACTERS_BY_ID = {character.id: character for character in CHARACTER_POOL}


@st.cache_data(show_spinner=False)
def image_data_uri(path: str) -> str:
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    extension = os.path.splitext(path)[1].lower().lstrip(".") or "png"
    if extension == "jpg":
        extension = "jpeg"
    return f"data:image/{extension};base64,{encoded}"

def chat_stage_label(message) -> str:
    if message.stage == "specialist":
        return "첫 의견"
    if message.stage == "debate" and message.metadata.get("phase") == "user_response":
        return "Agent 답변"
    if message.stage == "synthesizer" and message.metadata.get("phase") == "followup_synthesis":
        return "중간 정리"
    if message.stage == "debate":
        return "Agent 대화"
    if message.stage == "user":
        return "내 의견"
    return STAGE_LABELS.get(message.stage, message.stage)

def normalize_summary_text(text: str) -> str:
    cleaned = re.sub(r"\*\*([^*]+?)\*\*", r"\1", text)
    cleaned = re.sub(r"^[-*]\s+", "", cleaned)
    cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned)
    cleaned = re.sub(r"^(요약|정리)\s*[:：]\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()

def is_structural_heading(text: str) -> bool:
    headings = {
        "핵심 판단",
        "근거",
        "실행 제안",
        "주의할 점",
        "모순 또는 충돌",
        "약한 가정",
        "누락된 관점",
        "최종 통합 전에 고쳐야 할 점",
        "최종 결론",
        "선택한 방향",
        "실행 단계",
        "리스크와 대응",
        "다음 24시간 액션",
    }
    return text in headings

def trim_summary(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1].rstrip()}..."

def live_message_frames(content: str) -> list[str]:
    content = content.strip()
    if not content:
        return [""]

    if len(content) <= 70:
        return [content]

    frame_count = min(8, max(2, len(content) // 140))
    step = max(70, len(content) // frame_count)
    frames: list[str] = []
    cursor = step
    while cursor < len(content):
        boundary = max(
            content.rfind("\n", 0, cursor),
            content.rfind(". ", 0, cursor),
            content.rfind("다.", 0, cursor),
            content.rfind("요.", 0, cursor),
            content.rfind(" ", 0, cursor),
        )
        previous_length = len(frames[-1]) if frames else 0
        if boundary > previous_length + 35:
            cursor = sentence_boundary_end(content, boundary)
        frame = content[:cursor].rstrip()
        if not frames or frame != frames[-1]:
            frames.append(frame)
        cursor += step

    if not frames or frames[-1] != content:
        frames.append(content)
    return frames

def sentence_boundary_end(content: str, boundary: int) -> int:
    for marker in ("다.", "요.", ". "):
        if content.startswith(marker, boundary):
            return boundary + len(marker)
    return boundary + 1

def message_content_html(content: str) -> str:
    safe_content = html.escape(content.strip())
    safe_content = re.sub(r"\*\*([^*\n]+?)\*\*", r"<strong>\1</strong>", safe_content)
    return safe_content.replace("\n", "<br>")

def character_for_persona(persona):
    if persona and persona.character:
        return CHARACTERS_BY_ID.get(persona.character.id, persona.character)
    return None

def character_class(character) -> str:
    if not character:
        return ""
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", character.id)
    return f"pg-character-{safe_id}"

def avatar_markup(name: str, character=None, fallback: str | None = None) -> str:
    if character:
        image_path = CHARACTER_IMAGE_PATHS.get(character.id)
        if image_path and os.path.exists(image_path):
            return (
                f'<img class="pg-chat-avatar-img" src="{image_data_uri(image_path)}" '
                f'alt="{html.escape(name)}">'
            )
    initials = html.escape((fallback or name[:2] or "AI").upper())
    return f'<div class="pg-chat-avatar-fallback">{initials}</div>'

def stage_meta_label(message) -> str:
    label = chat_stage_label(message)
    source = message.metadata.get("source", "unknown")
    if source == "fallback":
        return f"{label} · 기본 응답"
    return label

def system_avatar_label(agent_id: str, agent_name: str, stage: str) -> str:
    return {
        "moderator": "MOD",
        "critic": "CR",
        "synthesizer": "FIN",
        "evaluator": "EV",
        "persona_generator": "PG",
    }.get(agent_id, agent_name[:2].upper() if agent_name else stage[:2].upper())
