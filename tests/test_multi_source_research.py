import unittest
from unittest.mock import patch

from multi_source_research import (
    fetch_tenrai_synopsis,
    format_anime_source_report,
    research_anime_sources,
)


class MultiSourceResearchTests(unittest.TestCase):
    @patch("multi_source_research.urlopen")
    def test_tenrai_requires_one_exact_title_and_strict_sfw(self, mock_urlopen):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                import json
                return json.dumps({"data": [
                    {"mal_id": 1, "title": "Frieren: Beyond Journey's End",
                     "title_english": "Frieren: Beyond Journey's End",
                     "synopsis": "A" * 120, "url": "https://myanimelist.net/anime/1"},
                    {"mal_id": 2, "title": "Frieren Another Story",
                     "synopsis": "B" * 120},
                ]}).encode()
        mock_urlopen.return_value = Response()
        result = fetch_tenrai_synopsis("Frieren: Beyond Journey's End")
        self.assertTrue(result["found"])
        request_url = mock_urlopen.call_args.args[0].full_url
        self.assertIn("sfw-strict=true", request_url)

    @patch("multi_source_research.fetch_wikidata_metadata")
    @patch("multi_source_research.fetch_tenrai_synopsis")
    @patch("multi_source_research.fetch_anilist_synopsis")
    def test_country_unknown_is_not_assumed_and_india_is_excluded(
        self, anilist, tenrai, wikidata
    ):
        anilist.return_value = {"found": True, "country": "", "year": "2023"}
        tenrai.return_value = {"found": True, "year": "2023"}
        wikidata.return_value = {"found": False, "status": "not found"}
        report = research_anime_sources("Example")
        self.assertIn("မူရင်းနိုင်ငံကို အတည်မပြုနိုင်သေး", report["eligibility"])
        anilist.return_value = {"found": True, "country": "IN", "year": "2023"}
        report = research_anime_sources("Example")
        self.assertTrue(report["india_excluded"])

    def test_report_is_clear_about_scope(self):
        report = {
            "title": "Example",
            "anilist": {"found": False, "status": "not found"},
            "tenrai": {"found": False, "status": "not found"},
            "wikidata": {"found": False, "status": "not found"},
            "eligibility": "unknown",
            "india_excluded": False,
            "year_conflict": False,
            "years": [],
        }
        output = format_anime_source_report(report)
        self.assertIn("episode ဇာတ်ကွက်အပြည့် မဟုတ်ပါ", output)
        self.assertIn("license", output)


if __name__ == "__main__":
    unittest.main()
