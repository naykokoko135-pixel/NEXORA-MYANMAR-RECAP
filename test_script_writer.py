import unittest

from script_writer import (classify_recap_title, generate_all_platform_plan, DEFAULT_DURATIONS, generate_recap_outline)


class TitleClassificationTests(unittest.TestCase):
    def test_pororo_is_south_korean_3d_childrens_animation(self):
        self.assertEqual(
            classify_recap_title("Pororo"),
            ("3D Animation / Children's Series", "South Korea"),
        )

    def test_chinese_title_is_donghua(self):
        self.assertEqual(classify_recap_title("Link Click"), ("Donghua", "China"))

    def test_unknown_title_is_not_guessed(self):
        category, region = classify_recap_title("An Unlisted Animation")
        self.assertIn("အတည်ပြုရန်", category)
        self.assertIn("အတည်ပြုရန်", region)

    def test_indian_titles_are_excluded_not_classified(self):
        for title in ("Motu Patlu", "Chhota Bheem"):
            category, region = classify_recap_title(title)
            self.assertEqual(category, "Project မှ ဖယ်ထုတ်ထားသည်")
            self.assertNotIn("India", region)

    def test_plan_shows_resolved_category(self):
        plan = generate_all_platform_plan("Pororo")
        self.assertIn("3D Animation / Children's Series", plan)
        self.assertIn("South Korea", plan)
        self.assertNotIn("Anime / 3D Animation / Cartoon / Donghua", plan)

    def test_youtube_plan_is_three_parts_of_15_to_20_minutes(self):
        plan = generate_all_platform_plan("Pororo")
        self.assertIn("၃ ပိုင်း | တစ်ပိုင်းလျှင် ၁၅–၂၀ မိနစ် | စုစုပေါင်း ၄၆–၆၀ မိနစ်", plan)
        self.assertIn("Part 1 (၁၅–၂၀ မိနစ်)", plan)
        self.assertIn("Part 2 (၁၅–၂၀ မိနစ်)", plan)
        self.assertIn("Part 3 (၁၅–၂၀ မိနစ်)", plan)

    def test_youtube_default_duration_and_outline_are_longform_three_parts(self):
        self.assertEqual(DEFAULT_DURATIONS["youtube"], "46-60")
        outline = generate_recap_outline("Pororo")
        self.assertIn("ရည်မှန်းချိန်: ၄၆–၆၀ မိနစ်", outline)
        self.assertIn("Extended Long-form", outline)
        self.assertEqual(DEFAULT_DURATIONS["facebook"], "46-60")
        self.assertEqual(DEFAULT_DURATIONS["tiktok"], "4-7")
        plan = generate_all_platform_plan("Pororo")
        self.assertIn("တစ်ပိုင်းလျှင် ၄–၇ မိနစ်", plan)
        facebook_outline = generate_recap_outline("Pororo", platform="facebook")
        self.assertIn("Detailed Cinematic Long-form Recap", facebook_outline)
        self.assertIn("အသေးစိတ်ဇာတ်လမ်းအခန်းများ", facebook_outline)


if __name__ == "__main__":
    unittest.main()
