import os
import unittest
from unittest.mock import patch

import openai_script_provider as provider


class OpenAIScriptProviderTests(unittest.TestCase):
    def test_status_reports_unconfigured_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(provider.openai_script_status()["configured"])

    def test_requires_verified_notes(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "NEXORA_ALLOW_PAID_AI": "1"}):
            with self.assertRaises(provider.AIScriptError):
                provider.generate_burmese_recap_script("Example", "too short")

    def test_paid_api_disabled_by_default_even_when_key_exists(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            self.assertFalse(provider.openai_script_status()["configured"])
            self.assertTrue(provider.openai_script_status()["key_present"])
            with self.assertRaisesRegex(provider.AIScriptError, "Free-only mode"):
                provider.generate_burmese_recap_script("Example", "A" * 100)

    def test_missing_key_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(provider.AIScriptError):
                provider.generate_burmese_recap_script("Example", "A" * 100)

    def test_youtube_longform_default_has_extended_script_budget(self):
        self.assertEqual(provider.generate_burmese_recap_script.__defaults__, ("youtube", "46-60"))
        self.assertEqual(provider.MAX_NOTES_CHARS, 20000)
        self.assertGreaterEqual(provider.MAX_OUTPUT_TOKENS, 30000)
        self.assertEqual(provider.MAX_SCRIPT_CHARS, 80000)


if __name__ == "__main__":
    unittest.main()
