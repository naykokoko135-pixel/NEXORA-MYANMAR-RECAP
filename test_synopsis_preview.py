import os
import unittest
from urllib.parse import parse_qs, urlparse
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
                with self.assertRaisesRegex(AIScriptError, "ဘာသာပြန်ရင်းမြစ်အားလုံး"):
                    preview._translate_synopsis_to_burmese("A detailed English synopsis for fallback testing.")

    def test_mymemory_splits_long_text_to_provider_byte_limit(self):
        seen = []

        def fake_read_json(request):
            query = parse_qs(urlparse(request.full_url).query)
            part = query["q"][0]
            seen.append(part)
            return {
                "responseStatus": 200,
                "responseData": {"translatedText": "မြန်မာဘာသာပြန်စာသား"},
            }

        with patch.object(preview, "_read_json", side_effect=fake_read_json):
            result = preview._translate_mymemory_chunk("A fairly long English synopsis. " * 35)

        self.assertTrue(preview._has_myanmar_text(result))
        self.assertGreater(len(seen), 1)
        self.assertTrue(all(len(part.encode("utf-8")) <= preview.MYMEMORY_MAX_BYTES for part in seen))

    def test_optional_providers_are_enabled_only_when_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            names = [name for name, _ in preview._configured_translation_providers()]
        self.assertEqual(names, ["Google Translate (keyless)", "MyMemory (keyless)"])

        with patch.dict(os.environ, {
            "NEXORA_LIBRETRANSLATE_URL": "https://translate.example",
            "AZURE_TRANSLATOR_KEY": "test-key",
            "GOOGLE_CLOUD_TRANSLATE_API_KEY": "test-key",
        }, clear=True):
            names = [name for name, _ in preview._configured_translation_providers()]
        self.assertEqual(len(names), 5)
        self.assertIn("LibreTranslate (configured endpoint)", names)
        self.assertIn("Microsoft Translator (configured key)", names)
        self.assertIn("Google Cloud Translation (configured key)", names)

    def test_mymemory_optional_email_is_sent_as_quota_contact(self):
        with patch.dict(os.environ, {"MYMEMORY_EMAIL": "owner@example.com"}, clear=True):
            with patch.object(preview, "_read_json", return_value={
                "responseStatus": "200",
                "responseData": {"translatedText": "မြန်မာဘာသာပြန်စာသား"},
            }) as mocked:
                preview._translate_mymemory_chunk("A short English sentence.")
        query = parse_qs(urlparse(mocked.call_args.args[0].full_url).query)
        self.assertEqual(query["de"], ["owner@example.com"])

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
