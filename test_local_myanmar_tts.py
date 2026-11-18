import asyncio
import os
import sys
import types
import unittest
import wave
from io import BytesIO
from unittest.mock import patch

from local_myanmar_tts import synthesize_local_burmese_speech


class LocalMyanmarTtsTests(unittest.TestCase):
    def tearDown(self):
        import local_myanmar_tts
        local_myanmar_tts._model = None
        local_myanmar_tts._reference_audio = None

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "မဖွင့်ရသေး"):
                asyncio.run(synthesize_local_burmese_speech("စမ်းသပ်စာသား"))

    def test_empty_text_rejected_when_enabled(self):
        with patch.dict(os.environ, {"NEXORA_LOCAL_TTS_ENABLED": "1"}):
            with self.assertRaises(ValueError):
                asyncio.run(synthesize_local_burmese_speech("  "))

    def test_text_limit(self):
        with patch.dict(os.environ, {"NEXORA_LOCAL_TTS_ENABLED": "1"}):
            with self.assertRaises(ValueError):
                asyncio.run(synthesize_local_burmese_speech("က" * 6001))

    def test_long_text_is_synthesized_in_bounded_chunks(self):
        calls = []

        class FakeModel:
            def inference(self, text, ref_audio, language, **kwargs):
                calls.append(text)
                return [0.0, 0.1, -0.1], None

        with patch.dict(os.environ, {"NEXORA_LOCAL_TTS_ENABLED": "1"}):
            with patch("local_myanmar_tts._get_model_and_reference", return_value=(FakeModel(), "/fake/reference.wav")):
                audio = asyncio.run(synthesize_local_burmese_speech("က" * 1201))

        self.assertEqual(len(calls), 2)
        self.assertTrue(all(0 < len(chunk) <= 1200 for chunk in calls))
        with wave.open(BytesIO(audio), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getframerate(), 44100)
            self.assertGreater(wav.getnframes(), 6)

    def test_low_level_api_receives_reference_audio(self):
        calls = {}

        class FakeModel:
            def __init__(self, *args):
                calls["model_args"] = args

            def to(self, device):
                calls["device"] = device
                return self

            def eval(self):
                return self

            def inference(self, text, ref_audio, language, **kwargs):
                calls["text"] = text
                calls["ref_audio"] = ref_audio
                calls["language"] = language
                calls["kwargs"] = kwargs
                return [0.0, 0.25, -0.25], None

        fake_hub = types.SimpleNamespace(
            hf_hub_download=lambda repo_id, filename: f"/fake/{filename}"
        )
        fake_api = types.SimpleNamespace(StableTTSAPI=FakeModel)
        fake_package = types.ModuleType("myanmar_tts")
        fake_package.__path__ = []
        with patch.dict(os.environ, {"NEXORA_LOCAL_TTS_ENABLED": "1"}):
            with patch.dict(sys.modules, {
                "huggingface_hub": fake_hub,
                "myanmar_tts": fake_package,
                "myanmar_tts.api": fake_api,
            }):
                audio = asyncio.run(synthesize_local_burmese_speech("မင်္ဂလာပါ"))

        self.assertTrue(audio.startswith(b"RIFF"))
        self.assertEqual(calls["device"], "cpu")
        self.assertEqual(calls["text"], "မင်္ဂလာပါ")
        self.assertEqual(calls["ref_audio"], "/fake/samples/sample_0.wav")
        self.assertEqual(calls["language"], "burmese")
        self.assertEqual(
            calls["kwargs"],
            {"step": 8, "solver": "euler", "cfg": 3.0},
        )


if __name__ == "__main__":
    unittest.main()
