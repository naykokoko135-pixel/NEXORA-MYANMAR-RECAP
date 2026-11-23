import unittest
from unittest.mock import patch

import synopsis_preview as preview
from openai_script_provider import AIScriptError
from gemini_script_provider import GeminiScriptError


class SynopsisPreviewTests(unittest.TestCase):
    def test_requires_source_and_minimum_synopsis(self):
        with self.assertRaises(ValueError):
            preview.generate_burmese_synopsis_preview("Haikyu!!", "short", "https://anilist.co/anime/1")
        with self.assertRaises(ValueError):
            preview.generate_burmese_synopsis_preview("Haikyu!!", "A" * 200, "")

    def test_openai_success_uses_short_tiktok_preset(self):
        with patch.object(preview, "generate_burmese_recap_script", return_value="မြန်မာ preview") as mocked:
            script, source = preview.generate_burmese_synopsis_preview(
                "Haikyu!!", "A detailed series synopsis. " * 8, "https://anilist.co/anime/20464"
            )
        self.assertEqual(script, "မြန်မာ preview")
        self.assertEqual(source, "https://anilist.co/anime/20464")
        self.assertEqual(mocked.call_args.kwargs["platform"], "tiktok")
        self.assertEqual(mocked.call_args.kwargs["duration"], "1-3")
        self.assertIn("SERIES-LEVEL SYNOPSIS ONLY", mocked.call_args.args[1])
        self.assertIn("Episode တစ်ခုချင်း", mocked.call_args.args[1])

    def test_free_only_uses_burmese_translation_without_paid_ai(self):
        translated = "ဇာတ်လမ်းသည် အားကစားသမားများ၏ ရည်မှန်းချက်နှင့် ကြိုးစားအားထုတ်မှုကို ဖော်ပြထားသည်။"
        with patch.object(
            preview, "generate_burmese_recap_script",
            side_effect=AIScriptError("Free-only mode ဖွင့်ထားသည်။"),
        ) as ai:
            with patch.object(preview, "_translate_synopsis_to_burmese", return_value=translated):
                script, source = preview.generate_burmese_synopsis_preview(
                    "Haikyu!!", "A detailed series synopsis. " * 8,
                    "https://anilist.co/anime/20464",
                )
        self.assertEqual(source, "https://anilist.co/anime/20464")
        self.assertIn(translated, script)
        self.assertIn("Full Recap မဟုတ်ပါ", script)
        ai.assert_called_once()

    def test_google_failure_uses_mymemory_fallback(self):
        translated = "ဇာတ်လမ်းသည် လူငယ်များ၏ ကြိုးစားမှုနှင့် ရည်မှန်းချက်ကို ဖော်ပြထားသည်။"
        with patch.object(preview, "_translate_google_chunk", side_effect=RuntimeError("Google unavailable")):
            with patch.object(preview, "_translate_mymemory_chunk", return_value=translated) as fallback:
                result = preview._translate_synopsis_to_burmese("A detailed English synopsis for fallback testing.")
        self.assertEqual(result, translated)
        fallback.assert_called_once()

    def test_google_empty_response_uses_mymemory_fallback(self):
        translated = "ဇာတ်လမ်းသည် လူငယ်များ၏ ကြိုးစားမှုနှင့် ရည်မှန်းချက်ကို ဖော်ပြထားသည်။"
        with patch.object(preview, "_translate_google_chunk", return_value=""):
            with patch.object(preview, "_translate_mymemory_chunk", return_value=translated) as fallback:
                result = preview._translate_synopsis_to_burmese("A detailed English synopsis for fallback testing.")
        self.assertEqual(result, translated)
        fallback.assert_called_once()

    def test_google_english_only_response_uses_mymemory_fallback(self):
        translated = "ဇာတ်လမ်းသည် လူငယ်များ၏ ကြိုးစားမှုနှင့် ရည်မှန်းချက်ကို ဖော်ပြထားသည်။"
        with patch.object(preview, "_translate_google_chunk", return_value="This is still English text."):
            with patch.object(preview, "_translate_mymemory_chunk", return_value=translated) as fallback:
                result = preview._translate_synopsis_to_burmese("A detailed English synopsis for fallback testing.")
        self.assertEqual(result, translated)
        fallback.assert_called_once()

    def test_both_free_translation_providers_unavailable_fails_closed(self):
        with patch.object(preview, "_translate_google_chunk", side_effect=RuntimeError("Google unavailable")):
            with patch.object(preview, "_translate_mymemory_chunk", side_effect=RuntimeError("MyMemory unavailable")):
                with self.assertRaisesRegex(AIScriptError, "Google Translate နှင့် MyMemory"):
                    preview._translate_synopsis_to_burmese("A detailed English synopsis for fallback testing.")

    def test_google_translation_success_does_not_call_mymemory(self):
        translated = "ဇာတ်လမ်းသည် လူငယ်များ၏ ကြိုးစားမှုနှင့် ရည်မှန်းချက်ကို ဖော်ပြထားသည်။"
        with patch.object(preview, "_translate_google_chunk", return_value=translated):
            with patch.object(preview, "_translate_mymemory_chunk") as fallback:
                result = preview._translate_synopsis_to_burmese("A detailed English synopsis for fallback testing.")
        self.assertEqual(result, translated)
        fallback.assert_not_called()

    def test_free_translation_failure_does_not_fabricate_script(self):
        with patch.object(
            preview, "generate_burmese_recap_script",
            side_effect=AIScriptError("Free-only mode ဖွင့်ထားသည်။"),
        ):
            with patch.object(
                preview, "_translate_synopsis_to_burmese",
                side_effect=AIScriptError("translation unavailable"),
            ):
                with self.assertRaisesRegex(AIScriptError, "translation unavailable"):
                    preview.generate_burmese_synopsis_preview(
                        "Haikyu!!", "A detailed series synopsis. " * 8,
                        "https://anilist.co/anime/20464",
                    )

    def test_only_quota_error_uses_gemini(self):
        with patch.object(preview, "generate_burmese_recap_script", side_effect=AIScriptError("OpenAI Limit/Quota")):
            with patch.object(preview, "gemini_script_status", return_value={"configured": True}):
                with patch.object(preview, "generate_gemini_recap_script", return_value="Gemini preview") as gemini:
                    script, _ = preview.generate_burmese_synopsis_preview(
                        "Haikyu!!", "A detailed series synopsis. " * 8, "https://anilist.co/anime/20464"
                    )
        self.assertEqual(script, "Gemini preview")
        self.assertEqual(gemini.call_count, 1)

    def test_non_quota_openai_error_does_not_call_gemini(self):
        with patch.object(preview, "generate_burmese_recap_script", side_effect=AIScriptError("HTTP 401")):
            with patch.object(preview, "generate_gemini_recap_script") as gemini:
                with self.assertRaises(AIScriptError):
                    preview.generate_burmese_synopsis_preview(
                        "Haikyu!!", "A detailed series synopsis. " * 8, "https://anilist.co/anime/20464"
                    )
        gemini.assert_not_called()

    def test_gemini_failure_is_reported_without_retry(self):
        with patch.object(preview, "generate_burmese_recap_script", side_effect=AIScriptError("Limit/Quota")):
            with patch.object(preview, "gemini_script_status", return_value={"configured": True}):
                with patch.object(preview, "generate_gemini_recap_script", side_effect=GeminiScriptError("HTTP 404")) as gemini:
                    with self.assertRaisesRegex(AIScriptError, "HTTP 404"):
                        preview.generate_burmese_synopsis_preview(
                            "Haikyu!!", "A detailed series synopsis. " * 8, "https://anilist.co/anime/20464"
                        )
        self.assertEqual(gemini.call_count, 1)


if __name__ == "__main__":
    unittest.main()
