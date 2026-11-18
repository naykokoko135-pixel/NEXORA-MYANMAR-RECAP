import unittest
from unittest.mock import patch

from trend_sources import fetch_anime_trends, format_anime_trends


class AnimeTrendTests(unittest.TestCase):
    @patch("trend_sources._fetch_json")
    def test_fetches_public_non_adult_anime_trends(self, fetch):
        fetch.return_value = {"data": {"Page": {"media": [{
            "title": {"english": "Example Show", "romaji": "Example"},
            "siteUrl": "https://anilist.co/anime/1",
            "trending": 1234, "popularity": 5678, "averageScore": 84,
            "episodes": 12, "format": "TV",
        }]}}}
        result = fetch_anime_trends()
        self.assertTrue(result["ok"])
        self.assertEqual(result["items"][0]["title"], "Example Show")
        self.assertEqual(result["items"][0]["trending"], 1234)
        self.assertIn("isAdult: false", fetch.call_args.kwargs["payload"]["query"])

    @patch("trend_sources._fetch_json")
    def test_network_failure_is_reported_without_fake_ranking(self, fetch):
        fetch.side_effect = OSError("offline")
        result = fetch_anime_trends()
        self.assertFalse(result["ok"])
        report = format_anime_trends(result)
        self.assertIn("Trend data မရရှိပါ", report)
        self.assertNotIn("1. ", report)

    def test_report_disclaims_episode_view_counts(self):
        result = {"ok": True, "source": "AniList", "checked_at": "2026-11-18T00:00:00+00:00",
                  "items": [{"title": "Example Show", "url": "https://anilist.co/anime/1",
                             "trending": 10, "popularity": 20, "score": 90}]}
        report = format_anime_trends(result)
        self.assertIn("Episode တစ်ခုချင်းစီ", report)
        self.assertIn("Example Show", report)


if __name__ == "__main__":
    unittest.main()
