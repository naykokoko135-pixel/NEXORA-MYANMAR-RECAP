import unittest

from tts_builder import VOICE_MAP, validate_tts_request


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

    def test_text_limit_enforced(self):
        with self.assertRaises(ValueError):
            validate_tts_request("က" * 6001, "female")


if __name__ == "__main__":
    unittest.main()
