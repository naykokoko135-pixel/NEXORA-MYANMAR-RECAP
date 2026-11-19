import json
import os
import unittest
from unittest.mock import patch

from tmdb_movie_research import fetch_tmdb_movie, format_movie_source_report, research_movie_sources


class TmdbMovieResearchTests(unittest.TestCase):
    @patch.dict(os.environ, {"TMDB_API_READ_ACCESS_TOKEN": "x" * 40})
    @patch("tmdb_movie_research.urlopen")
    def test_exact_non_adult_match_and_imdb_external_id(self, mock_urlopen):
        class Response:
            def __init__(self, data):
                self.data = data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps(self.data).encode()

        mock_urlopen.side_effect = [
            Response({"results": [
                {"id": 42, "title": "Example Movie", "original_title": "Example Movie",
                 "release_date": "2020-01-01", "adult": False, "overview": "Short overview."},
                {"id": 43, "title": "Example Movie 2", "original_title": "Example Movie 2",
                 "release_date": "2021-01-01", "adult": False},
            ]}),
            Response({"id": 42, "title": "Example Movie", "original_title": "Example Movie",
                      "release_date": "2020-01-01", "adult": False,
                      "original_language": "en", "production_countries": [{"name": "United States"}],
                      "overview": "Longer overview.", "external_ids": {"imdb_id": "tt1234567"}}),
        ]
        result = fetch_tmdb_movie("Example Movie")
        self.assertTrue(result["found"])
        self.assertEqual(result["imdb_id"], "tt1234567")
        search_request = mock_urlopen.call_args_list[0].args[0]
        self.assertIn("include_adult=false", search_request.full_url)
        self.assertEqual(search_request.get_header("Authorization"), "Bearer " + "x" * 40)

    def test_missing_token_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            result = fetch_tmdb_movie("Example Movie")
        self.assertFalse(result["found"])
        self.assertIn("Token", result["status"])

    @patch("tmdb_movie_research.fetch_wikidata_metadata")
    @patch("tmdb_movie_research.fetch_tmdb_movie")
    def test_unexpected_tmdb_failure_preserves_wikidata_result(self, tmdb, wikidata):
        tmdb.side_effect = RuntimeError("provider schema changed")
        wikidata.return_value = {
            "found": True, "countries": ["Japan"], "year": "2023",
            "genres": ["anime"], "source": "https://www.wikidata.org/wiki/Q1",
        }
        report = research_movie_sources("Example")
        self.assertFalse(report["tmdb"]["found"])
        self.assertTrue(report["wikidata"]["found"])
        self.assertIn("TMDB", report["tmdb"]["status"])

    @patch("tmdb_movie_research.fetch_wikidata_metadata")
    @patch("tmdb_movie_research.fetch_tmdb_movie")
    def test_unexpected_wikidata_failure_preserves_tmdb_result(self, tmdb, wikidata):
        wikidata.side_effect = RuntimeError("provider schema changed")
        tmdb.return_value = {
            "found": True, "countries": ["Japan"], "year": "2023",
            "provider_url": "https://www.themoviedb.org/movie/1",
            "title": "Example", "overview": "Overview", "imdb_id": "",
        }
        report = research_movie_sources("Example")
        self.assertTrue(report["tmdb"]["found"])
        self.assertFalse(report["wikidata"]["found"])
        self.assertIn("Wikidata", report["wikidata"]["status"])

    def test_report_disclaims_commercial_use_and_imdb_scope(self):
        report = {
            "title": "Example",
            "tmdb": {"found": False, "status": "not configured"},
            "wikidata": {"found": False, "status": "not found"},
            "india_excluded": False,
            "year_conflict": False,
            "years": [],
            "eligibility": "unknown",
        }
        output = format_movie_source_report(report)
        self.assertIn("non-commercial", output)
        self.assertIn("IMDb ID", output)


if __name__ == "__main__":
    unittest.main()
