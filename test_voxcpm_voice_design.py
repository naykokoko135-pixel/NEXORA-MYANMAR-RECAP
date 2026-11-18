import asyncio
import os
import sys
import types
import unittest
from unittest.mock import patch

from voxcpm_voice_design import (
    VOICE_DESIGNS,
    synthesize_designed_burmese_voice,
    validate_voice_design_request,
)


class VoxCPMVoiceDesignTests(unittest.TestCase):
    def test_fictional_voice_profiles_are_available(self):
        self.assertGreaterEqual(len(VOICE_DESIGNS), 8)
        self.assertIn("story_male", VOICE_DESIGNS)
        self.assertIn("villain", VOICE_DESIGNS)

    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            validate_voice_design_request("", "story_male")

    def test_unknown_voice_rejected(self):
        with self.assertRaises(ValueError):
            validate_voice_design_request("မင်္ဂလာပါ", "unknown")

    def test_text_limit_enforced(self):
        with self.assertRaises(ValueError):
            validate_voice_design_request("က" * 3001, "story_male")

    def test_backend_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "မဖွင့်ထားပါ"):
                asyncio.run(synthesize_designed_burmese_voice("မင်္ဂလာပါ", "story_male"))

    def test_enabled_backend_generates_wav(self):
        class FakeModel:
            class TTS:
                sample_rate = 48000
            tts_model = TTS()

            def generate(self, **kwargs):
                self.kwargs = kwargs
                return [0.0, 0.1, -0.1]

        import io
        class FakeSoundFile:
            @staticmethod
            def write(file_obj, audio, sample_rate, format, subtype):
                file_obj.write(b"RIFF" + b"fake-wav-data")

        fake_voxcpm = types.SimpleNamespace(VoxCPM=types.SimpleNamespace(
            from_pretrained=lambda *args, **kwargs: FakeModel()
        ))
        with patch.dict(os.environ, {"NEXORA_VOXCPM_ENABLED": "1"}):
            with patch.dict(sys.modules, {
                "voxcpm": fake_voxcpm,
                "soundfile": FakeSoundFile,
            }):
                import voxcpm_voice_design
                with patch.object(voxcpm_voice_design, "_model", None):
                    audio = asyncio.run(
                        synthesize_designed_burmese_voice("မင်္ဂလာပါ", "story_male")
                    )
        self.assertTrue(audio.startswith(b"RIFF"))


if __name__ == "__main__":
    unittest.main()
