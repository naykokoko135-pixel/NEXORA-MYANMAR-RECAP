import json
import os
import unittest
from unittest.mock import patch

import gemini_script_provider as provider


class _FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _limit):
        return json.dumps(self.body).encode("utf-8")


class GeminiScriptProviderTests(unittest.TestCase):
    def test_status_reports_unconfigured_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            status = provider.gemini_script_status()
            self.assertFalse(status["configured"])
            self.assertEqual(status["model"], "gemini-3.8-flash")

    def test_paid_api_disabled_by_default_even_when_key_exists(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            self.assertFalse(provider.gemini_script_status()["configured"])
            self.assertTrue(provider.gemini_script_status()["key_present"])
            with self.assertRaisesRegex(provider.GeminiScriptError, "Free-only mode"):
                provider.generate_burmese_recap_script("Example", "A" * 100)

    def test_missing_key_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(provider.GeminiScriptError):
                provider.generate_burmese_recap_script("Example", "A" * 100)

    def test_requires_sufficient_notes(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "NEXORA_ALLOW_PAID_AI": "1"}):
            with self.assertRaises(provider.GeminiScriptError):
                provider.generate_burmese_recap_script("Example", "too short")

    def test_extracts_only_model_output_text(self):
        result = {
            "steps": [
                {"type": "thought", "content": [{"type": "text", "text": "private thought"}]},
                {"type": "model_output", "content": [{"type": "text", "text": "မြန်မာဇာတ်ညွှန်း"}]},
            ]
        }
        self.assertEqual(provider._extract_interaction_text(result), "မြန်မာဇာတ်ညွှန်း")

    def test_uses_interactions_endpoint_and_store_false(self):
        script = "မြန်မာ" * 1300
        result = {"steps": [{"type": "model_output", "content": [{"type": "text", "text": script}]}]}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "NEXORA_ALLOW_PAID_AI": "1"}, clear=True):
            with patch.object(provider, "urlopen", return_value=_FakeResponse(result)) as mocked:
                output = provider.generate_burmese_recap_script("Example", "verified notes " * 10, duration="15-20")
        self.assertEqual(output, script)
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "https://generativelanguage.googleapis.com/v1beta/interactions")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "gemini-3.8-flash")
        self.assertFalse(payload["store"])

    def test_404_is_clear_and_does_not_retry(self):
        from urllib.error import HTTPError
        error = HTTPError("https://example.invalid", 404, "not found", {}, None)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            with patch.object(provider, "urlopen", side_effect=error) as mocked:
                with self.assertRaisesRegex(provider.GeminiScriptError, "HTTP 404"):
                    provider.generate_burmese_recap_script("Example", "verified notes " * 10)
        self.assertEqual(mocked.call_count, 1)


if __name__ == "__main__":
    unittest.main()
