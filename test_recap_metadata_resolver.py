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
        anime.assert_called_once_with("Example")

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
            "enwiki_title": "", "mywiki_title": "",
        }
        anime.return_value = {
            "india_excluded": False, "year_conflict": False,
            "anilist": {
                "found": True, "provider": "AniList", "title": "Example",
                "country": "JP", "year": 2024,
                "synopsis": "A sufficiently detailed series synopsis for a safe short preview, with enough verified descriptive detail to support a brief introduction without inventing any episode events.",
                "provider_url": "https://anilist.co/anime/1",
            },
            "tenrai": {"found": False},
        }
        result = resolve_recap_metadata("Example")
        self.assertTrue(result["found"])
        self.assertEqual(result["provider"], "Wikidata")
        self.assertEqual(result["countries"], ["Japan"])
        self.assertEqual(result["anime_synopsis"], "A sufficiently detailed series synopsis for a safe short preview, with enough verified descriptive detail to support a brief introduction without inventing any episode events.")
        self.assertEqual(result["anime_synopsis_source"], "https://anilist.co/anime/1")
        tmdb.assert_not_called()
        anime.assert_called_once_with("Example")

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_localized_wikidata_description_uses_english_film_description(self, wikidata, tmdb, anime):
        wikidata.return_value = {
            "found": True, "title": "Example", "countries": ["United States"],
            "year": "1926", "description": "ရုပ်ရှင်",
            "description_en": "silent comedy film",
            "source": "https://www.wikidata.org/wiki/Q1",
        }
        tmdb.return_value = {
            "found": True, "title": "Example", "countries": ["United States"],
            "year": "1926", "provider_url": "https://www.themoviedb.org/movie/1",
        }
        result = resolve_recap_metadata("Example")
        self.assertTrue(result["found"])
        self.assertEqual(result["provider"], "TMDB + Wikidata")
        tmdb.assert_called_once_with("Example")
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



    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_exact_query_synopsis_survives_other_catalogue_year_conflict_and_title_alias(self, wikidata, tmdb, anime):
        wikidata.return_value = {
            "found": True, "title": "Haikyu!!", "countries": ["Japan"],
            "year": "2014", "description": "Japanese anime television series",
            "source": "https://www.wikidata.org/wiki/Q1",
            "enwiki_title": "", "mywiki_title": "",
        }
        anime.return_value = {
            "title": "Haikyu!!",
            "india_excluded": False,
            "year_conflict": True,
            "anilist": {
                "found": True, "provider": "AniList", "title": "Haikyuu!!",
                "country": "JP", "year": 2014,
                "synopsis": "A sufficiently detailed series synopsis for a safe short preview, with enough verified descriptive detail to support a brief introduction without inventing any episode events.",
                "provider_url": "https://anilist.co/anime/1",
            },
            "tenrai": {"found": True, "provider": "Tenrai", "title": "Haikyu!!", "year": 2013},
        }
        result = resolve_recap_metadata("Haikyu!!")
        self.assertTrue(result["found"])
        self.assertEqual(result["anime_synopsis_provider"], "AniList")
        self.assertEqual(result["anime_synopsis_source"], "https://anilist.co/anime/1")
        tmdb.assert_not_called()
        anime.assert_called_once_with("Haikyu!!")

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_exact_query_synopsis_is_kept_when_wikidata_year_is_missing(self, wikidata, tmdb, anime):
        wikidata.return_value = {
            "found": True, "title": "Naruto", "countries": ["Japan"],
            "year": None, "description": "Japanese anime television series",
            "source": "https://www.wikidata.org/wiki/Q1",
            "enwiki_title": "", "mywiki_title": "",
        }
        anime.return_value = {
            "title": "Naruto", "india_excluded": False, "year_conflict": False,
            "anilist": {
                "found": True, "provider": "AniList", "title": "Naruto",
                "country": "JP", "year": 2002,
                "synopsis": "A sufficiently detailed Naruto series synopsis for a safe short preview, with enough verified descriptive detail to support an introduction without inventing episode events.",
                "provider_url": "https://anilist.co/anime/20",
            },
            "tenrai": {"found": False},
        }
        result = resolve_recap_metadata("Naruto")
        self.assertTrue(result["found"])
        self.assertEqual(result["anime_synopsis_provider"], "AniList")
        self.assertEqual(result["anime_synopsis_source"], "https://anilist.co/anime/20")
        self.assertEqual(result["anime_synopsis"], anime.return_value["anilist"]["synopsis"])
        tmdb.assert_not_called()
        anime.assert_called_once_with("Naruto")

    @patch("recap_metadata_resolver.research_anime_sources")
    @patch("recap_metadata_resolver.fetch_tmdb_movie")
    @patch("recap_metadata_resolver.fetch_wikidata_metadata")
    def test_exact_tenrai_match_uses_tenrai_country_and_synopsis_source(self, wikidata, tmdb, anime):
        wikidata.return_value = {"found": False, "status": "no exact Wikidata match"}
        tmdb.return_value = {"found": False, "status": "no exact movie"}
        anime.return_value = {
            "india_excluded": False, "year_conflict": False,
            "anilist": {"found": False},
            "tenrai": {
                "found": True, "provider": "Tenrai", "title": "Example Series",
                "country": "JP", "year": 2021, "format": "TV",
                "synopsis": "A sufficiently detailed series synopsis for a safe short preview, with enough verified descriptive detail to support an introduction without inventing episode events.",
                "provider_url": "https://myanimelist.net/anime/123",
            },
            "wikidata": {"found": False},
        }
        result = resolve_recap_metadata("Example Series")
        self.assertTrue(result["found"])
        self.assertEqual(result["countries"], ["Japan"])
        self.assertEqual(result["anime_synopsis_source"], "https://myanimelist.net/anime/123")
        self.assertEqual(result["anime_synopsis_provider"], "Tenrai")
        tmdb.assert_called_once_with("Example Series")

if __name__ == "__main__":
    unittest.main()
