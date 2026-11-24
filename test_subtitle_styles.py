import unittest
from subtitle_styles import SUBTITLE_STYLES, build_subtitle_filter

class SubtitleStyleTests(unittest.TestCase):
    def test_all_styles_build_filter(self):
        for style in SUBTITLE_STYLES:
            value = build_subtitle_filter("/tmp/captions.srt", style)
            self.assertIn("subtitles=filename=", value)
            self.assertIn("FontName=Noto Sans Myanmar", value)

    def test_invalid_style_and_path(self):
        with self.assertRaises(ValueError):
            build_subtitle_filter("/tmp/captions.srt", "comic-sans")
        with self.assertRaises(ValueError):
            build_subtitle_filter("/tmp/bad'path.srt", "classic")
