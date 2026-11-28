import unittest
from unittest import mock

from studio import settings


class GeminiModelDefaultTests(unittest.TestCase):
    def test_retired_saved_model_is_migrated_in_memory(self):
        with mock.patch(
            "studio.settings.db.kv_get",
            side_effect=lambda key, default=None: (
                {"models": {"gemini": "gemini-2.0-flash"}}
                if key == "ai" else default
            ),
        ):
            current = settings.ai_settings()

        self.assertEqual(current["models"]["gemini"], "gemini-3.8-flash")

    def test_retired_models_are_not_offered(self):
        self.assertNotIn("gemini-2.0-flash", settings.GEMINI_MODELS)
        self.assertNotIn("gemini-1.5-flash", settings.GEMINI_MODELS)
        self.assertIn("gemini-3.8-flash", settings.GEMINI_MODELS)


if __name__ == "__main__":
    unittest.main()
