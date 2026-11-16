import json
import unittest
from io import BytesIO
from unittest.mock import patch

from auto_research import search_movie_sources, ResearchLookupError


class AutoResearchTests(unittest.TestCase):
    @patch("auto_research.urlopen")
    def test_returns_short_source_excerpt_and_link(self, mock_urlopen):
        payload = {
            "query": {
                "pages": [{
                    "title": "Avatar (2009 film)",
                    "extract": "Avatar is a 2009 epic science fiction film.",
                    "fullurl": "https://en.wikipedia.org/wiki/Avatar_(2009_film)",
                }]
            }
        }

        class Response(BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.close()

        mock_urlopen.return_value = Response(json.dumps(payload).encode("utf-8"))
        result = search_movie_sources("Avatar")
        self.assertIn("Avatar (2009 film)", result)
        self.assertIn("https://en.wikipedia.org/wiki/Avatar_(2009_film)", result)
        self.assertIn("အတည်ပြုထားသော ဇာတ်လမ်းအကျဉ်း မဟုတ်ပါ", result)


    @patch("auto_research.urlopen")
    def test_prioritizes_exact_title_over_sequels(self, mock_urlopen):
        payload = {
            "query": {"pages": [
                {"title": "Avatar: The Way of Water", "extract": "Sequel.", "fullurl": "https://example.com/sequel"},
                {"title": "Avatar Aang: The Last Airbender", "extract": "Animation.", "fullurl": "https://example.com/aang"},
                {"title": "Avatar (2009 film)", "extract": "Original film.", "fullurl": "https://example.com/avatar"},
            ]}
        }

        class Response(BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.close()

        mock_urlopen.return_value = Response(json.dumps(payload).encode("utf-8"))
        result = search_movie_sources("Avatar")
        self.assertLess(result.index("Avatar (2009 film)"), result.index("Avatar: The Way of Water"))
        self.assertIn("အမည်ကိုက်ညီသော ရလဒ်", result)
        self.assertIn("ဆက်စပ်ရလဒ်", result)

    def test_rejects_empty_title(self):
        with self.assertRaises(ResearchLookupError):
            search_movie_sources("  ")

    @patch("auto_research.urlopen")
    def test_handles_no_results(self, mock_urlopen):
        class Response(BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.close()

        mock_urlopen.return_value = Response(b'{"query":{"pages":[]}}')
        self.assertIn("မတွေ့ပါ", search_movie_sources("Unknown film title"))


if __name__ == "__main__":
    unittest.main()
