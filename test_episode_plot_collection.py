import unittest
from unittest.mock import patch

from episode_plot_collection import collect_episode_plots, format_episode_plot_collection


class EpisodePlotCollectionTests(unittest.TestCase):
    @patch("multi_source_research.research_anime_sources")
    @patch("bangumi_episode_research.fetch_bangumi_episode_summaries")
    @patch("kitsu_anime_research.fetch_kitsu_episode_summaries")
    @patch("tvmaze_synopsis.fetch_tvmaze_episode_summaries")
    def test_collects_provider_results_separately(self, tvmaze, kitsu, bangumi, verify):
        tvmaze.return_value = {"found": True, "title": "Sample", "episodes": [
            {"season": 1, "number": 1, "title": "Pilot", "summary_excerpt": "TV plot", "source": "https://tvmaze.test/1"}
        ]}
        kitsu.return_value = {"found": True, "title": "Sample", "episodes": [
            {"season": 1, "number": 1, "title": "Episode One", "summary_excerpt": "Kitsu plot", "source": "https://kitsu.test/1"}
        ]}
        bangumi.return_value = {"found": True, "title": "Sample", "episodes": [
            {"number": 1, "title": "第一集", "source": "https://bgm.test/1"}
        ]}
        verify.return_value = {
            "anilist": {"found": True, "country": "JP"},
            "wikidata": {"found": True, "countries": ["Japan"]},
            "india_excluded": False,
        }
        result = collect_episode_plots("Sample")
        self.assertTrue(result["found"])
        self.assertEqual(set(result["sources"]), {"TVmaze", "Kitsu", "Bangumi"})
        self.assertEqual(result["sources"]["TVmaze"]["episodes"][0]["title"], "Pilot")
        self.assertEqual(result["sources"]["Kitsu"]["episodes"][0]["title"], "Episode One")
        self.assertEqual(result["sources"]["Bangumi"]["episodes"][0]["title"], "第一集")
        self.assertEqual(kitsu.call_args.args, ("Sample", 10))
        self.assertEqual(bangumi.call_args.args, ("Sample", 10))

    @patch("multi_source_research.research_anime_sources")
    @patch("bangumi_episode_research.fetch_bangumi_episode_summaries")
    @patch("kitsu_anime_research.fetch_kitsu_episode_summaries")
    @patch("tvmaze_synopsis.fetch_tvmaze_episode_summaries")
    def test_skips_anime_catalogues_without_independent_country(self, tvmaze, kitsu, bangumi, verify):
        tvmaze.return_value = {"found": False, "status": "No TVmaze"}
        verify.return_value = {
            "anilist": {"found": False},
            "wikidata": {"found": False, "countries": []},
            "india_excluded": False,
        }
        result = collect_episode_plots("Unknown Series")
        self.assertFalse(result["found"])
        kitsu.assert_not_called()
        bangumi.assert_not_called()
        self.assertIn("နိုင်ငံ", result["skipped"]["Kitsu"])

    @patch("multi_source_research.research_anime_sources")
    @patch("bangumi_episode_research.fetch_bangumi_episode_summaries")
    @patch("kitsu_anime_research.fetch_kitsu_episode_summaries")
    @patch("tvmaze_synopsis.fetch_tvmaze_episode_summaries")
    def test_rejects_indian_origin_before_anime_catalogues(self, tvmaze, kitsu, bangumi, verify):
        tvmaze.return_value = {"found": False}
        verify.return_value = {
            "anilist": {"found": True, "country": "IN"},
            "wikidata": {"found": True, "countries": ["India"]},
            "india_excluded": True,
        }
        result = collect_episode_plots("Sample")
        self.assertTrue(result["india_excluded"])
        kitsu.assert_not_called()
        bangumi.assert_not_called()

    def test_invalid_title(self):
        self.assertFalse(collect_episode_plots("")["found"])

    def test_formatter_discloses_missing_plot_and_no_license(self):
        report = {
            "title": "Sample",
            "country_verified": True,
            "country": "Japan",
            "sources": {
                "TVmaze": {"found": True, "title": "Sample", "episodes": [
                    {"season": 1, "number": 1, "title": "Pilot", "source": "https://tvmaze.test/1"}
                ]},
                "Kitsu": {"found": False, "status": "No Kitsu"},
                "Bangumi": {"found": False, "status": "No Bangumi"},
            },
            "skipped": {},
        }
        result = format_episode_plot_collection(report)
        self.assertIn("Episode ဇာတ်ကွက်စာသား မဖော်ပြထားပါ", result)
        self.assertIn("Footage/music အသုံးပြုခွင့်", result)
        self.assertIn("https://tvmaze.test/1", result)


if __name__ == "__main__":
    unittest.main()
