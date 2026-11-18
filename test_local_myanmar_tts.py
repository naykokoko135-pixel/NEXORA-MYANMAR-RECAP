import asyncio
import os
import sys
import types
import unittest
from unittest.mock import patch

from local_myanmar_tts import synthesize_local_burmese_speech


class LocalMyanmarTtsTests(unittest.TestCase):
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
                asyncio.run(synthesize_local_burmese_speech("က" * 1201))

    def test_local_model_returns_wav_without_network_api(self):
        calls = {}

        class FakeModel:
            def __init__(self, device="cpu"):
                calls["device"] = device

            def tts(self, text, **kwargs):
                calls["text"] = text
                calls["kwargs"] = kwargs
                return [0.0, 0.25, -0.25]

        fake_module = types.SimpleNamespace(MyanmarTTS=FakeModel)
        with patch.dict(os.environ, {"NEXORA_LOCAL_TTS_ENABLED": "1"}):
            with patch.dict(sys.modules, {"myanmar_tts": fake_module}):
                import local_myanmar_tts
                local_myanmar_tts._model = None
                try:
                    audio = asyncio.run(synthesize_local_burmese_speech("မင်္ဂလာပါ"))
                finally:
                    local_myanmar_tts._model = None

        self.assertTrue(audio.startswith(b"RIFF"))
        self.assertEqual(calls["device"], "cpu")
        self.assertEqual(calls["text"], "မင်္ဂလာပါ")
        self.assertEqual(calls["kwargs"], {"solver": "euler", "step": 8, "cfg": 3.0})


if __name__ == "__main__":
    unittest.main()
