import unittest

from production_qa import (
    analyze_production_package,
    format_production_qa_report,
    parse_production_package,
    validate_srt,
)


def _srt(duration_seconds=2760):
    minutes, seconds = divmod(duration_seconds, 60)
    end = f"00:{minutes:02d}:{seconds:02d},000"
    return f"1\n00:00:00,000 --> {end}\nSubtitle sample"


def _package(platform="youtube", part_text=None, duration=2760):
    if part_text is None:
        part_text = "က" * (180 * 12)
    markers = [f"[PART {index}]\n{part_text}" for index in range(1, 4)] if platform in {"youtube", "facebook"} else [f"[PART 1]\n{part_text}"]
    return "\n\n".join(markers) + "\n\n[SRT]\n" + _srt(duration)


class ProductionQATests(unittest.TestCase):
    def test_parse_three_parts_and_srt(self):
        parts, srt = parse_production_package(_package())
        self.assertEqual(sorted(parts), [1, 2, 3])
        self.assertIn("Subtitle sample", srt)

    def test_youtube_valid_structure_and_duration(self):
        # 15 minutes per part at 12 chars/second; total estimated 45 minutes,
        # so total-duration rule correctly requires at least 46 minutes.
        report = analyze_production_package("youtube", _package())
        self.assertEqual(report["status"], "REVIEW")
        self.assertTrue(any("စုစုပေါင်း Script" in item for item in report["issues"]))

    def test_youtube_total_and_srt_duration_pass(self):
        part = "က" * (16 * 60 * 12)
        package = _package(part_text=part, duration=48 * 60)
        report = analyze_production_package("youtube", package)
        self.assertEqual(report["status"], "READY FOR HUMAN REVIEW")
        self.assertEqual(report["srt"]["entries"], 1)

    def test_tiktok_requires_one_part_and_four_to_seven_minutes(self):
        part = "က" * (5 * 60 * 12)
        package = "[PART 1]\n" + part + "\n\n[SRT]\n" + _srt(300)
        report = analyze_production_package("tiktok", package)
        self.assertEqual(report["status"], "READY FOR HUMAN REVIEW")

    def test_missing_parts_and_srt_flagged(self):
        report = analyze_production_package("facebook", "[PART 1]\nစာသား")
        self.assertEqual(report["status"], "REVIEW")
        self.assertTrue(any("အပိုင်း 3 ပိုင်းတိတိ" in item for item in report["issues"]))
        self.assertTrue(any("[SRT]" in item for item in report["issues"]))

    def test_srt_overlap_and_caption_length(self):
        srt = (
            "1\n00:00:00,000 --> 00:00:03,000\n" + "က" * 43 + "\n\n"
            "2\n00:00:02,000 --> 00:00:04,000\nဒုတိယစာတန်း"
        )
        result = validate_srt(srt)
        self.assertFalse(result["valid"])
        self.assertTrue(any("ထပ်နေသည်" in item for item in result["issues"]))
        self.assertTrue(any("42 characters" in item for item in result["issues"]))

    def test_srt_sequence_and_timestamp_errors(self):
        result = validate_srt("2\n00:00:03,000 --> 00:00:02,000\nစာတန်း")
        self.assertFalse(result["valid"])
        self.assertTrue(any("sequence" in item for item in result["issues"]))
        self.assertTrue(any("အဆုံးအချိန်" in item for item in result["issues"]))

    def test_invalid_platform_rejected(self):
        report = analyze_production_package("instagram", "[PART 1]\ntext")
        self.assertEqual(report["status"], "NOT READY")

    def test_formatter_disclaims_actual_audio_verification(self):
        report = analyze_production_package("tiktok", "[PART 1]\n" + "က" * 3600 + "\n\n[SRT]\n" + _srt(300))
        output = format_production_qa_report(report)
        self.assertIn("တကယ့်အသံဖိုင်ကြာချိန် မဟုတ်ပါ", output)


if __name__ == "__main__":
    unittest.main()
