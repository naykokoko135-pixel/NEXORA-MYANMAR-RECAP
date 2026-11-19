import os
import unittest
from unittest.mock import patch

import openai_script_provider as provider


class OpenAIScriptProviderTests(unittest.TestCase):
    def test_status_reports_unconfigured_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(provider.openai_script_status()["configured"])

    def test_requires_verified_notes(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with self.assertRaises(provider.AIScriptError):
                provider.generate_burmese_recap_script("Example", "too short")

    def test_missing_key_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(provider.AIScriptError):
                provider.generate_burmese_recap_script("Example", "A" * 100)


if __name__ == "__main__":
    unittest.main()
