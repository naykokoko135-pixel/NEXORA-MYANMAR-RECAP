import unittest

from creator_voice_recap import split_clone_text, build_duration_scaled_srt, combine_estimated_srt_parts


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
        last_block = srt.strip().split("\n\n")[-1]
        self.assertIn("--> 00:00:12,500", last_block)
        self.assertIn("မင်္ဂလာပါ", srt)

    def test_combined_srt_offsets_each_part_and_reindexes(self):
        first = "1\\n00:00:00,000 --> 00:00:05,000\\nPart one"
        second = "1\\n00:00:00,000 --> 00:00:07,000\\nPart two"
        combined = combine_estimated_srt_parts([(first, 5), (second, 7)])
        self.assertIn("1\\n00:00:00,000 --> 00:00:05,000", combined)
        self.assertIn("2\\n00:00:05,000 --> 00:00:12,000", combined)

    def test_srt_rejects_invalid_duration(self):
        with self.assertRaises(ValueError):
            build_duration_scaled_srt("စာသား", 0)


if __name__ == "__main__":
    unittest.main()
