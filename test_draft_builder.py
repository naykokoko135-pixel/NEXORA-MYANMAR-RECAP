import unittest

from draft_builder import generate_draft_worksheet


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


if __name__ == "__main__":
    unittest.main()
