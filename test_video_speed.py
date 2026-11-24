import unittest

from video_speed import (
    build_video_speed_filter,
    normalize_video_speed,
    required_source_duration,
)


class VideoSpeedTests(unittest.TestCase):
    def test_normalize_video_speed(self):
        cases = [
            ("0.5", 0.5),
            ("0.75x", 0.75),
            ("1", 1.0),
            ("1.25", 1.25),
            ("2x", 2.0),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_video_speed(raw), expected)

    def test_speed_filter_changes_video_only(self):
        self.assertEqual(build_video_speed_filter(1.0), "")
        self.assertEqual(build_video_speed_filter(0.5), "setpts=PTS/0.5000")
        self.assertEqual(build_video_speed_filter(2.0), "setpts=PTS/2.0000")

    def test_source_coverage_scales_with_playback_speed(self):
        self.assertEqual(required_source_duration(20, 0.5), 10)
        self.assertEqual(required_source_duration(20, 1.0), 20)
        self.assertEqual(required_source_duration(20, 2.0), 40)

    def test_reject_invalid_speed(self):
        for raw in ("0.1", "2.5", "fast", "", None):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    normalize_video_speed(raw)


if __name__ == "__main__":
    unittest.main()
