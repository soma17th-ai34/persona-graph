from __future__ import annotations

import os
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from app.llm import LLMClient, parse_json_object
from app.prompt_examples import SEARCH_QUERY_REWRITE_EXAMPLES


@dataclass
class Classification:
    needs_search: bool
    queries: list[str] = field(default_factory=list)
    reason: str = ""


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

    @property
    def provider(self) -> str:
        return "tavily" if self._client is not None else "duckduckgo"

    def classify(self, text: str, llm: LLMClient, mode: str = "auto") -> Classification:
        normalized_mode = mode if mode in {"auto", "always", "off"} else "auto"
        stripped = text.strip()
        if normalized_mode == "off":
            return Classification(needs_search=False, reason="off")

        if normalized_mode == "always":
            queries = self._rewrite_queries(stripped, llm, [stripped] if stripped else [])
            return Classification(
                needs_search=bool(queries),
                queries=queries[:3],
                reason="always",
            )

        local_needs_search = self._local_needs_search(stripped)
        llm_classification = self._classify_with_llm(stripped, llm)
        fallback_queries = llm_classification.queries or ([stripped] if stripped else [])

        if llm_classification.needs_search:
            queries = self._rewrite_queries(stripped, llm, fallback_queries)
            return Classification(
                needs_search=bool(queries),
                queries=queries[:3],
                reason=llm_classification.reason or "llm",
            )
        if local_needs_search:
            queries = self._rewrite_queries(stripped, llm, fallback_queries)
            return Classification(
                needs_search=bool(queries),
                queries=queries[:3],
                reason="heuristic",
            )
        return Classification(needs_search=False, queries=[], reason="not_needed")

    def _classify_with_llm(self, text: str, llm: LLMClient) -> Classification:
        result = llm.complete(
            system_prompt="당신은 질문 분류기입니다. 엄격한 JSON만 반환하세요.",
            user_prompt=f"""다음 질문이 외부 검색을 통해 답변 품질이 유의미하게 높아지는지 판단하세요.

검색이 필요한 경우:
- 최신 정보, 현재 상태, 실제 수치, 가격, 상품 비교, 뉴스, 정책, 회사/인물 현황
- 추천 질문 중 시간/장소/가격/메타/트렌드가 중요한 경우
- 게임 메타, 챔피언 패치, 식당/메뉴, 여행, 상품, AI 모델/API/라이브러리/프레임워크처럼 정보가 자주 바뀌는 주제

질문: {text}

반드시 JSON 객체만 반환하세요.
- needs_search: true 또는 false
- queries: 검색어 배열 (needs_search가 true일 때만, 최대 3개, 한국어 또는 영어)""",
            temperature=0.0,
        )
        if not result.used_llm or not result.content:
            return Classification(needs_search=False, reason="llm_unavailable")
        parsed = parse_json_object(result.content)
        if not isinstance(parsed, dict):
            return Classification(needs_search=False, reason="llm_parse_error")
        needs = bool(parsed.get("needs_search"))
        queries = [str(q).strip() for q in parsed.get("queries", []) if str(q).strip()][:3]
        return Classification(needs_search=needs and bool(queries), queries=queries, reason="llm")

    def _rewrite_queries(self, text: str, llm: LLMClient, fallback_queries: list[str]) -> list[str]:
        fallback = [query.strip() for query in fallback_queries if query.strip()][:3]
        if not text.strip():
            return fallback

        result = llm.complete(
            system_prompt="당신은 웹 검색어 재작성기입니다. 엄격한 JSON만 반환하세요.",
            user_prompt=f"""사용자 입력을 검색엔진 친화적인 검색어 1~3개로 바꾸세요.

예시는 형식과 판단 기준만 참고하고, 예시 문장을 그대로 복사하지 마세요.
{SEARCH_QUERY_REWRITE_EXAMPLES}

사용자 입력:
{text}

출력 JSON 형식:
{{"queries": ["검색어 1", "검색어 2"]}}

규칙:
- 너무 긴 원문 전체를 그대로 검색어로 쓰지 마세요.
- 최신성, 비교, 가격, 사례, 프레임워크, 시뮬레이션처럼 검색 목적이 드러나게 하세요.
- 한국어 질문이어도 영어 검색어가 더 정확하면 영어를 섞으세요.
- API 키, 개인정보, 내부 설정값은 검색어에 넣지 마세요.""",
            temperature=0.0,
        )
        if not result.used_llm or not result.content:
            return fallback

        parsed = parse_json_object(result.content)
        if not isinstance(parsed, dict):
            return fallback

        queries = [str(query).strip() for query in parsed.get("queries", []) if str(query).strip()]
        return queries[:3] or fallback

    def _local_needs_search(self, text: str) -> bool:
        normalized = text.lower()
        compact = "".join(normalized.split())
        terms = (
            "오늘",
            "요즘",
            "최근",
            "현재",
            "최신",
            "이번",
            "2026",
            "패치",
            "추천",
            "비교",
            "순위",
            "가격",
            "후기",
            "사례",
            "트렌드",
            "롤",
            "챔프",
            "메타",
            "승률",
            "픽률",
            "식당",
            "메뉴",
            "맛집",
            "배달",
            "여행",
            "숙소",
            "상품",
            "노트북",
            "폰",
            "라이브러리",
            "프레임워크",
            "회사",
            "정책",
            "뉴스",
        )
        phrases = (
            "ai모델",
            "ai model",
            "aiagent",
            "ai agent",
            "api",
        )
        return any(term in normalized for term in terms) or any(phrase in compact for phrase in phrases)

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
