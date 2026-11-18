import unittest
from unittest.mock import patch

from tvmaze_synopsis import fetch_tvmaze_synopsis


class TVMazeSynopsisTests(unittest.TestCase):
    def _show(self, **overrides):
        show = {
            "id": 22, "name": "Sample Cartoon",
            "summary": "<p>A series overview. " + ("More information. " * 10) + "</p>",
            "url": "https://www.tvmaze.com/shows/22/sample-cartoon",
            "genres": ["Animation", "Children"], "premiered": "2021-01-01",
            "status": "Ended",
            "network": {"country": {"name": "United States"}},
        }
        show.update(overrides)
        return show

    @patch("tvmaze_synopsis._get_json")
    def test_exact_match_returns_series_overview(self, mock_get):
        mock_get.return_value = [{"score": 1, "show": self._show()}]
        result = fetch_tvmaze_synopsis("Sample Cartoon")
        self.assertTrue(result["found"])
        self.assertEqual(result["scope"], "series_overview_not_episode_plot")
        self.assertNotIn("<p>", result["summary"])

    @patch("tvmaze_synopsis._get_json")
    def test_rejects_fuzzy_match(self, mock_get):
        mock_get.return_value = [{"score": 1, "show": self._show(name="Sample Cartoon 2")}]
        self.assertFalse(fetch_tvmaze_synopsis("Sample Cartoon")["found"])

    @patch("tvmaze_synopsis._get_json")
    def test_excludes_indian_origin(self, mock_get):
        mock_get.return_value = [{"score": 1, "show": self._show(
            network={"country": {"name": "India"}}
        )}]
        result = fetch_tvmaze_synopsis("Sample Cartoon")
        self.assertFalse(result["found"])
        self.assertIn("အိန္ဒိယ", result["status"])

    @patch("tvmaze_synopsis._get_json")
    def test_rejects_unknown_country(self, mock_get):
        mock_get.return_value = [{"score": 1, "show": self._show(
            network=None, webChannel=None
        )}]
        result = fetch_tvmaze_synopsis("Sample Cartoon")
        self.assertFalse(result["found"])
        self.assertIn("နိုင်ငံအချက်အလက်", result["status"])

    def test_rejects_empty_title(self):
        self.assertFalse(fetch_tvmaze_synopsis("")["found"])


if __name__ == "__main__":
    unittest.main()
