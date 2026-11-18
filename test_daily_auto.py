import unittest
from datetime import date

from daily_auto import (
    MOVIE_ROTATION, TITLE_CATEGORIES, build_daily_message, category_for_title,
    region_for_title, select_daily_movie, split_telegram_text,
)


class DailyAutoTests(unittest.TestCase):
    def test_selection_is_stable_for_same_day(self):
        day = date(2026, 11, 17)
        self.assertEqual(select_daily_movie(day), select_daily_movie(day))

    def test_selection_rotates_on_next_day(self):
        self.assertNotEqual(select_daily_movie(date(2026, 11, 17)), select_daily_movie(date(2026, 11, 18)))

    def test_pororo_is_classified_as_3d_animation(self):
        self.assertEqual(category_for_title("Pororo the Little Penguin"), "3D Animation")

    def test_selection_uses_catalog(self):
        self.assertIn(select_daily_movie(date(2026, 11, 17)), MOVIE_ROTATION)

    def test_all_four_animation_categories_have_titles(self):
        self.assertEqual(set(TITLE_CATEGORIES), {"Anime", "3D Animation", "Cartoon", "Donghua"})
        self.assertTrue(all(TITLE_CATEGORIES.values()))

    def test_international_titles_and_regions_are_included(self):
        self.assertIn("Klaus", MOVIE_ROTATION)
        self.assertEqual(region_for_title("Klaus"), "Spain")
        self.assertEqual(region_for_title("Ne Zha"), "China")
        self.assertEqual(region_for_title("Masha and the Bear"), "Russia")
        self.assertEqual(region_for_title("Motu Patlu"), "India")

    def test_message_contains_three_youtube_parts(self):
        result = build_daily_message("Avatar", "Research leads")
        self.assertIn("Part 1", result)
        self.assertIn("Part 2", result)
        self.assertIn("Part 3", result)
        self.assertIn("ဇာတ်ညွှန်းအပြည့်", result)
        self.assertIn("လူကြိုက်များမှု (Popularity)", result)
        self.assertIn("ဇာတ်လမ်းအရ အကောင်းဆုံးဖြစ်မှု", result)
        self.assertIn("အချက်အလက်မရရှိ", result)

    def test_long_message_is_split(self):
        chunks = split_telegram_text("x" * 8000)
        self.assertEqual("".join(chunks), "x" * 8000)
        self.assertTrue(all(len(chunk) <= 3900 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
