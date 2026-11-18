import json
import unittest
from io import BytesIO
from urllib.error import URLError
from unittest.mock import patch

from auto_research import search_movie_sources, ResearchLookupError


class Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


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
        mock_urlopen.return_value = Response(json.dumps(payload).encode("utf-8"))
        result = search_movie_sources("Avatar")
        self.assertLess(result.index("Avatar (2009 film)"), result.index("Avatar: The Way of Water"))
        self.assertIn("အမည်ကိုက်ညီသော ရလဒ်", result)
        self.assertIn("ဆက်စပ်ရလဒ်", result)

    @patch("auto_research.urlopen")
    def test_excludes_unrelated_search_hits(self, mock_urlopen):
        payload = {
            "query": {"pages": [
                {"title": "9th Crunchyroll Anime Awards", "extract": "Awards ceremony.", "fullurl": "https://example.com/awards"},
                {"title": "Atsumi Tanezaki", "extract": "Voice actress.", "fullurl": "https://example.com/voice"},
                {"title": "Demon Slayer: Kimetsu no Yaiba", "extract": "Different anime.", "fullurl": "https://example.com/demonslayer"},
            ]}
        }
        mock_urlopen.return_value = Response(json.dumps(payload).encode("utf-8"))
        result = search_movie_sources("Frieren: Beyond Journey's End")
        self.assertIn("ကိုက်ညီမှုရှိသော Wikipedia ဆောင်းပါး မတွေ့ပါ", result)
        self.assertNotIn("Atsumi Tanezaki", result)
        self.assertNotIn("Demon Slayer", result)
        self.assertNotIn("Crunchyroll Anime Awards", result)

    @patch("auto_research.urlopen")
    def test_uses_rest_fallback_when_action_api_fails(self, mock_urlopen):
        rest_payload = {
            "pages": [{
                "title": "Avatar",
                "key": "Avatar",
                "excerpt": "Avatar is a science fiction film.",
            }]
        }
        mock_urlopen.side_effect = [
            URLError("primary unavailable"),
            Response(json.dumps(rest_payload).encode("utf-8")),
        ]
        result = search_movie_sources("Avatar")
        self.assertIn("Avatar", result)
        self.assertIn("https://en.wikipedia.org/wiki/Avatar", result)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("auto_research.urlopen")
    def test_reports_both_sources_unavailable(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("offline")
        with self.assertRaises(ResearchLookupError):
            search_movie_sources("Avatar")

    def test_rejects_empty_title(self):
        with self.assertRaises(ResearchLookupError):
            search_movie_sources("  ")

    @patch("auto_research.urlopen")
    def test_handles_no_results(self, mock_urlopen):
        mock_urlopen.return_value = Response(b'{"query":{"pages":[]}}')
        self.assertIn("မတွေ့ပါ", search_movie_sources("Unknown film title"))


if __name__ == "__main__":
    unittest.main()
