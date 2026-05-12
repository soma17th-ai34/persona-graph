from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from app.llm import LLMClient, parse_json_object


@dataclass
class Classification:
    needs_search: bool
    queries: list[str] = field(default_factory=list)


class SearchClient:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("TAVILY_API_KEY")
        self._client = None
        if self.api_key:
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=self.api_key)
            except Exception:
                pass

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def classify(self, text: str, llm: LLMClient) -> Classification:
        result = llm.complete(
            system_prompt="당신은 질문 분류기입니다. 엄격한 JSON만 반환하세요.",
            user_prompt=f"""다음 질문이 외부 검색(최신 정보, 실제 수치, 상품 비교 등)을 통해 답변 품질이 유의미하게 높아지는지 판단하세요.

질문: {text}

반드시 JSON 객체만 반환하세요.
- needs_search: true 또는 false
- queries: 검색어 배열 (needs_search가 true일 때만, 최대 3개, 한국어 또는 영어)""",
            temperature=0.0,
        )
        if not result.used_llm or not result.content:
            return Classification(needs_search=False)
        parsed = parse_json_object(result.content)
        if not isinstance(parsed, dict):
            return Classification(needs_search=False)
        needs = bool(parsed.get("needs_search"))
        queries = [str(q).strip() for q in parsed.get("queries", []) if str(q).strip()][:3]
        return Classification(needs_search=needs and bool(queries), queries=queries)

    def fetch(self, queries: list[str]) -> str | None:
        if not self.enabled or not queries:
            return None
        lines: list[str] = []
        for query in queries:
            try:
                response = self._client.search(query, max_results=3)
                for item in response.get("results", []):
                    title = item.get("title", "").strip()
                    content = item.get("content", "").strip()
                    if content:
                        lines.append(f"[{title}] {content[:300]}")
            except Exception:
                continue
        return "\n".join(lines) if lines else None
