import unittest

from voiceover_builder import generate_voiceover_draft, generate_voiceover_part_files


class VoiceoverBuilderTests(unittest.TestCase):
    def setUp(self):
        self.notes = "\n".join([
            "Jake arrives on Pandora.",
            "Jake meets Neytiri.",
            "Grace leads the Avatar program.",
            "The mining operation threatens the Na'vi.",
            "Jake learns the Na'vi way of life.",
            "The conflict escalates after the Hometree attack.",
            "Jake gathers the clans.",
            "The final battle takes place.",
            "Jake's consciousness is transferred permanently.",
        ])

    def test_formats_notes_into_three_parts_without_dropping_facts(self):
        result = generate_voiceover_draft("Avatar", self.notes)
        self.assertIn("PART 1", result)
        self.assertIn("PART 2", result)
        self.assertIn("PART 3", result)
        for fact in self.notes.splitlines():
            self.assertIn(fact, result)
        self.assertIn("Avatar", result)

    def test_creates_three_separate_files_and_preserves_every_fact(self):
        files = generate_voiceover_part_files("Avatar", self.notes)
        self.assertEqual(len(files), 3)
        combined = "\\n".join(files)
        for fact in self.notes.splitlines():
            self.assertIn(fact, combined)
        for index, content in enumerate(files, start=1):
            self.assertIn(f"PART {index}/3", content)
        self.assertIn("Fact-check မဟုတ်ပါ", combined)

    def test_does_not_claim_to_verify_or_invent_facts(self):
        result = generate_voiceover_draft("Avatar", self.notes)
        self.assertIn("Fact-check မဟုတ်ပါ", result)
        self.assertIn("အချက်အလက်အသစ် မဖန်တီးပါ", result)

    def test_rejects_too_few_notes_and_placeholders(self):
        with self.assertRaisesRegex(ValueError, "အနည်းဆုံး ၆ ကြောင်း"):
            generate_voiceover_draft(
                "Avatar",
                "Jake arrives.\nJake meets Neytiri.\n[ဇာတ်ကားနဲ့ ပြန်စစ်ထားတဲ့ ဖြစ်ရပ်တွေ ထည့်ပါ]",
            )

    def test_requires_title_and_notes(self):
        with self.assertRaises(ValueError):
            generate_voiceover_draft("", self.notes)
        with self.assertRaises(ValueError):
            generate_voiceover_draft("Avatar", " ")

    def test_rejects_oversized_notes(self):
        with self.assertRaises(ValueError):
            generate_voiceover_draft("Avatar", "x" * 12001)


if __name__ == "__main__":
    unittest.main()
