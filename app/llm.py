from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

DEFAULT_MODEL = "gpt-5.4-mini"


@dataclass
class LLMResult:
    content: str
    used_llm: bool
    error: str | None = None


class LLMClient:
    """Small OpenAI-compatible LLM wrapper with a graceful local fallback path."""

    def __init__(self, model: str | None = None, temperature: float = 0.35, enabled: bool = True):
        load_dotenv()
        self.model = model or os.getenv("PERSONA_GRAPH_MODEL", DEFAULT_MODEL)
        self.temperature = temperature
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.enabled = enabled and bool(self.api_key)
        self._client = None
        self._init_error: str | None = None

        if self.enabled:
            try:
                from openai import OpenAI

                kwargs: dict[str, Any] = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
            except Exception as exc:  # pragma: no cover - depends on local package setup
                self.enabled = False
                self._init_error = str(exc)

    @property
    def unavailable_reason(self) -> str:
        if self._init_error:
            return self._init_error
        if not self.api_key:
            return "OPENAI_API_KEY is not set."
        return "LLM client is disabled."

    def complete(self, system_prompt: str, user_prompt: str, temperature: float | None = None) -> LLMResult:
        if not self.enabled or self._client is None:
            return LLMResult(content="", used_llm=False, error=self.unavailable_reason)

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature if temperature is None else temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content or ""
            return LLMResult(content=content.strip(), used_llm=True)
        except Exception as exc:
            return LLMResult(content="", used_llm=False, error=str(exc))


def parse_json_object(raw: str) -> Any | None:
    """Extract JSON from a plain or fenced model response."""
    if not raw:
        return None

    text = raw.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    candidates = [text]
    if "[" in text and "]" in text:
        candidates.append(text[text.find("[") : text.rfind("]") + 1])
    if "{" in text and "}" in text:
        candidates.append(text[text.find("{") : text.rfind("}") + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None
