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
        self.assertIn("verification_status", item)

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
        report = format_category_pageviews(result)
        self.assertIn("Pageview အချက်အလက် မရရှိပါ", report)
        self.assertIn("ဒေတာမရရှိပါ", report)
        self.assertIn("မခန့်မှန်းထားပါ", report)

    def test_report_disclaims_video_views(self):
        report = format_category_pageviews({
            "ok": True, "source": "Wikimedia Pageviews API (English Wikipedia)",
            "period_start": "20261104", "period_end": "20261117",
            "samples_per_category": 2,
            "categories": {"Anime": [{
                "title": "Show A", "url": "https://en.wikipedia.org/wiki/Show_A",
                "recent_views": 120, "previous_views": 100, "change_pct": 20.0,
                "verification_status": "လူကိုယ်တိုင် မူရင်းနှင့် ထပ်မံစစ်ဆေးရန်",
            }]},
        })
        self.assertIn("YouTube/Facebook/TikTok", report)
        self.assertIn("Show A", report)
        self.assertIn("English Wikipedia article views", report)
        self.assertIn("ယနေ့နမူနာအတွင်း", report)
        self.assertIn("Wikipedia source:", report)
        self.assertIn("လူကိုယ်တိုင်", report)
        self.assertIn("မရရှိသေးပါ", report)

    def test_partial_category_data_is_marked_unavailable(self):
        report = format_category_pageviews({
            "ok": True, "samples_per_category": 2,
            "categories": {"Anime": [], "Donghua": [{
                "title": "Show B", "url": "https://en.wikipedia.org/wiki/Show_B",
                "recent_views": 5, "previous_views": 4, "change_pct": 25.0,
            }]},
        })
        self.assertIn("Anime — နမူနာ 2 ခုအနက် ဒေတာရရှိမှု 0 ခု", report)
        self.assertIn("Donghua — နမူနာ 2 ခုအနက် ဒေတာရရှိမှု 1 ခု", report)


if __name__ == "__main__":
    unittest.main()
