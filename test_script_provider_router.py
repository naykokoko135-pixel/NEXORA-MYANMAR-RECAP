import os
import unittest
from unittest.mock import patch
import script_provider_router as router


class ScriptProviderRouterTests(unittest.TestCase):
    def test_auto_prefers_configured_gemini(self):
        with patch.dict(os.environ, {"NEXORA_SCRIPT_PROVIDER": "auto"}, clear=True):
            with patch.object(router, "gemini_script_status", return_value={"configured": True, "model": "gemini-test"}):
                with patch.object(router, "openai_script_status", return_value={"configured": True, "model": "openai-test"}):
                    self.assertEqual(router.script_provider_status()["provider"], "gemini")

    def test_auto_uses_openai_when_gemini_not_configured(self):
        with patch.dict(os.environ, {"NEXORA_SCRIPT_PROVIDER": "auto"}, clear=True):
            with patch.object(router, "gemini_script_status", return_value={"configured": False, "model": "gemini-test"}):
                with patch.object(router, "openai_script_status", return_value={"configured": True, "model": "openai-test"}):
                    self.assertEqual(router.script_provider_status()["provider"], "openai")

    def test_selected_gemini_failure_does_not_call_openai(self):
        with patch.dict(os.environ, {"NEXORA_SCRIPT_PROVIDER": "gemini"}, clear=True):
            with patch.object(router, "gemini_script_status", return_value={"configured": True, "model": "gemini-test"}):
                with patch.object(router, "openai_script_status", return_value={"configured": True, "model": "openai-test"}):
                    with patch.object(router, "generate_gemini_script", side_effect=router.GeminiScriptError("quota")) as gemini:
                        with patch.object(router, "generate_openai_script") as openai:
                            with self.assertRaises(router.GeminiScriptError):
                                router.generate_burmese_recap_script("Title", "Verified notes", "tiktok", "4-7")
        gemini.assert_called_once()
        openai.assert_not_called()

    def test_invalid_provider_is_rejected(self):
        with patch.dict(os.environ, {"NEXORA_SCRIPT_PROVIDER": "unknown"}, clear=True):
            with self.assertRaises(router.AIScriptError):
                router.generate_burmese_recap_script("Title", "Verified notes")


if __name__ == "__main__":
    unittest.main()
