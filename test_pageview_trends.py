import unittest
from datetime import date
from unittest.mock import patch

from pageview_trends import _sample_titles, fetch_category_pageviews, format_category_pageviews


class PageviewTrendTests(unittest.TestCase):
    def test_sample_rotates_and_is_bounded(self):
        titles = ["A", "B", "C", "D"]
        first = _sample_titles(titles, date(2026, 11, 18), 2)
        second = _sample_titles(titles, date(2026, 11, 19), 2)
        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 2)
        self.assertNotEqual(first, second)

    @patch("pageview_trends._fetch_json")
    def test_fetch_compares_two_seven_day_periods(self, fetch):
        fetch.return_value = {"items": [
            {"timestamp": f"202611{day:02d}00", "views": 10 if day < 12 else 20}
            for day in range(5, 19)
        ]}
        result = fetch_category_pageviews(
            {"Anime": ["Show A", "Show B"]},
            as_of=date(2026, 11, 20),
            samples_per_category=1,
        )
        self.assertTrue(result["ok"])
        item = result["categories"]["Anime"][0]
        self.assertEqual(item["recent_views"], 140)
        self.assertEqual(item["previous_views"], 70)
        self.assertEqual(item["change_pct"], 100.0)

    @patch("pageview_trends._fetch_json")
    def test_api_failures_do_not_create_fake_scores(self, fetch):
        fetch.side_effect = OSError("offline")
        result = fetch_category_pageviews(
            {"Donghua": ["Show A"]},
            as_of=date(2026, 11, 20),
            samples_per_category=1,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["categories"]["Donghua"], [])
        self.assertIn("Pageview အချက်အလက် မရရှိပါ", format_category_pageviews(result))

    def test_report_disclaims_video_views(self):
        report = format_category_pageviews({
            "ok": True, "source": "Wikimedia Pageviews API",
            "period_start": "20261104", "period_end": "20261117",
            "categories": {"Anime": [{
                "title": "Show A", "url": "https://en.wikipedia.org/wiki/Show_A",
                "recent_views": 120, "previous_views": 100, "change_pct": 20.0,
            }]},
        })
        self.assertIn("YouTube/Facebook/TikTok", report)
        self.assertIn("Show A", report)


if __name__ == "__main__":
    unittest.main()
