import unittest
from unittest.mock import patch

from english_plot_recap import generate_burmese_recap_from_english_plot


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
        self.assertEqual(kwargs["duration"], "3-5")

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
