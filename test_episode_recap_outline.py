import unittest

from episode_recap_outline import format_episode_recap_outline


class EpisodeRecapOutlineTests(unittest.TestCase):
    def setUp(self):
        self.research = {
            "found": True,
            "title": "Sample Series",
            "country": "Japan",
            "provider_url": "https://www.tvmaze.com/shows/1/sample",
            "episodes": [{
                "season": 1,
                "number": 2,
                "title": "The Turning Point",
                "airdate": "2025-01-01",
                "rating": 9.2,
                "summary_excerpt": "A short episode research lead.",
                "source": "https://www.tvmaze.com/episodes/2/sample",
            }],
        }

    def test_creates_episode_specific_creator_worksheet(self):
        result = format_episode_recap_outline(self.research, "youtube", "20-30")
        self.assertIn("S1 E2", result)
        self.assertIn("Opening Hook", result)
        self.assertIn("Turning Point", result)
        self.assertIn("https://www.tvmaze.com/episodes/2/sample", result)
        self.assertIn("အလိုအလျောက် ဇာတ်လမ်းရေးသားခြင်း", result)

    def test_platform_duration_fallback(self):
        result = format_episode_recap_outline(self.research, "tiktok", "45-60")
        self.assertIn("TikTok | ရည်မှန်းကြာချိန်: 1-3 မိနစ်", result)

    def test_indian_title_rejected(self):
        research = dict(self.research, country="India")
        with self.assertRaises(ValueError):
            format_episode_recap_outline(research)

    def test_unverified_or_incomplete_research_rejected(self):
        with self.assertRaises(ValueError):
            format_episode_recap_outline({"found": False})
        research = dict(self.research, episodes=[])
        with self.assertRaises(ValueError):
            format_episode_recap_outline(research)

    def test_missing_rating_or_source_rejected(self):
        research = dict(self.research)
        research["episodes"] = [dict(self.research["episodes"][0], rating=None)]
        with self.assertRaises(ValueError):
            format_episode_recap_outline(research)
        research["episodes"] = [dict(self.research["episodes"][0], source="")]
        with self.assertRaises(ValueError):
            format_episode_recap_outline(research)


if __name__ == "__main__":
    unittest.main()
