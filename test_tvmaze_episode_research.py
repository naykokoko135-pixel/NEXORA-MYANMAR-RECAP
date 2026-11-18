import unittest
from unittest.mock import patch

from tvmaze_synopsis import fetch_tvmaze_episode_summaries


class TVMazeEpisodeResearchTests(unittest.TestCase):
    def _show(self, **overrides):
        show = {
            "id": 45, "name": "Sample Donghua",
            "genres": ["Animation", "Adventure"],
            "network": {"country": {"name": "China"}},
            "url": "https://www.tvmaze.com/shows/45/sample-donghua",
        }
        show.update(overrides)
        return show

    @patch("tvmaze_synopsis._get_json")
    def test_returns_short_episode_summary_excerpts(self, mock_get):
        mock_get.side_effect = [
            [{"show": self._show()}],
            [{
                "season": 1, "number": 1, "name": "First Step",
                "airdate": "2024-01-01",
                "summary": "<p>" + ("A short episode summary. " * 20) + "</p>",
                "url": "https://www.tvmaze.com/episodes/1",
            }],
        ]
        result = fetch_tvmaze_episode_summaries("Sample Donghua")
        self.assertTrue(result["found"])
        self.assertEqual(len(result["episodes"]), 1)
        self.assertLessEqual(len(result["episodes"][0]["summary_excerpt"]), 240)
        self.assertIn("tvmaze.com/episodes/1", result["episodes"][0]["source"])

    @patch("tvmaze_synopsis._get_json")
    def test_rejects_non_animation_genre(self, mock_get):
        mock_get.return_value = [{"show": self._show(genres=["Drama"])}]
        result = fetch_tvmaze_episode_summaries("Sample Donghua")
        self.assertFalse(result["found"])
        self.assertIn("Animation", result["status"])

    @patch("tvmaze_synopsis._get_json")
    def test_rejects_indian_origin(self, mock_get):
        mock_get.return_value = [{"show": self._show(
            network={"country": {"name": "India"}}
        )}]
        result = fetch_tvmaze_episode_summaries("Sample Donghua")
        self.assertFalse(result["found"])
        self.assertIn("အိန္ဒိယ", result["status"])

    @patch("tvmaze_synopsis._get_json")
    def test_rejects_unknown_country(self, mock_get):
        mock_get.return_value = [{"show": self._show(
            network=None, webChannel=None
        )}]
        result = fetch_tvmaze_episode_summaries("Sample Donghua")
        self.assertFalse(result["found"])
        self.assertIn("နိုင်ငံအချက်အလက်", result["status"])

    def test_rejects_empty_title(self):
        self.assertFalse(fetch_tvmaze_episode_summaries("")["found"])


if __name__ == "__main__":
    unittest.main()
