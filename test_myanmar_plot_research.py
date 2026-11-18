import unittest
from unittest.mock import patch

from myanmar_plot_research import PlotResearchError, fetch_burmese_plot_section


class MyanmarPlotResearchTests(unittest.TestCase):
    @patch("myanmar_plot_research._api")
    def test_uses_only_explicit_plot_section(self, mock_api):
        mock_api.side_effect = [
            {
                "parse": {
                    "title": "ဥပမာဇာတ်ကား",
                    "sections": [
                        {"line": "သရုပ်ဆောင်များ", "index": "2"},
                        {"line": "ဇာတ်လမ်းအကျဉ်း", "index": "3"},
                    ],
                }
            },
            {
                "parse": {
                    "text": {
                        "*": "<p>" + ("ဒီဇာတ်လမ်းအကျဉ်းဖြစ်သည်။ " * 30) + "</p>"
                    }
                }
            },
        ]
        result = fetch_burmese_plot_section("ဥပမာဇာတ်ကား")
        self.assertTrue(result["found"])
        self.assertEqual(result["section"], "ဇာတ်လမ်းအကျဉ်း")
        self.assertIn("ဒီဇာတ်လမ်းအကျဉ်း", result["plot_text"])
        self.assertIn("my.wikipedia.org/wiki/", result["source"])
        self.assertEqual(mock_api.call_count, 2)

    @patch("myanmar_plot_research._api")
    def test_does_not_use_other_sections_as_plot(self, mock_api):
        mock_api.return_value = {
            "parse": {
                "title": "ဥပမာဇာတ်ကား",
                "sections": [
                    {"line": "သရုပ်ဆောင်များ", "index": "2"},
                    {"line": "ထုတ်လုပ်မှု", "index": "3"},
                ],
            }
        }
        with self.assertRaisesRegex(PlotResearchError, "ဇာတ်လမ်းအကျဉ်း"):
            fetch_burmese_plot_section("ဥပမာဇာတ်ကား")
        self.assertEqual(mock_api.call_count, 1)

    def test_rejects_missing_title(self):
        with self.assertRaises(PlotResearchError):
            fetch_burmese_plot_section("")


if __name__ == "__main__":
    unittest.main()
