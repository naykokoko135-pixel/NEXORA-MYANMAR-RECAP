import unittest
from unittest import mock

from studio.base import config
from studio import providers, settings


class GeminiModelTests(unittest.TestCase):
    def test_defaults_are_the_live_model_not_retired_ones(self):
        self.assertEqual(config.GEMINI_DEFAULT_MODEL, "gemini-3.8-flash")
        for retired in config.GEMINI_RETIRED:
            self.assertNotIn(retired, settings.GEMINI_MODELS)

    def test_retired_model_names_are_mapped_before_the_request(self):
        for old in ("gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"):
            resp = mock.Mock(status_code=200)
            resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
            with mock.patch.object(providers, "key_for", return_value="k"), mock.patch.object(providers.requests, "post", return_value=resp) as post, \
                    mock.patch.object(config, "LLM_DELAY", 0):
                providers._call_gemini("hi", "", old, False)
            self.assertIn("models/gemini-3.8-flash:generateContent", post.call_args.args[0], old)


if __name__ == "__main__":
    unittest.main()
