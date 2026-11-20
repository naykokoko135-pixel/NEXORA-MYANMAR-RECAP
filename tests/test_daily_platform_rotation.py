"""Regression tests for NEXORA's daily three-platform research rotation."""
import unittest
from datetime import date, timedelta

from daily_auto import (
    TITLE_CATEGORIES,
    build_platform_daily_message,
    select_daily_platform_titles,
)


class DailyPlatformRotationTests(unittest.TestCase):
    def test_curated_catalogue_has_no_duplicate_titles(self):
        all_titles = [
            title
            for category_titles in TITLE_CATEGORIES.values()
            for title in category_titles
        ]
        self.assertEqual(len(all_titles), len(set(all_titles)))

    def test_platforms_receive_distinct_categories_and_titles(self):
        for offset in range(15):
            selected = select_daily_platform_titles(
                date(2026, 11, 20) + timedelta(days=offset)
            )
            self.assertEqual(
                len({item["category"] for item in selected.values()}), 3
            )
            self.assertEqual(
                len({item["title"] for item in selected.values()}), 3
            )

    def test_each_platform_changes_category_on_next_day(self):
        today = date(2026, 11, 20)
        tomorrow = today + timedelta(days=1)
        first = select_daily_platform_titles(today)
        second = select_daily_platform_titles(tomorrow)
        for platform in ("youtube", "facebook", "tiktok"):
            self.assertNotEqual(
                first[platform]["category"], second[platform]["category"]
            )

    def test_daily_briefs_keep_platform_duration_contracts(self):
        expected = {
            "youtube": ("၄၆–၆၀ မိနစ်", "၃ ပိုင်းတိတိ"),
            "facebook": ("၄၆–၆၀ မိနစ်", "၃ ပိုင်းတိတိ"),
            "tiktok": ("၄–၇ မိနစ်", "တစ်ပုဒ်တည်း"),
        }
        for platform, (duration, structure) in expected.items():
            item = {"title": "Test title", "category": "Test category"}
            message = build_platform_daily_message(
                platform, item, "Research notes", "", ""
            )
            self.assertIn(duration, message)
            self.assertIn(structure, message)


if __name__ == "__main__":
    unittest.main()
