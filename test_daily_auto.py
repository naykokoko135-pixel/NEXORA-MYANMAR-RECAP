import unittest
from datetime import date

from daily_auto import MOVIE_ROTATION, build_daily_message, select_daily_movie, split_telegram_text


class DailyAutoTests(unittest.TestCase):
    def test_selection_is_stable_for_same_day(self):
        day = date(2026, 11, 17)
        self.assertEqual(select_daily_movie(day), select_daily_movie(day))

    def test_selection_rotates_on_next_day(self):
        self.assertNotEqual(select_daily_movie(date(2026, 11, 17)), select_daily_movie(date(2026, 11, 18)))

    def test_selection_uses_catalog(self):
        self.assertIn(select_daily_movie(date(2026, 11, 17)), MOVIE_ROTATION)

    def test_message_contains_three_youtube_parts(self):
        result = build_daily_message("Avatar", "Research leads")
        self.assertIn("Part 1", result)
        self.assertIn("Part 2", result)
        self.assertIn("Part 3", result)
        self.assertIn("ဇာတ်ညွှန်းအပြည့်", result)

    def test_long_message_is_split(self):
        chunks = split_telegram_text("x" * 8000)
        self.assertEqual("".join(chunks), "x" * 8000)
        self.assertTrue(all(len(chunk) <= 3900 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
