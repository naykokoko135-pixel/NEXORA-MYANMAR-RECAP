import unittest
from recap_video_pack import MAX_RECAP_SCRIPT_CHARS, parse_recap_video_request, validate_non_indian_wikidata_metadata, build_recap_video_sidecars
from licensed_narrated_clip import _subtitle_duration_seconds, LicensedClipError, build_licensed_attribution_note
PRESETS = {"narrator", "hero", "female"}

class RecapVideoPackTests(unittest.TestCase):
    def test_builds_separate_mp3_and_utf8_srt_sidecars(self):
        audio, subtitles = build_recap_video_sidecars(
            b"fake-mp3",
            "1\\n00:00:00,000 --> 00:00:01,000\\nမြန်မာစာ\\n",
        )
        self.assertEqual(audio, b"fake-mp3")
        self.assertTrue(subtitles.startswith(b"\xef\xbb\xbf"))
        self.assertIn("မြန်မာစာ".encode("utf-8"), subtitles)

    def test_rejects_invalid_sidecar_assets(self):
        for audio, srt in ((b"", "1\n00:00:00,000 --> 00:00:01,000\nစာ"), (b"mp3", "")):
            with self.assertRaises(ValueError):
                build_recap_video_sidecars(audio, srt)

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
    def test_attribution_note_contains_license_creator_and_source(self):
        note = build_licensed_attribution_note(
            {
                "title": "File:Example.webm",
                "artist": "<a href='https://example.org'>Creator</a>",
                "attribution": "Creator — CC BY",
                "license": "CC BY-SA 4.0",
                "usage_terms": "Share alike",
                "source_page": "https://commons.wikimedia.org/wiki/File:Example.webm",
            },
            "Example Show",
            "https://www.wikidata.org/wiki/Q123",
        )
        self.assertIn("Creator", note)
        self.assertNotIn("<a href", note)
        self.assertIn("CC BY-SA 4.0", note)
        self.assertIn("https://commons.wikimedia.org/wiki/File:Example.webm", note)
        self.assertIn("Share-Alike", note)

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
