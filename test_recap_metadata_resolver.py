import unittest
from unittest.mock import patch

from recap_metadata_resolver import resolve_recap_metadata


class RecapMetadataResolverTests(unittest.TestCase):
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_wikidata_remains_primary(self, wikidata, tmdb):
        wikidata.return_value = {
            "found": True, "title": "Example", "countries": ["United States"],
            "year": "2020", "description": "film", "source": "https://www.wikidata.org/wiki/Q1",
        }
        tmdb.return_value = {"found": False, "status": "TMDB token missing"}
        result = resolve_recap_metadata("Example")
        self.assertTrue(result["found"])
        self.assertEqual(result["provider"], "Wikidata")
        self.assertEqual(result["metadata_confidence"], "exact_title_match")
        tmdb.assert_called_once_with("Example")

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_tmdb_exact_movie_is_used_when_wikidata_fails(self, wikidata, tmdb, anime):
        wikidata.return_value = {"found": False, "status": "ambiguous"}
        anime.return_value = {"india_excluded": False, "anilist": {"found": False}, "tenrai": {"found": False}}
        tmdb.return_value = {
            "found": True, "title": "The General", "countries": ["United States"],
            "year": "1926", "provider_url": "https://www.themoviedb.org/movie/1",
            "overview": "A silent comedy.",
        }
        result = resolve_recap_metadata("The General (1926)")
        self.assertTrue(result["found"])
        self.assertEqual(result["provider"], "TMDB")
        self.assertEqual(result["year"], "1926")
        self.assertEqual(result["countries"], ["United States"])
        anime.assert_called_once_with("The General (1926)")

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_anilist_exact_anime_is_used_with_known_country(self, wikidata, tmdb, anime):
        wikidata.return_value = {"found": False, "status": "ambiguous"}
        tmdb.return_value = {"found": False, "status": "no exact movie"}
        anime.return_value = {
            "india_excluded": False,
            "anilist": {
                "found": True, "provider": "AniList", "title": "Example Anime",
                "country": "JP", "year": 2024, "provider_url": "https://anilist.co/anime/1",
            },
            "tenrai": {"found": False},
            "wikidata": {"found": False},
        }
        result = resolve_recap_metadata("Example Anime")
        self.assertTrue(result["found"])
        self.assertEqual(result["provider"], "AniList")
        self.assertEqual(result["countries"], ["Japan"])

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_indian_tmdb_result_is_rejected(self, wikidata, tmdb, anime):
        wikidata.return_value = {"found": False, "status": "ambiguous"}
        tmdb.return_value = {
            "found": True, "title": "Example", "countries": ["India"], "year": "2020",
        }
        result = resolve_recap_metadata("Example")
        self.assertFalse(result["found"])
        self.assertIn("အိန္ဒိယ", result["status"])
        anime.assert_not_called()

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_missing_country_fails_closed(self, wikidata, tmdb, anime):
        wikidata.return_value = {"found": False, "status": "ambiguous"}
        tmdb.return_value = {"found": True, "title": "Example", "countries": []}
        anime.return_value = {"india_excluded": False, "anilist": {"found": False}, "tenrai": {"found": False}}
        result = resolve_recap_metadata("Example")
        self.assertFalse(result["found"])
        self.assertIn("နိုင်ငံ", result["status"])
        anime.assert_not_called()

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_anime_requested_year_mismatch_is_rejected(self, wikidata, tmdb, anime):
        wikidata.return_value = {"found": False, "status": "ambiguous"}
        tmdb.return_value = {"found": False, "status": "no exact movie"}
        anime.return_value = {
            "india_excluded": False,
            "year_conflict": False,
            "anilist": {
                "found": True, "provider": "AniList", "title": "Example Anime",
                "country": "JP", "year": 2023,
            },
            "tenrai": {"found": False},
            "wikidata": {"found": False},
        }
        result = resolve_recap_metadata("Example Anime (2024)")
        self.assertFalse(result["found"])
        self.assertIn("2024", result["status"])

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_anime_cross_source_year_conflict_is_rejected(self, wikidata, tmdb, anime):
        wikidata.return_value = {"found": False, "status": "ambiguous"}
        tmdb.return_value = {"found": False, "status": "no exact movie"}
        anime.return_value = {
            "india_excluded": False,
            "year_conflict": True,
            "anilist": {
                "found": True, "provider": "AniList", "title": "Example Anime",
                "country": "JP", "year": 2024,
            },
            "tenrai": {"found": True, "provider": "Tenrai", "year": 2023},
            "wikidata": {"found": False},
        }
        result = resolve_recap_metadata("Example Anime")
        self.assertFalse(result["found"])
        self.assertIn("နှစ် မကိုက်ညီ", result["status"])

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_tmdb_and_wikidata_year_conflict_is_rejected(self, wikidata, tmdb, anime):
        wikidata.return_value = {
            "found": True, "title": "Example", "countries": ["United States"],
            "description": "film", "year": "1927", "source": "https://www.wikidata.org/wiki/Q1",
        }
        tmdb.return_value = {
            "found": True, "title": "Example", "countries": ["United States"],
            "year": "1926", "provider_url": "https://www.themoviedb.org/movie/1",
        }
        result = resolve_recap_metadata("Example")
        self.assertFalse(result["found"])
        self.assertIn("မကိုက်ညီ", result["status"])
        anime.assert_not_called()

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_tmdb_and_wikidata_country_conflict_is_rejected(self, wikidata, tmdb, anime):
        wikidata.return_value = {
            "found": True, "title": "Example", "countries": ["France"],
            "description": "film", "year": "2020", "source": "https://www.wikidata.org/wiki/Q1",
        }
        tmdb.return_value = {
            "found": True, "title": "Example", "countries": ["Japan"],
            "year": "2020", "provider_url": "https://www.themoviedb.org/movie/1",
        }
        result = resolve_recap_metadata("Example")
        self.assertFalse(result["found"])
        self.assertIn("နိုင်ငံ", result["status"])
        anime.assert_not_called()

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_tmdb_metadata_includes_source_provenance(self, wikidata, tmdb, anime):
        wikidata.return_value = {
            "found": True, "title": "Example", "countries": ["United States"],
            "description": "film", "year": "1926", "source": "https://www.wikidata.org/wiki/Q1",
        }
        tmdb.return_value = {
            "found": True, "title": "Example", "countries": ["United States"],
            "year": "1926", "provider_url": "https://www.themoviedb.org/movie/1",
            "overview": "A film.",
        }
        result = resolve_recap_metadata("Example")
        self.assertTrue(result["found"])
        self.assertEqual(result["metadata_confidence"], "cross_checked")
        self.assertEqual(len(result["source_urls"]), 2)
        anime.assert_not_called()

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_wikidata_anime_series_is_not_overwritten_by_same_named_tmdb_movie(self, wikidata, tmdb, anime):
        wikidata.return_value = {
            "found": True, "title": "Example", "countries": ["Japan"],
            "year": "2024", "description": "Japanese anime television series",
            "source": "https://www.wikidata.org/wiki/Q1",
        }
        result = resolve_recap_metadata("Example")
        self.assertTrue(result["found"])
        self.assertEqual(result["provider"], "Wikidata")
        tmdb.assert_not_called()
        anime.assert_not_called()

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_same_title_movie_and_anime_catalogue_collision_is_rejected(self, wikidata, tmdb, anime):
        wikidata.return_value = {"found": False, "status": "ambiguous"}
        tmdb.return_value = {
            "found": True, "title": "Example", "countries": ["United States"],
            "year": "2024", "provider_url": "https://www.themoviedb.org/movie/1",
        }
        anime.return_value = {
            "india_excluded": False,
            "anilist": {"found": True, "title": "Example", "year": 2024},
            "tenrai": {"found": False},
        }
        result = resolve_recap_metadata("Example")
        self.assertFalse(result["found"])
        self.assertIn("နှစ်/အမျိုးအစား", result["status"])


if __name__ == "__main__":
    unittest.main()
