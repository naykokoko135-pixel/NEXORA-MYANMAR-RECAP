import unittest

from script_writer import generate_all_platform_plan, generate_episode_selection_guide


class EpisodeSelectionGuideTests(unittest.TestCase):
    def test_guide_separates_popularity_and_story_quality(self):
        guide = generate_episode_selection_guide()
        self.assertIn("Popularity", guide)
        self.assertIn("Story Quality", guide)
        self.assertIn("view count", guide.lower())
        self.assertIn("rating", guide.lower())

    def test_guide_warns_against_invented_metrics(self):
        guide = generate_episode_selection_guide()
        self.assertIn("အချက်အလက်မရရှိ", guide)
        self.assertIn("အတည်မပြုရသေး", guide)

    def test_all_platform_plan_includes_episode_selection(self):
        plan = generate_all_platform_plan("Pororo")
        self.assertIn("လူကြိုက်များ + အကောင်းဆုံး Episode ရွေးချယ်မှု", plan)
        self.assertIn("Season / Episode", plan)
        self.assertIn("YouTube", plan)
        self.assertIn("TikTok", plan)


if __name__ == "__main__":
    unittest.main()
