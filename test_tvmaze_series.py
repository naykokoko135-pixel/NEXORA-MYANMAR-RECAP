import json
import unittest
from io import BytesIO
from urllib.error import URLError
from unittest.mock import patch

from tvmaze_series import fetch_series_episode_guide, format_series_episode_guide


class Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class TVmazeSeriesTests(unittest.TestCase):
    @patch("tvmaze_series.urlopen")
    def test_exact_show_returns_season_episode_counts_and_sources(self, mock_urlopen):
        search = [{
            "score": 1.0,
            "show": {
                "id": 101, "name": "Example Series", "status": "Ended",
                "premiered": "2020-01-01", "ended": "2022-01-01",
                "network": {"name": "Example Network"},
            },
        }]
        episodes = [
            {"season": 1, "number": 1, "name": "Beginning", "airdate": "2020-01-01"},
            {"season": 1, "number": 2, "name": "Next Step", "airdate": "2020-01-08"},
            {"season": 2, "number": 1, "name": "Return", "airdate": "2021-01-01"},
            {"season": 0, "number": 1, "name": "Special", "airdate": "2021-02-01"},
        ]
        mock_urlopen.side_effect = [
            Response(json.dumps(search).encode()),
            Response(json.dumps(episodes).encode()),
        ]
        result = fetch_series_episode_guide("Example Series")
        self.assertTrue(result["found"])
        self.assertEqual(result["season_count"], 2)
        self.assertEqual(result["episode_count"], 3)
        self.assertEqual(result["special_count"], 1)
        self.assertEqual(result["seasons"], {1: 2, 2: 1})
        formatted = format_series_episode_guide(result)
        self.assertIn("Season 1: 2 Episodes", formatted)
        self.assertIn("tvmaze.com/shows/101/episodes", formatted)
        self.assertIn("CC BY-SA", formatted)

    @patch("tvmaze_series.urlopen")
    def test_unrelated_fuzzy_search_result_is_rejected(self, mock_urlopen):
        mock_urlopen.return_value = Response(json.dumps([{
            "show": {"id": 5, "name": "Example Series: The Movie"}
        }]).encode())
        result = fetch_series_episode_guide("Example Series")
        self.assertFalse(result["found"])
        self.assertIn("အတိအကျ", result["status"])
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("tvmaze_series.urlopen")
    def test_duplicate_exact_titles_are_not_selected_automatically(self, mock_urlopen):
        mock_urlopen.return_value = Response(json.dumps([
            {"show": {"id": 1, "name": "Same Name"}},
            {"show": {"id": 2, "name": "Same Name"}},
        ]).encode())
        result = fetch_series_episode_guide("Same Name")
        self.assertFalse(result["found"])
        self.assertIn("အမည်တူ", result["status"])

    @patch("tvmaze_series.urlopen")
    def test_api_failure_does_not_invent_episode_count(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("offline")
        result = fetch_series_episode_guide("Example Series")
        self.assertFalse(result["found"])
        self.assertIn("မခန့်မှန်းထားပါ", result["status"])

    def test_invalid_title_is_rejected(self):
        result = fetch_series_episode_guide("")
        self.assertFalse(result["found"])

    def test_missing_series_data_is_formatted_clearly(self):
        text = format_series_episode_guide({"found": False, "status": "မရရှိပါ"})
        self.assertIn("Season / Episode", text)
        self.assertIn("မရရှိပါ", text)


if __name__ == "__main__":
    unittest.main()
