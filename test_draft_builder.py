import unittest

from draft_builder import generate_draft_worksheet, generate_three_part_draft_worksheets


class DraftBuilderTests(unittest.TestCase):
    def test_keeps_creator_notes_and_builds_youtube_chapters(self):
        result = generate_draft_worksheet(
            "Avatar",
            "Jake arrives on Pandora.\nHe meets the Na'vi.",
            platform="youtube",
            duration="15-20",
        )
        self.assertIn("Jake arrives on Pandora.", result)
        self.assertIn("အခန်း ၅", result)
        self.assertIn("သီးခြားအတည်မပြုထား", result)

    def test_requires_notes(self):
        with self.assertRaises(ValueError):
            generate_draft_worksheet("Avatar", " ")

    def test_uses_short_form_chapters_for_tiktok(self):
        result = generate_draft_worksheet(
            "Avatar", "Creator-checked note.", platform="tiktok", duration="3-5"
        )
        self.assertIn("အပိုင်း ၃", result)
        self.assertNotIn("အခန်း ၅", result)

    def test_three_part_worksheets_are_distinct(self):
        result = generate_three_part_draft_worksheets(
            "Avatar", "Checked note: the story is set on Pandora.", duration="15-20"
        )
        self.assertIn("PART 1", result)
        self.assertIn("PART 2", result)
        self.assertIn("PART 3", result)
        self.assertIn("ဇာတ်လမ်းစတင်ရာ", result)
        self.assertIn("အဓိကပြဿနာ", result)
        self.assertIn("Climax", result)
        self.assertIn("Checked note: the story is set on Pandora.", result)
        self.assertIn("စုစုပေါင်းရည်မှန်းချိန်: ၁၅–၂၀ မိနစ်", result)

    def test_three_part_requires_notes(self):
        with self.assertRaises(ValueError):
            generate_three_part_draft_worksheets("Avatar", "")

    def test_three_part_rejects_oversized_notes(self):
        with self.assertRaises(ValueError):
            generate_three_part_draft_worksheets("Avatar", "x" * 10001)

    def test_rejects_placeholder_instead_of_real_research_notes(self):
        with self.assertRaisesRegex(ValueError, "Placeholder"):
            generate_three_part_draft_worksheets(
                "Avatar", "ဇာတ်ကားနဲ့တိုက်စစ်ထားတဲ့ Research Notes တွေ ဒီမှာထည့်ပါ။"
            )

    def test_default_youtube_worksheet_is_three_parts_of_15_to_20_minutes(self):
        result = generate_three_part_draft_worksheets(
            "Avatar", "Verified creator note."
        )
        self.assertIn("စုစုပေါင်းရည်မှန်းချိန်: ၄၆–၆၀ မိနစ်", result)
        self.assertIn("အပိုင်းတစ်ခုလျှင် ၁၅–၂၀ မိနစ်ခန့်", result)
        self.assertEqual(result.count("ရည်မှန်းချိန်: အပိုင်းတစ်ခုလျှင်"), 3)

    def test_default_youtube_draft_worksheet_uses_exactly_three_parts(self):
        result = generate_draft_worksheet("Avatar", "Verified creator note.")
        self.assertEqual(result.count("PART "), 3)
        self.assertIn("ရည်မှန်းချိန်: ၄၆–၆၀ မိနစ်", result)

    def test_facebook_extended_duration_uses_three_parts(self):
        result = generate_draft_worksheet("Avatar", "Verified creator note.", platform="facebook", duration="46-60")
        self.assertEqual(result.count("PART "), 3)
        self.assertIn("၁၅–၂၀ မိနစ်", result)

    def test_tiktok_four_to_seven_minute_preset_is_supported(self):
        result = generate_draft_worksheet("Avatar", "Verified creator note.", platform="tiktok", duration="4-7")
        self.assertIn("ရည်မှန်းချိန်: ၄–၇ မိနစ်", result)


if __name__ == "__main__":
    unittest.main()
