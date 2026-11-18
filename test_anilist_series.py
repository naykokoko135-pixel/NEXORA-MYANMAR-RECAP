import json
import unittest
from io import BytesIO
from urllib.error import URLError
from unittest.mock import patch

from anilist_series import (
    ANIME_SERIES_TITLES, fetch_anilist_episode_guide,
    format_anilist_episode_guide,
)


class Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def media(media_id=1, english="Frieren: Beyond Journey's End", romaji="Sousou no Frieren",
          episodes=28, media_format="TV", adult=False):
    return {
        "id": media_id,
        "title": {"english": english, "romaji": romaji, "native": "葬送のフリーレン"},
        "episodes": episodes,
        "format": media_format,
        "status": "FINISHED",
        "seasonYear": 2023,
        "siteUrl": "https://anilist.co/anime/52991",
        "isAdult": adult,
    }


class AniListSeriesTests(unittest.TestCase):
    @patch("anilist_series.urlopen")
    def test_exact_anime_title_returns_episode_count(self, mock_urlopen):
        mock_urlopen.return_value = Response(json.dumps({
            "data": {"Page": {"media": [media()]}}
        }).encode())
        result = fetch_anilist_episode_guide("Frieren: Beyond Journey's End")
        self.assertTrue(result["found"])
        self.assertEqual(result["episode_count"], 28)
        self.assertEqual(result["format"], "TV")
        formatted = format_anilist_episode_guide(result)
        self.assertIn("စုစုပေါင်း Episode အရေအတွက်: 28", formatted)
        self.assertIn("anilist.co/anime/52991", formatted)
        self.assertIn("Official Broadcaster", formatted)

    @patch("anilist_series.urlopen")
    def test_unrelated_fuzzy_result_is_rejected(self, mock_urlopen):
        mock_urlopen.return_value = Response(json.dumps({
            "data": {"Page": {"media": [media(english="Frieren: The Movie")]}}
        }).encode())
        result = fetch_anilist_episode_guide("Frieren: Beyond Journey's End")
        self.assertFalse(result["found"])
        self.assertIn("အတိအကျ", result["status"])

    @patch("anilist_series.urlopen")
    def test_duplicate_exact_versions_are_not_selected(self, mock_urlopen):
        mock_urlopen.return_value = Response(json.dumps({
            "data": {"Page": {"media": [media(media_id=1), media(media_id=2)]}}
        }).encode())
        result = fetch_anilist_episode_guide("Frieren: Beyond Journey's End")
        self.assertFalse(result["found"])
        self.assertIn("version", result["status"])

    @patch("anilist_series.urlopen")
    def test_adult_entries_are_ignored(self, mock_urlopen):
        mock_urlopen.return_value = Response(json.dumps({
            "data": {"Page": {"media": [media(adult=True)]}}
        }).encode())
        result = fetch_anilist_episode_guide("Frieren: Beyond Journey's End")
        self.assertFalse(result["found"])

    @patch("anilist_series.urlopen")
    def test_movies_are_not_reported_as_series(self, mock_urlopen):
        mock_urlopen.return_value = Response(json.dumps({
            "data": {"Page": {"media": [media(media_format="MOVIE")]}}
        }).encode())
        result = fetch_anilist_episode_guide("Frieren: Beyond Journey's End")
        self.assertFalse(result["found"])
        self.assertIn("TV/Web Series", result["status"])

    @patch("anilist_series.urlopen")
    def test_missing_episode_count_is_not_invented(self, mock_urlopen):
        mock_urlopen.return_value = Response(json.dumps({
            "data": {"Page": {"media": [media(episodes=None)]}}
        }).encode())
        result = fetch_anilist_episode_guide("Frieren: Beyond Journey's End")
        self.assertFalse(result["found"])
        self.assertIn("မရရှိသေးပါ", result["status"])

    @patch("anilist_series.urlopen")
    def test_api_failure_is_reported_safely(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("offline")
        result = fetch_anilist_episode_guide("Frieren: Beyond Journey's End")
        self.assertFalse(result["found"])
        self.assertIn("မခန့်မှန်းထားပါ", result["status"])

    def test_non_allowlisted_title_does_not_make_api_request(self):
        with patch("anilist_series.urlopen") as mock_urlopen:
            result = fetch_anilist_episode_guide("The King's Avatar")
        self.assertFalse(result["found"])
        mock_urlopen.assert_not_called()

    def test_allow_list_contains_only_curated_anime_series(self):
        self.assertIn("Frieren: Beyond Journey's End", ANIME_SERIES_TITLES)
        self.assertNotIn("The King's Avatar", ANIME_SERIES_TITLES)
        self.assertNotIn("Train to Busan", ANIME_SERIES_TITLES)


if __name__ == "__main__":
    unittest.main()
