import unittest
from unittest.mock import patch

from recap_metadata_resolver import resolve_recap_metadata


class ResolverProviderIsolationTests(unittest.TestCase):
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    def test_wikidata_exception_does_not_discard_tmdb_movie(self, tmdb, wikidata):
        wikidata.side_effect = RuntimeError("provider schema changed")
        tmdb.return_value = {
            "found": True,
            "countries": ["Japan"],
            "year": "2023",
            "provider_url": "https://www.themoviedb.org/movie/1",
            "title": "Example Movie",
            "overview": "Overview",
            "imdb_id": "",
        }
        with patch("recap_metadata_resolver.research_anime_sources", return_value={
            "india_excluded": False, "anilist": {"found": False},
            "tenrai": {"found": False},
        }):
            result = resolve_recap_metadata("Example Movie")
        self.assertTrue(result["found"])
        self.assertEqual(result["metadata_source"], "TMDB")

    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    def test_tmdb_exception_preserves_wikidata_result(self, tmdb, wikidata):
        tmdb.side_effect = RuntimeError("provider unavailable")
        wikidata.return_value = {
            "found": True,
            "countries": ["Japan"],
            "year": "2023",
            "description": "Japanese animated television series",
            "source": "https://www.wikidata.org/wiki/Q1",
            "title": "Example Anime",
        }
        result = resolve_recap_metadata("Example Anime")
        self.assertTrue(result["found"])
        self.assertEqual(result["metadata_source"], "Wikidata")

    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.research_anime_sources")
    def test_all_provider_exceptions_fail_closed(self, anime, tmdb, wikidata):
        wikidata.side_effect = RuntimeError("Wikidata down")
        tmdb.side_effect = RuntimeError("TMDB down")
        anime.side_effect = RuntimeError("Anime catalogue down")
        result = resolve_recap_metadata("Unknown Title")
        self.assertFalse(result["found"])
        self.assertIn("အတိအကျ အတည်မပြုနိုင်", result["status"])


if __name__ == "__main__":
    unittest.main()
