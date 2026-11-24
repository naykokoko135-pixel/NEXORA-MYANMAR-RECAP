import unittest
from fade_effects import build_edge_fade_filters

class EdgeFadeTests(unittest.TestCase):
    def test_video_and_audio_fades(self):
        video, audio = build_edge_fade_filters(60, 0.8)
        self.assertIn("fade=t=in", video)
        self.assertIn("fade=t=out:st=59.200", video)
        self.assertIn("afade=t=in", audio)
        self.assertIn("afade=t=out:st=59.200", audio)

    def test_disabled_and_invalid(self):
        self.assertEqual(build_edge_fade_filters(10, 0), ("", ""))
        with self.assertRaises(ValueError):
            build_edge_fade_filters(5, 3)
        with self.assertRaises(ValueError):
            build_edge_fade_filters(10, -1)
