import unittest

from tts_builder import VOICE_MAP, VOICE_PRESETS, get_tts_preset, validate_tts_request, build_word_aligned_srt


class BurmeseTtsValidationTests(unittest.TestCase):
    def test_burmese_voice_options(self):
        self.assertEqual(VOICE_MAP["female"], "my-MM-NilarNeural")
        self.assertEqual(VOICE_MAP["male"], "my-MM-ThihaNeural")

    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            validate_tts_request("  ", "female")

    def test_unknown_voice_rejected(self):
        with self.assertRaises(ValueError):
            validate_tts_request("စမ်းသပ်စာသား", "unknown")


    def test_word_boundary_srt_uses_real_offsets(self):
        srt = build_word_aligned_srt([
            {"text": "မင်္ဂလာပါ။", "offset": 0, "duration": 12_000_000},
            {"text": " နေကောင်းလား။", "offset": 12_500_000, "duration": 15_000_000},
        ])
        self.assertIn("00:00:00,000 --> 00:00:01,200", srt)
        self.assertIn("မင်္ဂလာပါ။", srt)
        self.assertIn("နေကောင်းလား။", srt)
        self.assertIn("00:00:01,250 --> 00:00:02,750", srt)

    def test_empty_word_boundaries_rejected(self):
        with self.assertRaises(ValueError):
            build_word_aligned_srt([])

    def test_story_voice_presets_use_supported_burmese_voices(self):
        self.assertGreaterEqual(len(VOICE_PRESETS), 10)
        for name, preset in VOICE_PRESETS.items():
            self.assertIn(preset["voice"], VOICE_MAP)
            self.assertIn("rate", preset)
            self.assertIn("pitch", preset)
            self.assertEqual(validate_tts_request("စမ်းသပ်စာသား", name), VOICE_MAP[preset["voice"]])

    def test_villain_preset_is_lower_and_slower(self):
        preset = get_tts_preset("villain")
        self.assertEqual(preset["voice"], "male")
        self.assertEqual(preset["rate"], "-12%")
        self.assertEqual(preset["pitch"], "-5Hz")
    def test_text_limit_enforced(self):
        with self.assertRaises(ValueError):
            validate_tts_request("က" * 6001, "female")


if __name__ == "__main__":
    unittest.main()
