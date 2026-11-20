import unittest

from srt_builder import build_srt


class EnglishSrtBuilderTests(unittest.TestCase):
    def test_builds_numbered_srt_from_timestamped_english_lines(self):
        result = build_srt(
            "00:00:00,000 --> 00:00:05,000 | Welcome to the story.\n"
            "00:00:05,000 --> 00:00:10,250 | The journey begins."
        )
        self.assertEqual(
            result,
            "1\n00:00:00,000 --> 00:00:05,000\nWelcome to the story.\n\n"
            "2\n00:00:05,000 --> 00:00:10,250\nThe journey begins.\n",
        )

    def test_rejects_invalid_line_format(self):
        with self.assertRaises(ValueError):
            build_srt("Welcome to the story.")

    def test_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            build_srt("  \n ")

    def test_rejects_zero_or_negative_duration(self):
        with self.assertRaises(ValueError):
            build_srt("00:00:05,000 --> 00:00:05,000 | Same time")

    def test_rejects_overlapping_or_out_of_order_captions(self):
        source = (
            "00:00:00,000 --> 00:00:05,000 | First\n"
            "00:00:04,500 --> 00:00:07,000 | Overlap"
        )
        with self.assertRaises(ValueError):
            build_srt(source)

    def test_rejects_minutes_or_seconds_above_59(self):
        invalid_timestamps = (
            "00:60:00,000 --> 01:00:00,000 | Invalid minute",
            "00:00:60,000 --> 00:01:00,000 | Invalid second",
        )
        for line in invalid_timestamps:
            with self.subTest(line=line):
                with self.assertRaises(ValueError):
                    build_srt(line)


if __name__ == "__main__":
    unittest.main()
