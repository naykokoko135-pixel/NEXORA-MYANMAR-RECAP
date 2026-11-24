import unittest
from audio_mix import build_background_music_graph

class BackgroundMusicMixTests(unittest.TestCase):
    def test_ducking_graph(self):
        graph, output = build_background_music_graph(0.2, True)
        self.assertEqual(output, "[aout]")
        self.assertIn("sidechaincompress", graph)
        self.assertIn("volume=0.200", graph)

    def test_non_ducking_graph(self):
        graph, _ = build_background_music_graph(0.12, False)
        self.assertNotIn("sidechaincompress", graph)
        self.assertIn("amix=inputs=2", graph)

    def test_invalid_volume_and_indexes(self):
        with self.assertRaises(ValueError):
            build_background_music_graph(1.5)
        with self.assertRaises(ValueError):
            build_background_music_graph(0.2, True, 1, 1)
