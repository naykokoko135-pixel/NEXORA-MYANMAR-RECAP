import unittest
from unittest.mock import patch, Mock

from audio_duration_qa import (
    evaluate_audio_duration,
    evaluate_audio_parts,\n    format_audio_parts_qa_report,
    format_audio_qa_report,
    parse_ffmpeg_audio_metadata,
)


class AudioDurationQATests(unittest.TestCase):
    def test_parse_audio_duration_metadata(self):
        output = (
            "Input #0, mp3, from 'sample.mp3':\\n"
            "  Duration: 00:48:12.34, start: 0.025057, bitrate: 128 kb/s\\n"
            "  Stream #0:0: Audio: mp3, 44100 Hz, stereo, fltp"
        )
        result = parse_ffmpeg_audio_metadata(output)
        self.assertEqual(result["duration_seconds"], 2892.34)
        self.assertIn("mp3", result["audio_stream"])

    def test_missing_duration_rejected(self):
        with self.assertRaises(ValueError):
            parse_ffmpeg_audio_metadata("Stream #0:0: Audio: mp3")

    def test_missing_audio_stream_rejected(self):
        with self.assertRaises(ValueError):
            parse_ffmpeg_audio_metadata("Duration: 00:05:00.00")

    def test_youtube_facebook_duration_limits(self):
        self.assertEqual(evaluate_audio_duration("youtube", 46 * 60)["status"], "DURATION PASS")
        self.assertEqual(evaluate_audio_duration("facebook", 60 * 60)["status"], "DURATION PASS")
        self.assertEqual(evaluate_audio_duration("youtube", 45 * 60)["status"], "TOO SHORT")
        self.assertEqual(evaluate_audio_duration("facebook", 61 * 60)["status"], "TOO LONG")

    def test_tiktok_duration_limits(self):
        self.assertEqual(evaluate_audio_duration("tiktok", 4 * 60)["status"], "DURATION PASS")
        self.assertEqual(evaluate_audio_duration("tt", 7 * 60)["status"], "DURATION PASS")
        self.assertEqual(evaluate_audio_duration("tiktok", 239)["status"], "TOO SHORT")

    def test_measured_three_part_audio_passes_for_youtube_and_facebook(self):
        durations = [15 * 60, 16 * 60, 15 * 60]
        for platform in ("youtube", "facebook"):
            with self.subTest(platform=platform):
                result = evaluate_audio_parts(platform, durations)
                self.assertEqual(result["status"], "DURATION PASS")
                self.assertEqual(result["total_duration_seconds"], 46 * 60)

    def test_measured_part_count_must_be_exact(self):
        self.assertEqual(evaluate_audio_parts("youtube", [900])["status"], "NOT READY")
        self.assertEqual(evaluate_audio_parts("tiktok", [300, 300])["status"], "NOT READY")

    def test_each_longform_part_and_total_are_checked(self):
        result = evaluate_audio_parts("youtube", [14 * 60, 15 * 60, 15 * 60])
        self.assertEqual(result["status"], "DURATION FAIL")
        self.assertTrue(any("Part 1" in issue for issue in result["issues"]))
        self.assertTrue(any("စုစုပေါင်း" in issue for issue in result["issues"]))

    def test_measured_tiktok_single_part_passes(self):
        self.assertEqual(evaluate_audio_parts("tiktok", [4 * 60])["status"], "DURATION PASS")

    def test_invalid_measured_duration_fails_closed(self):
        self.assertEqual(evaluate_audio_parts("youtube", [900, float("nan"), 900])["status"], "DURATION FAIL")

    def test_multipart_report_displays_measured_part_and_total(self):
        evaluation = evaluate_audio_parts("youtube", [15 * 60, 15 * 60, 16 * 60])
        report = format_audio_parts_qa_report("youtube", evaluation)
        self.assertIn("DURATION PASS", report)
        self.assertIn("Part 1: 00:15:00", report)
        self.assertIn("စုစုပေါင်း: 00:46:00", report)

    def test_unknown_platform_rejected(self):
        self.assertEqual(evaluate_audio_duration("instagram", 300)["status"], "NOT READY")

    def test_report_disclaims_scope(self):
        metadata = {"duration_seconds": 300, "audio_stream": "mp3", "decode_ok": True}
        report = format_audio_qa_report("tiktok", metadata, evaluate_audio_duration("tiktok", 300))
        self.assertIn("FFmpeg ဖြင့် တိုင်းတာထားသော Audio ကြာချိန်", report)
        self.assertIn("SRT နှင့် စကားလုံးတစ်လုံးချင်း sync", report)


if __name__ == "__main__":
    unittest.main()
