import unittest

from episode_plot_verification import (
    verify_episode_plot_sources,
    format_episode_plot_verification,
)


class EpisodePlotVerificationTests(unittest.TestCase):
    def setUp(self):
        self.collection = {
            "title": "Sample Series",
            "sources": {
                "TVmaze": {"found": True, "episodes": [
                    {"season": 1, "number": 1, "title": "The Beginning",
                     "summary_excerpt": "A hero discovers a hidden world.",
                     "source": "https://tvmaze.test/1"},
                    {"season": 1, "number": 2, "title": "The Journey",
                     "summary_excerpt": "The hero leaves home.",
                     "source": "https://tvmaze.test/2"},
                ]},
                "Kitsu": {"found": True, "episodes": [
                    {"season": 1, "number": 1, "title": "The Beginning",
                     "summary_excerpt": "A hero discovers a hidden world.",
                     "source": "https://kitsu.test/1"},
                    {"season": 1, "number": 2, "title": "A Different Name",
                     "summary_excerpt": "The hero leaves home.",
                     "source": "https://kitsu.test/2"},
                ]},
                "Bangumi": {"found": True, "episodes": [
                    {"season": None, "number": 1, "title": "The Beginning",
                     "summary_excerpt": "A hero discovers a hidden world.",
                     "source": "https://bgm.test/1"},
                ]},
            },
        }

    def test_exact_title_and_number_become_candidate_match(self):
        result = verify_episode_plot_sources(self.collection)
        self.assertTrue(result["found"])
        self.assertTrue(any(
            set(item["providers"]) == {"TVmaze", "Kitsu"}
            for item in result["matches"]
        ))
        self.assertTrue(any(
            set(item["providers"]) == {"TVmaze", "Bangumi"}
            for item in result["matches"]
        ))

    def test_same_episode_number_with_different_title_is_discrepancy(self):
        result = verify_episode_plot_sources(self.collection)
        self.assertTrue(any(
            item["number"] == 2 and set(item["providers"]) == {"TVmaze", "Kitsu"}
            for item in result["slot_conflicts"]
        ))

    def test_text_similarity_is_not_present_without_two_descriptions(self):
        result = verify_episode_plot_sources({
            "title": "Sample",
            "sources": {
                "TVmaze": {"found": True, "episodes": [
                    {"number": 1, "title": "Pilot", "source": "a"}
                ]},
                "Bangumi": {"found": True, "episodes": [
                    {"number": 1, "title": "Pilot", "source": "b"}
                ]},
            },
        })
        self.assertIsNone(result["matches"][0]["text_similarity"])

    def test_requires_two_sources(self):
        result = verify_episode_plot_sources({
            "title": "Sample",
            "sources": {"TVmaze": {"found": True, "episodes": [{"number": 1, "title": "Pilot"}]}},
        })
        self.assertFalse(result["found"])
        self.assertIn("၂ ခု", result["status"])

    def test_formatter_disclaims_fact_verification(self):
        report = verify_episode_plot_sources(self.collection)
        text = format_episode_plot_verification(report)
        self.assertIn("fact-check score မဟုတ်ပါ", text)
        self.assertIn("ဇာတ်ကွက်အမှန်ဖြစ်ကြောင်း သက်သေမဟုတ်ပါ", text)
        self.assertIn("https://tvmaze.test/1", text)


if __name__ == "__main__":
    unittest.main()
