import unittest
from unittest.mock import patch

from english_plot_recap import generate_burmese_recap_from_english_plot
from openai_script_provider import AIScriptError


class EnglishPlotRecapTests(unittest.TestCase):
    def sample_plot(self):
        return {
            "found": True,
            "plot_text": "A verified-title-linked plot section. " * 20,
            "source": "https://en.wikipedia.org/wiki/Sample_Film",
        }

    @patch("english_plot_recap.generate_burmese_recap_script")
    def test_uses_source_notes_and_returns_provenance(self, mock_generate):
        mock_generate.return_value = "မြန်မာ recap narration"
        script, source = generate_burmese_recap_from_english_plot(
            "Sample Film", self.sample_plot(), "youtube"
        )
        self.assertEqual(script, "မြန်မာ recap narration")
        self.assertEqual(source, "https://en.wikipedia.org/wiki/Sample_Film")
        args, kwargs = mock_generate.call_args
        self.assertEqual(args[0], "Sample Film")
        self.assertIn("လူထုတည်းဖြတ်ရင်းမြစ်", args[1])
        self.assertIn(source, args[1])
        self.assertEqual(kwargs["platform"], "youtube")
        self.assertEqual(kwargs["duration"], "15-20")

    @patch("english_plot_recap.generate_burmese_recap_script")
    def test_uses_platform_specific_duration(self, mock_generate):
        mock_generate.return_value = "မြန်မာ recap narration"
        for platform, duration in (("youtube", "15-20"), ("facebook", "10-15"), ("tiktok", "1-3")):
            with self.subTest(platform=platform):
                generate_burmese_recap_from_english_plot(
                    "Sample Film", self.sample_plot(), platform
                )
                self.assertEqual(mock_generate.call_args.kwargs["duration"], duration)


    @patch("english_plot_recap.generate_gemini_recap_script")
    @patch("english_plot_recap.gemini_script_status")
    @patch("english_plot_recap.generate_burmese_recap_script")
    def test_falls_back_to_gemini_only_on_openai_quota(self, mock_openai, mock_status, mock_gemini):
        mock_openai.side_effect = AIScriptError("OpenAI API Limit/Quota ပြည့်နေသည်။")
        mock_status.return_value = {"configured": True}
        mock_gemini.return_value = "Gemini ဖြင့်ရေးသားထားသော မြန်မာဇာတ်ညွှန်း"
        script, _ = generate_burmese_recap_from_english_plot(
            "Sample Film", self.sample_plot(), "youtube"
        )
        self.assertIn("Gemini", script)
        mock_openai.assert_called_once()
        mock_gemini.assert_called_once()

    @patch("english_plot_recap.gemini_script_status")
    @patch("english_plot_recap.generate_burmese_recap_script")
    def test_does_not_call_gemini_when_openai_error_is_not_quota(self, mock_openai, mock_status):
        mock_openai.side_effect = AIScriptError("OpenAI API authentication မမှန်ပါ။")
        mock_status.return_value = {"configured": True}
        with self.assertRaises(AIScriptError):
            generate_burmese_recap_from_english_plot(
                "Sample Film", self.sample_plot(), "youtube"
            )
        mock_status.assert_not_called()

    @patch("english_plot_recap.gemini_script_status")
    @patch("english_plot_recap.generate_burmese_recap_script")
    def test_explains_gemini_key_requirement_when_openai_quota_is_exhausted(self, mock_openai, mock_status):
        mock_openai.side_effect = AIScriptError("OpenAI API Limit/Quota ပြည့်နေသည်။")
        mock_status.return_value = {"configured": False}
        with self.assertRaisesRegex(AIScriptError, "GEMINI_API_KEY"):
            generate_burmese_recap_from_english_plot(
                "Sample Film", self.sample_plot(), "youtube"
            )
\n    def test_rejects_unknown_platform_before_calling_provider(self):
        with patch("english_plot_recap.generate_burmese_recap_script") as mock_generate:
            with self.assertRaises(ValueError):
                generate_burmese_recap_from_english_plot(
                    "Sample Film", self.sample_plot(), "unknown"
                )
            mock_generate.assert_not_called()

    def test_rejects_non_wikipedia_source(self):
        plot = self.sample_plot()
        plot["source"] = "https://example.org/wiki/Sample_Film"
        with self.assertRaises(ValueError):
            generate_burmese_recap_from_english_plot("Sample Film", plot)

    def test_rejects_missing_or_short_plot(self):
        for plot in ({"found": False}, {
            "found": True, "plot_text": "short",
            "source": "https://en.wikipedia.org/wiki/Sample_Film",
        }):
            with self.assertRaises(ValueError):
                generate_burmese_recap_from_english_plot("Sample Film", plot)


if __name__ == "__main__":
    unittest.main()
