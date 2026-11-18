import asyncio
import sys
import types
import unittest
from unittest.mock import patch

from tts_builder import VOICE_MAP, VOICE_PRESETS, get_tts_preset, validate_tts_request, build_word_aligned_srt\nfrom scene_tts import parse_scene_script


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
    def test_ttssrt_applies_selected_voice_preset(self):
        calls = {}

        class FakeCommunicate:
            def __init__(self, text, voice, **kwargs):
                calls["voice"] = voice
                calls.update(kwargs)

            async def stream(self):
                yield {"type": "audio", "data": b"fake-mp3"}
                yield {
                    "type": "WordBoundary",
                    "text": "မင်္ဂလာပါ။",
                    "offset": 0,
                    "duration": 12_000_000,
                }

        fake_module = types.SimpleNamespace(Communicate=FakeCommunicate)
        with patch.dict(sys.modules, {"edge_tts": fake_module}):
            audio, srt = asyncio.run(
                __import__("tts_builder").synthesize_burmese_speech_with_srt(
                    "မင်္ဂလာပါ။", "villain"
                )
            )

        self.assertEqual(audio, b"fake-mp3")
        self.assertEqual(calls["voice"], "my-MM-ThihaNeural")
        self.assertEqual(calls["rate"], "-12%")
        self.assertEqual(calls["pitch"], "-5Hz")
        self.assertEqual(calls["boundary"], "WordBoundary")
        self.assertIn("မင်္ဂလာပါ။", srt)

    def test_scene_script_parses_multiple_presets(self):
        scenes = parse_scene_script(
            "[narrator]\\nဇာတ်လမ်းကို စတင်မိတ်ဆက်မယ်။\\n"
            "[hero]\\nငါ အရှုံးမပေးဘူး။\\n"
            "[villain]\\nမင်း ငါ့ကို မတားနိုင်ဘူး။"
        )
        self.assertEqual([scene["preset"] for scene in scenes], ["narrator", "hero", "villain"])
        self.assertEqual(scenes[1]["text"], "ငါ အရှုံးမပေးဘူး။")

    def test_scene_script_rejects_unknown_preset(self):
        with self.assertRaises(ValueError):
            parse_scene_script("[unknown]\\nစာသား")

    def test_scene_script_requires_header(self):
        with self.assertRaises(ValueError):
            parse_scene_script("ခေါင်းစဉ်မပါသော စာသား")

    def test_scene_script_limits_scene_count(self):
        script = "\\n".join(f"[narrator]\\nအခန်း {i}" for i in range(9))
        with self.assertRaises(ValueError):
            parse_scene_script(script)

    def test_text_limit_enforced(self):
        with self.assertRaises(ValueError):
            validate_tts_request("က" * 6001, "female")


if __name__ == "__main__":
    unittest.main()
