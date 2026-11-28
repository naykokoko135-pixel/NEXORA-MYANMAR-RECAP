import os
import unittest
from unittest import mock

from studio.base import config
from studio import providers, settings


class GeminiModelTests(unittest.TestCase):
    @unittest.skipIf(os.getenv("GEMINI_MODELS") or os.getenv("GEMINI_MODEL"), "deployment override present: defaults not under test")
    def test_defaults_are_the_live_model_not_retired_ones(self):
        self.assertEqual(config.GEMINI_DEFAULT_MODEL, "gemini-3.8-flash")
        for retired in config.GEMINI_RETIRED:
            self.assertNotIn(retired, settings.GEMINI_MODELS)

    def test_retired_model_names_are_mapped_before_the_request(self):
        for old in ("gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"):
            resp = mock.Mock(status_code=200)
            resp.json.return_value = {"steps": [{"type": "thought", "content": []}, {"type": "model_output", "content": [{"type": "text", "text": "ok"}]}]}
            with mock.patch.object(providers, "key_for", return_value="k"), mock.patch.object(providers.requests, "post", return_value=resp) as post, \
                    mock.patch.object(config, "LLM_DELAY", 0):
                out = providers._call_gemini("hi", "sys", old, False)
            self.assertEqual(out, "ok")
            self.assertTrue(post.call_args.args[0].endswith("/v1beta/interactions"))
            self.assertEqual(post.call_args.kwargs["json"]["model"], "gemini-3.8-flash", old)
            self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "k")
            self.assertNotIn("key", post.call_args.kwargs.get("params", {}))


    def test_key_is_scrubbed_and_empty_output_is_an_error(self):
        boom = providers.requests.RequestException("connection to https://x?key=SECRETKEY failed")
        with mock.patch.object(providers, "key_for", return_value="SECRETKEY"), mock.patch.object(config, "LLM_DELAY", 0), \
                mock.patch.object(providers.requests, "post", side_effect=boom):
            with self.assertRaises(providers.ProviderError) as cm:
                providers._call_gemini("hi", "", "gemini-3.8-flash", False)
        self.assertNotIn("SECRETKEY", str(cm.exception))
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"steps": []}
        with mock.patch.object(providers, "key_for", return_value="k"), mock.patch.object(config, "LLM_DELAY", 0), \
                mock.patch.object(providers.requests, "post", return_value=resp):
            with self.assertRaises(providers.ProviderError):
                providers._call_gemini("hi", "", "gemini-3.8-flash", False)


if __name__ == "__main__":
    unittest.main()
