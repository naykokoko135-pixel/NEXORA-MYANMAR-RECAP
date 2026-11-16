import unittest

from voiceover_builder import generate_voiceover_draft


class VoiceoverBuilderTests(unittest.TestCase):
    def test_formats_creator_notes_without_dropping_facts(self):
        result = generate_voiceover_draft(
            "Avatar",
            "- Jake arrives on Pandora.\n- He meets Neytiri."
        )
        self.assertIn("Jake arrives on Pandora.", result)
        self.assertIn("He meets Neytiri.", result)
        self.assertIn("Avatar", result)

    def test_does_not_claim_to_verify_or_invent_facts(self):
        result = generate_voiceover_draft("Avatar", "Creator-checked event.")
        self.assertIn("မဖြည့်စွက်ပါ", result)
        self.assertIn("Creator-checked event.", result)

    def test_requires_title_and_notes(self):
        with self.assertRaises(ValueError):
            generate_voiceover_draft("", "A fact.")
        with self.assertRaises(ValueError):
            generate_voiceover_draft("Avatar", " ")

    def test_rejects_oversized_notes(self):
        with self.assertRaises(ValueError):
            generate_voiceover_draft("Avatar", "x" * 9001)


if __name__ == "__main__":
    unittest.main()
