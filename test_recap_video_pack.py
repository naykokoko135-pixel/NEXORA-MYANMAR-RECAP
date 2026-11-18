import unittest
from recap_video_pack import MAX_RECAP_SCRIPT_CHARS, parse_recap_video_request, validate_non_indian_wikidata_metadata
from licensed_narrated_clip import _subtitle_duration_seconds, LicensedClipError
PRESETS = {"narrator", "hero", "female"}

class RecapVideoPackTests(unittest.TestCase):
    def test_parse_title_preset_and_script(self):
        self.assertEqual(parse_recap_video_request("/recapvideo Frieren: Beyond Journey's End\nnarrator\nမြန်မာ narration", PRESETS),
                         ("Frieren: Beyond Journey's End", "narrator", "မြန်မာ narration"))
    def test_default_preset(self):
        self.assertEqual(parse_recap_video_request("/recapvideo Example Show\nဇာတ်လမ်းစာသား", PRESETS),
                         ("Example Show", "narrator", "ဇာတ်လမ်းစာသား"))
    def test_missing_title_or_script_rejected(self):
        for message in ("/recapvideo\nဇာတ်လမ်း", "/recapvideo Example Show"):
            with self.assertRaises(ValueError):
                parse_recap_video_request(message, PRESETS)
    def test_script_limit_and_preset(self):
        with self.assertRaises(ValueError):
            parse_recap_video_request("/recapvideo Example\n" + ("က" * (MAX_RECAP_SCRIPT_CHARS + 1)), PRESETS)
        # An unrecognized first line is treated as narration, not silently as a voice preset.
        self.assertEqual(
            parse_recap_video_request("/recapvideo Example\nunknown\nဇာတ်လမ်း", PRESETS),
            ("Example", "narrator", "unknown\nဇာတ်လမ်း"),
        )
    def test_subtitle_duration_is_read_without_truncation(self):
        self.assertAlmostEqual(
            _subtitle_duration_seconds("1\n00:00:00,000 --> 00:00:05,250\nမြန်မာစာ\n"),
            5.25,
        )
        with self.assertRaises(LicensedClipError):
            _subtitle_duration_seconds("not an SRT")

    def test_requires_known_non_indian_country(self):
        self.assertEqual(validate_non_indian_wikidata_metadata({"found": True, "countries": ["Japan"]}), ["Japan"])
        for metadata in ({"found": False, "status": "not found"}, {"found": True, "countries": []},
                         {"found": True, "countries": ["India"]}, {"found": True, "countries": ["Japan", "India"]}):
            with self.assertRaises(ValueError):
                validate_non_indian_wikidata_metadata(metadata)

if __name__ == "__main__":
    unittest.main()
