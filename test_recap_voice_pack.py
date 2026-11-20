import unittest
from recap_voice_pack import MAX_RECAP_SCRIPT_CHARS, parse_recap_voice_request

PRESETS = {"narrator", "hero", "villain", "female", "male"}

class RecapVoicePackTests(unittest.TestCase):
    def test_default_narrator_and_script(self):
        self.assertEqual(parse_recap_voice_request("/recapvoice\nဒီနေ့ ဇာတ်လမ်းကို စတင်မိတ်ဆက်ပါမယ်။", PRESETS),
                         ("narrator", "ဒီနေ့ ဇာတ်လမ်းကို စတင်မိတ်ဆက်ပါမယ်။"))

    def test_selected_preset(self):
        self.assertEqual(parse_recap_voice_request("/recapvoice hero\nဇာတ်လမ်းစာသား", PRESETS),
                         ("hero", "ဇာတ်လမ်းစာသား"))

    def test_missing_script_rejected(self):
        with self.assertRaises(ValueError):
            parse_recap_voice_request("/recapvoice narrator", PRESETS)

    def test_unknown_preset_rejected(self):
        with self.assertRaises(ValueError):
            parse_recap_voice_request("/recapvoice unknown\nစာသား", PRESETS)

    def test_script_limit_supports_long_form_narration(self):
        self.assertEqual(MAX_RECAP_SCRIPT_CHARS, 80000)
        script = "က" * 50000
        self.assertEqual(len(parse_recap_voice_request("/recapvoice narrator\n" + script, PRESETS)[1]), 50000)
        with self.assertRaises(ValueError):
            parse_recap_voice_request("/recapvoice narrator\n" + ("က" * (MAX_RECAP_SCRIPT_CHARS + 1)), PRESETS)

if __name__ == "__main__":
    unittest.main()
