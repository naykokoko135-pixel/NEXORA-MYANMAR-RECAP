import unittest
from recap_voice_pack import MAX_RECAP_SCRIPT_CHARS, parse_recap_voice_request, parse_recap_voice_parts_request

PRESETS = {"narrator", "hero", "villain", "female", "male"}

class RecapVoicePackTests(unittest.TestCase):
    def test_default_narrator_and_script(self):
        self.assertEqual(parse_recap_voice_request("/recapvoice\nဒီနေ့ ဇာတ်လမ်းကို စတင်မိတ်ဆက်ပါမယ်။", PRESETS),
                         ("narrator", "ဒီနေ့ ဇာတ်လမ်းကို စတင်မိတ်ဆက်ပါမယ်။"))

    def test_selected_preset(self):
        self.assertEqual(parse_recap_voice_request("/recapvoice hero\nဇာတ်လမ်းစာသား", PRESETS),
                         ("hero", "ဇာတ်လမ်းစာသား"))

    def test_myvoice_accepts_optional_profile_name(self):
        request = "/recapvoice myvoice ကိုယ်ပိုင်အသံ\nမင်္ဂလာပါ။ ဒီနေ့ ဇာတ်လမ်းတစ်ပုဒ်ကို တင်ဆက်ပေးပါမယ်။"
        self.assertEqual(
            parse_recap_voice_request(request, PRESETS),
            ("myvoice", "မင်္ဂလာပါ။ ဒီနေ့ ဇာတ်လမ်းတစ်ပုဒ်ကို တင်ဆက်ပေးပါမယ်။"),
        )

    def test_missing_script_rejected(self):
        with self.assertRaises(ValueError):
            parse_recap_voice_request("/recapvoice narrator", PRESETS)

    def test_unknown_preset_rejected(self):
        with self.assertRaises(ValueError):
            parse_recap_voice_request("/recapvoice unknown\nစာသား", PRESETS)

    def test_three_part_script_parser_accepts_exact_parts(self):
        request = "/recapvoice3 narrator\n[PART 1]\nပထမပိုင်း\n[PART 2]\nဒုတိယပိုင်း\n[PART 3]\nတတိယပိုင်း"
        preset, parts = parse_recap_voice_parts_request(request, PRESETS)
        self.assertEqual(preset, "narrator")
        self.assertEqual(parts, {1: "ပထမပိုင်း", 2: "ဒုတိယပိုင်း", 3: "တတိယပိုင်း"})

    def test_three_part_parser_rejects_missing_extra_duplicate_and_empty_parts(self):
        for request in (
            "/recapvoice3\n[PART 1]\na\n[PART 2]\nb",
            "/recapvoice3\n[PART 1]\na\n[PART 2]\nb\n[PART 3]\nc\n[PART 4]\nd",
            "/recapvoice3\n[PART 1]\na\n[PART 2]\nb\n[PART 2]\nc\n[PART 3]\nd",
            "/recapvoice3\n[PART 1]\na\n[PART 2]\n\n[PART 3]\nc",
        ):
            with self.subTest(request=request), self.assertRaises(ValueError):
                parse_recap_voice_parts_request(request, PRESETS)

    def test_three_part_parser_rejects_unknown_preset(self):
        with self.assertRaises(ValueError):
            parse_recap_voice_parts_request("/recapvoice3 unknown\n[PART 1]\na\n[PART 2]\nb\n[PART 3]\nc", PRESETS)

    def test_script_limit_supports_long_form_narration(self):
        self.assertEqual(MAX_RECAP_SCRIPT_CHARS, 80000)
        script = "က" * 50000
        self.assertEqual(len(parse_recap_voice_request("/recapvoice narrator\n" + script, PRESETS)[1]), 50000)
        with self.assertRaises(ValueError):
            parse_recap_voice_request("/recapvoice narrator\n" + ("က" * (MAX_RECAP_SCRIPT_CHARS + 1)), PRESETS)

if __name__ == "__main__":
    unittest.main()
