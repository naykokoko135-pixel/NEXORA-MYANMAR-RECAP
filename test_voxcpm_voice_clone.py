import asyncio
import os
import sys
import types
import unittest
from unittest.mock import patch

from voxcpm_voice_clone import validate_voice_clone_request, synthesize_cloned_burmese_voice


class VoiceCloneTests(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(validate_voice_clone_request("မင်္ဂလာပါ", "ref.wav", b"wav"), "မင်္ဂလာပါ")
        for args in [
            ("", "ref.wav", b"wav"),
            ("စာ", "ref.txt", b"wav"),
            ("စာ", "ref.wav", b""),
        ]:
            with self.assertRaises(ValueError):
                validate_voice_clone_request(*args)

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ပိတ်ထားပါတယ်"):
                asyncio.run(synthesize_cloned_burmese_voice("မင်္ဂလာပါ", "ref.wav", b"wav"))

    def test_clone_uses_reference_path(self):
        import wave
        captured = {}
        class FakeModel:
            class TTS:
                sample_rate = 24000
            tts_model = TTS()
            def generate(self, **kwargs):
                captured.update(kwargs)
                self.assert_file_exists = os.path.exists(kwargs["reference_wav_path"])
                return [0.0, 0.1, -0.1]
        class FakeSoundFile:
            @staticmethod
            def write(file_obj, audio, sample_rate, format, subtype):
                with wave.open(file_obj, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(sample_rate)
                    wav.writeframes(b"\x00\x00" * len(audio))
        fake_vox = types.SimpleNamespace(VoxCPM=types.SimpleNamespace(from_pretrained=lambda *a, **k: FakeModel()))
        fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True))
        with patch.dict(os.environ, {"NEXORA_VOXCPM_ENABLED": "1"}):
            with patch.dict(sys.modules, {"voxcpm": fake_vox, "torch": fake_torch, "soundfile": FakeSoundFile}):
                import voxcpm_voice_design
                with patch.object(voxcpm_voice_design, "_model", None):
                    result = asyncio.run(synthesize_cloned_burmese_voice("မင်္ဂလာပါ", "ref.wav", b"reference"))
        self.assertIn("reference_wav_path", captured)
        self.assertTrue(result.startswith(b"RIFF"))
        self.assertFalse(os.path.exists(captured["reference_wav_path"]))


if __name__ == "__main__":
    unittest.main()
