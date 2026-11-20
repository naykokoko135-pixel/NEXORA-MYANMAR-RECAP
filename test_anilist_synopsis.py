import unittest
from unittest.mock import patch

from anilist_synopsis import fetch_anilist_synopsis


class AniListSynopsisTests(unittest.TestCase):
    def _item(self, **overrides):
        item = {
            "id": 101,
            "title": {"romaji": "Example Anime", "english": "Example Anime", "native": "例"},
            "synonyms": ["Example Series"],
            "description": "<p>A useful series overview. " + ("More context. " * 20) + "</p>",
            "siteUrl": "https://anilist.co/anime/101",
            "format": "TV",
            "episodes": 12,
            "seasonYear": 2024,
            "countryOfOrigin": "JP",
        }
        item.update(overrides)
        return item

    @patch("anilist_synopsis._graphql")
    def test_exact_match_returns_series_overview(self, mock_graphql):
        mock_graphql.return_value = {
            "data": {"Page": {"media": [self._item()]}}
        }
        result = fetch_anilist_synopsis("Example Anime")
        self.assertTrue(result["found"])
        self.assertEqual(result["scope"], "series_overview_not_episode_plot")
        self.assertIn("AniList", result["provider"])
        self.assertNotIn("<p>", result["synopsis"])

    @patch("anilist_synopsis._graphql")
    def test_movie_descriptor_alias_matches_unique_record(self, mock_graphql):
        item = self._item(id=178788, title={
            "romaji": "Kimetsu no Yaiba: Mugenjou-hen Movie 1 - Akaza Sairai",
            "english": "Demon Slayer: Kimetsu no Yaiba Infinity Castle",
            "native": "劇場版「鬼滅の刃」無限城編 第一章 猗窩座再来",
        }, synonyms=["Demon Slayer: Kimetsu no Yaiba Infinity Castle"], format="MOVIE", episodes=1)
        mock_graphql.side_effect = [
            {"data": {"Page": {"media": []}}},
        ] + [
            {"data": {"Page": {"media": [item]}}}
            for _ in range(8)
        ]
        result = fetch_anilist_synopsis("Demon Slayer: Kimetsu no Yaiba – The Movie: Infinity Castle")
        self.assertTrue(result["found"])
        self.assertEqual(result["media_id"], 178788)

    @patch("anilist_synopsis._graphql")
    def test_rejects_fuzzy_match(self, mock_graphql):
        mock_graphql.return_value = {
            "data": {"Page": {"media": [self._item() | {
                "title": {"romaji": "Example Anime 2", "english": "Example Anime 2"}
            }]} }
        }
        result = fetch_anilist_synopsis("Example Anime")
        self.assertFalse(result["found"])

    @patch("anilist_synopsis._graphql")
    def test_rejects_indian_origin(self, mock_graphql):
        mock_graphql.return_value = {
            "data": {"Page": {"media": [self._item(countryOfOrigin="IN")]}}
        }
        result = fetch_anilist_synopsis("Example Anime")
        self.assertFalse(result["found"])
        self.assertIn("အိန္ဒိယ", result["status"])

    def test_rejects_empty_title(self):
        self.assertFalse(fetch_anilist_synopsis("")["found"])


if __name__ == "__main__":
    unittest.main()
