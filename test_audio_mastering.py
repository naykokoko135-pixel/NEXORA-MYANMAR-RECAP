import unittest

from audio_mastering import AUDIO_PRESETS, build_audio_filter


class AudioMasteringTests(unittest.TestCase):
    def test_all_audio_presets_are_valid_strings(self):
        for name, value in AUDIO_PRESETS.items():
            self.assertTrue(build_audio_filter(name))
            self.assertIsInstance(value, str)

    def test_unknown_audio_preset_rejected(self):
        with self.assertRaises(ValueError):
            build_audio_filter("invalid")
