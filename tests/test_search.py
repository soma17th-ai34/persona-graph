import unittest

from app.search import _clean_duckduckgo_url, _parse_duckduckgo_results


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
