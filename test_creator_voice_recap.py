import unittest

from creator_voice_recap import split_clone_text, build_duration_scaled_srt


class CreatorVoiceRecapTests(unittest.TestCase):
    def test_split_respects_clone_limit_and_preserves_text(self):
        text = ("မင်္ဂလာပါ။ " * 900).strip()
        chunks = split_clone_text(text, max_chars=500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 500 for chunk in chunks))
        self.assertEqual("".join(chunks).replace(" ", ""), text.replace(" ", ""))

    def test_srt_spans_measured_duration(self):
        srt = build_duration_scaled_srt("မင်္ဂလာပါ။ ဒီနေ့ ဇာတ်လမ်းကို ပြောပြပါမယ်။", 12.5)
        self.assertIn("00:00:00,000 --> ", srt)
        self.assertTrue(srt.rstrip().endswith("00:00:12,500"))
        self.assertIn("မင်္ဂလာပါ", srt)

    def test_srt_rejects_invalid_duration(self):
        with self.assertRaises(ValueError):
            build_duration_scaled_srt("စာသား", 0)


if __name__ == "__main__":
    unittest.main()
