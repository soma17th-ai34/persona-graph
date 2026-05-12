from __future__ import annotations

import os
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

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
        return True

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
        if not queries:
            return None
        if self._client is None:
            return self._fetch_duckduckgo(queries)
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

    def _fetch_duckduckgo(self, queries: list[str]) -> str | None:
        lines: list[str] = []
        for query in queries:
            try:
                url = f"https://duckduckgo.com/html/?{urlencode({'q': query})}"
                request = Request(url, headers={"User-Agent": "PersonaGraph/1.0"})
                with urlopen(request, timeout=8) as response:
                    html = response.read().decode("utf-8", errors="ignore")
                for title, href, snippet in _parse_duckduckgo_results(html)[:3]:
                    body = snippet or href
                    if title and body:
                        lines.append(f"[{title}] {body[:300]}")
            except Exception:
                continue
        return "\n".join(lines[:9]) if lines else None


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._active_field: str | None = None

    def handle_starttag(self, tag: str, attrs):
        attrs_dict = dict(attrs)
        class_name = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in class_name:
            self._current = {
                "title": "",
                "href": _clean_duckduckgo_url(attrs_dict.get("href", "")),
                "snippet": "",
            }
            self._active_field = "title"
            self.results.append(self._current)
            return
        if self._current is not None and "result__snippet" in class_name:
            self._active_field = "snippet"

    def handle_endtag(self, tag: str):
        if tag == "a" and self._active_field == "title":
            self._active_field = None
        elif self._active_field == "snippet":
            self._active_field = None

    def handle_data(self, data: str):
        if self._current is None or self._active_field is None:
            return
        value = " ".join(data.split())
        if not value:
            return
        existing = self._current.get(self._active_field, "")
        self._current[self._active_field] = f"{existing} {value}".strip()


def _parse_duckduckgo_results(html: str) -> list[tuple[str, str, str]]:
    parser = _DuckDuckGoResultParser()
    parser.feed(html)
    parsed: list[tuple[str, str, str]] = []
    for item in parser.results:
        title = item.get("title", "").strip()
        href = item.get("href", "").strip()
        snippet = item.get("snippet", "").strip()
        if title:
            parsed.append((title, href, snippet))
    return parsed


def _clean_duckduckgo_url(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    if parsed.path == "/l/":
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return href
