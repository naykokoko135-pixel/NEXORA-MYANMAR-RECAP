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
    _validate_wav_bytes,
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

        import wave
        class FakeSoundFile:
            @staticmethod
            def write(file_obj, audio, sample_rate, format, subtype):
                with wave.open(file_obj, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(b"\\x00\\x00" * len(audio))

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
        _validate_wav_bytes(audio)

    def test_malformed_wav_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "WAV"):
            _validate_wav_bytes(b"RIFF\\x00\\x00\\x00\\x00not-a-wave-file")

    def test_empty_wav_is_rejected(self):
        import io
        import wave
        output = io.BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(48000)
        with self.assertRaisesRegex(RuntimeError, "WAV"):
            _validate_wav_bytes(output.getvalue())


if __name__ == "__main__":
    unittest.main()
