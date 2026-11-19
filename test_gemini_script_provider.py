import os
import unittest
from unittest.mock import patch

import gemini_script_provider as provider


class GeminiScriptProviderTests(unittest.TestCase):
    def test_status_reports_unconfigured_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(provider.gemini_script_status()["configured"])

    def test_missing_key_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(provider.GeminiScriptError):
                provider.generate_burmese_recap_script("Example", "A" * 100)

    def test_requires_sufficient_notes(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with self.assertRaises(provider.GeminiScriptError):
                provider.generate_burmese_recap_script("Example", "too short")


if __name__ == "__main__":
    unittest.main()
