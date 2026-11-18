import unittest

from verified_plot_narration import generate_burmese_plot_narration


class VerifiedPlotNarrationTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "found": True,
            "title": "Example Anime",
            "title_my": "ဥပမာ အန်နီမေးရှင်း",
            "countries": ["Japan"],
        }
        self.plot = {
            "found": True,
            "title": "ဥပမာ အန်နီမေးရှင်း",
            "plot_text": "ဇာတ်လမ်းအကျဉ်းစာသား။ " * 50,
            "source": "https://my.wikipedia.org/wiki/Example",
        }

    def test_narration_uses_source_text_and_discloses_source(self):
        script = generate_burmese_plot_narration(self.metadata, self.plot)
        self.assertIn("ဥပမာ အန်နီမေးရှင်း", script)
        self.assertIn("ဇာတ်လမ်းအကျဉ်းစာသား", script)
        self.assertIn("Wikipedia", script)
        self.assertIn("မခန့်မှန်းထားပါ", script)

    def test_rejects_indian_title(self):
        self.metadata["countries"] = ["India"]
        with self.assertRaisesRegex(ValueError, "အိန္ဒိယ"):
            generate_burmese_plot_narration(self.metadata, self.plot)

    def test_rejects_missing_plot_source(self):
        with self.assertRaises(ValueError):
            generate_burmese_plot_narration(self.metadata, {"found": False})


if __name__ == "__main__":
    unittest.main()
