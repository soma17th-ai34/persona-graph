import unittest

from app.llm import LLMClient, LLMResult
from app.search import SearchClient, _clean_duckduckgo_url, _parse_duckduckgo_results


class FakeLLM:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def complete(self, system_prompt: str, user_prompt: str, temperature=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "temperature": temperature,
            }
        )
        if not self.results:
            raise AssertionError("FakeLLM received more calls than expected")
        return self.results.pop(0)


class SearchFallbackTest(unittest.TestCase):
    def test_parse_duckduckgo_results_extracts_title_url_and_snippet(self):
        html = """
        <div class="result">
            <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fpost">Example Title</a>
            <a class="result__snippet">Short search result summary.</a>
        </div>
        """

        results = _parse_duckduckgo_results(html)

        self.assertEqual(
            [("Example Title", "https://example.com/post", "Short search result summary.")],
            results,
        )

    def test_clean_duckduckgo_url_leaves_regular_urls_unchanged(self):
        self.assertEqual(
            "https://example.com/path",
            _clean_duckduckgo_url("https://example.com/path"),
        )

    def test_aggressive_auto_searches_dinner_recommendations(self):
        classification = SearchClient().classify(
            "오늘 저녁 추천해줘",
            LLMClient(enabled=False),
            mode="auto",
        )

        self.assertTrue(classification.needs_search)
        self.assertEqual(["오늘 저녁 추천해줘"], classification.queries)
        self.assertEqual("heuristic", classification.reason)

    def test_aggressive_auto_searches_lol_champion_recommendations(self):
        classification = SearchClient().classify(
            "롤 탑 미드 챔프 추천해줘",
            LLMClient(enabled=False),
            mode="auto",
        )

        self.assertTrue(classification.needs_search)
        self.assertEqual(["롤 탑 미드 챔프 추천해줘"], classification.queries)

    def test_off_mode_skips_search(self):
        classification = SearchClient().classify(
            "오늘 저녁 추천해줘",
            LLMClient(enabled=False),
            mode="off",
        )

        self.assertFalse(classification.needs_search)
        self.assertEqual([], classification.queries)
        self.assertEqual("off", classification.reason)

    def test_always_mode_uses_original_query_without_llm(self):
        classification = SearchClient().classify(
            "일반적인 고민도 검색해줘",
            LLMClient(enabled=False),
            mode="always",
        )

        self.assertTrue(classification.needs_search)
        self.assertEqual(["일반적인 고민도 검색해줘"], classification.queries)
        self.assertEqual("always", classification.reason)

    def test_always_mode_rewrites_query_with_llm(self):
        llm = FakeLLM(
            [
                LLMResult(
                    content='{"queries": ["low budget Physical AI MVP robotics simulation validation", "robotics simulation before hardware purchase MVP"]}',
                    used_llm=True,
                )
            ]
        )

        classification = SearchClient().classify(
            "저예산으로 Physical AI 프로젝트를 시작하고 싶다. 하드웨어 구매 전에 시뮬레이션과 소프트웨어 MVP로 검증할 방법을 찾아줘.",
            llm,
            mode="always",
        )

        self.assertTrue(classification.needs_search)
        self.assertEqual(
            [
                "low budget Physical AI MVP robotics simulation validation",
                "robotics simulation before hardware purchase MVP",
            ],
            classification.queries,
        )
        self.assertNotIn("저예산으로", classification.queries[0])
        self.assertIn("검색어 재작성기", llm.calls[0]["system_prompt"])

    def test_auto_mode_uses_rewritten_query_after_search_needed(self):
        llm = FakeLLM(
            [
                LLMResult(
                    content='{"needs_search": true, "queries": ["Physical AI 프로젝트 검증"]}',
                    used_llm=True,
                ),
                LLMResult(
                    content='{"queries": ["Physical AI MVP simulation validation examples"]}',
                    used_llm=True,
                ),
            ]
        )

        classification = SearchClient().classify(
            "요즘 Physical AI MVP 검증 사례를 찾아줘.",
            llm,
            mode="auto",
        )

        self.assertTrue(classification.needs_search)
        self.assertEqual(["Physical AI MVP simulation validation examples"], classification.queries)
        self.assertEqual("llm", classification.reason)
