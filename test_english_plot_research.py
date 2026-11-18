import unittest
from unittest.mock import patch

from english_plot_research import EnglishPlotError, fetch_english_plot_section


class EnglishPlotResearchTests(unittest.TestCase):
    @patch("english_plot_research._api")
    def test_returns_explicit_plot_section(self, mock_api):
        mock_api.side_effect = [
            {"parse": {"title": "Sample Film", "sections": [
                {"line": "Cast", "index": "2"},
                {"line": "Plot", "index": "3"},
            ]}},
            {"parse": {"text": {"*": "<p>" + ("The story unfolds. " * 30) + "</p>"}}},
        ]
        result = fetch_english_plot_section("Sample Film")
        self.assertTrue(result["found"])
        self.assertEqual(result["section"], "Plot")
        self.assertIn("en.wikipedia.org", result["source"])

    @patch("english_plot_research._api")
    def test_rejects_article_without_plot_section(self, mock_api):
        mock_api.return_value = {"parse": {"title": "Sample Film", "sections": [
            {"line": "Cast", "index": "1"}
        ]}}
        with self.assertRaises(EnglishPlotError):
            fetch_english_plot_section("Sample Film")

    def test_rejects_empty_title(self):
        with self.assertRaises(EnglishPlotError):
            fetch_english_plot_section("")


if __name__ == "__main__":
    unittest.main()
