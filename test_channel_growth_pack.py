import unittest

from channel_growth_pack import generate_growth_pack


class ChannelGrowthPackTests(unittest.TestCase):
    def test_youtube_pack_has_title_thumbnail_and_retention_checks(self):
        result = generate_growth_pack("Example Anime", "Anime", "youtube", "Verified plot summary.")
        self.assertIn("Example Anime", result)
        self.assertIn("Thumbnail", result)
        self.assertIn("Audience Retention", result)
        self.assertIn("Verified plot summary.", result)

    def test_category_is_required_and_restricted_to_project_categories(self):
        with self.assertRaises(ValueError):
            generate_growth_pack("Example", "Indian Movies")
        with self.assertRaises(ValueError):
            generate_growth_pack("Example", "Anime", "youtube")

    def test_platform_specific_pacing(self):
        short = generate_growth_pack("Example", "Donghua", "tiktok")
        self.assertIn("0–2 sec", short)
        facebook = generate_growth_pack("Example", "Cartoon", "facebook")
        self.assertIn("3–5 sec", facebook)

    def test_rejects_oversized_inputs(self):
        with self.assertRaises(ValueError):
            generate_growth_pack("x" * 141, "Anime")
        with self.assertRaises(ValueError):
            generate_growth_pack("Example", "Anime", summary="x" * 1001)

    def test_discloses_missing_summary_instead_of_inventing_plot(self):
        result = generate_growth_pack("Example Movie", "International Movies")
        self.assertIn("[အတည်ပြုပြီးသော ဇာတ်လမ်းအကျဉ်း", result)
        self.assertIn("မခန့်မှန်း", result)


if __name__ == "__main__":
    unittest.main()
