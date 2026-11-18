import unittest
from animated_episode_pack import format_animated_episode_pack


class AnimatedEpisodePackTests(unittest.TestCase):
    def setUp(self):
        self.research = {
            "found": True, "title": "Sample Series", "country": "Japan",
            "provider_url": "https://www.tvmaze.com/shows/1/sample",
            "episodes": [{
                "season": 1, "number": 2, "title": "The Turning Point",
                "airdate": "2025-01-01", "rating": 9.2,
                "summary_excerpt": "A brief research lead.",
                "source": "https://www.tvmaze.com/episodes/2/sample",
            }],
        }

    def test_formats_episode_and_source_attribution(self):
        source = {
            "title": "File: Sample Series scene.webm",
            "license": "CC BY-SA 4.0", "artist": "Creator",
            "source_page": "https://commons.wikimedia.org/wiki/File:Sample",
            "usage_terms": "Attribution required",
        }
        result = format_animated_episode_pack(self.research, source)
        self.assertIn("9.2/10", result)
        self.assertIn("CC BY-SA 4.0", result)
        self.assertIn("Attribution required", result)
        self.assertIn("views/popularity မဟုတ်ပါ", result)

    def test_missing_clip_is_disclosed(self):
        result = format_animated_episode_pack(self.research)
        self.assertIn("ခိုင်မာစွာကိုက်ညီသော", result)
        self.assertIn("MP4 မဟုတ်ပါ", result)

    def test_unverified_research_rejected(self):
        with self.assertRaises(ValueError):
            format_animated_episode_pack({"found": False})

    def test_missing_country_rejected(self):
        research = dict(self.research)
        research["country"] = ""
        with self.assertRaises(ValueError):
            format_animated_episode_pack(research)


if __name__ == "__main__":
    unittest.main()
