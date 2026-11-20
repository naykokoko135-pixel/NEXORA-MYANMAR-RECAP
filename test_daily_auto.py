import unittest
from datetime import date

from daily_auto import (
    MOVIE_ROTATION, TITLE_CATEGORIES, build_daily_message, category_for_title,
    region_for_title, format_for_title, select_daily_movie, split_telegram_text,
    select_daily_platform_titles, build_platform_daily_message,
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

    def test_all_four_animation_categories_and_movie_category_have_titles(self):
        self.assertEqual(set(TITLE_CATEGORIES), {"Anime", "3D Animation", "Cartoon", "Donghua", "International Movies"})
        self.assertTrue(all(TITLE_CATEGORIES.values()))

    def test_international_titles_and_regions_are_included(self):
        self.assertIn("Klaus", MOVIE_ROTATION)
        self.assertEqual(region_for_title("Klaus"), "Spain")
        self.assertEqual(region_for_title("Ne Zha"), "China")
        self.assertEqual(region_for_title("Masha and the Bear"), "Russia")
        self.assertNotIn("Motu Patlu", MOVIE_ROTATION)
        self.assertNotIn("Chhota Bheem", MOVIE_ROTATION)
        self.assertFalse(any(region_for_title(title) == "India" for title in MOVIE_ROTATION))
        self.assertIn("Train to Busan", TITLE_CATEGORIES["International Movies"])
        self.assertNotIn("Train to Busan", TITLE_CATEGORIES["3D Animation"])
        self.assertEqual(category_for_title("Train to Busan"), "International Movies")

    def test_media_format_distinguishes_series_and_animated_films(self):
        self.assertEqual(format_for_title("Frieren: Beyond Journey's End"), "Animated Series")
        self.assertEqual(format_for_title("Spirited Away"), "Animated Film")
        self.assertEqual(format_for_title("Ne Zha"), "Animated Film")

    def test_international_movies_are_live_action_only(self):
        for title in TITLE_CATEGORIES["International Movies"]:
            self.assertEqual(format_for_title(title), "Live-action Film")
        self.assertEqual(format_for_title("Spider-Man: Into the Spider-Verse"), "Animated Film")

    def test_unknown_media_format_is_not_guessed(self):
        self.assertIn("Official Source", format_for_title("Unknown New Title"))

    def test_daily_message_shows_media_format(self):
        result = build_daily_message("Train to Busan", "Research leads")
        self.assertIn("မီဒီယာပုံစံ: Live-action Film", result)

    def test_daily_message_includes_optional_series_episode_guide(self):
        result = build_daily_message(
            "Frieren: Beyond Journey's End", "Research leads",
            series_text="Season 1: 28 Episodes",
        )
        self.assertIn("Season 1: 28 Episodes", result)

    def test_daily_message_includes_optional_wikidata_metadata(self):
        result = build_daily_message("Train to Busan", "Wikipedia research", "Wikidata metadata cross-check")
        self.assertIn("Wikidata metadata cross-check", result)
        self.assertIn("International Movies", result)

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



    def test_daily_platform_selection_uses_three_distinct_categories(self):
        selected = select_daily_platform_titles(date(2026, 11, 20))
        self.assertEqual(set(selected), {"youtube", "facebook", "tiktok"})
        self.assertEqual(len({item["category"] for item in selected.values()}), 3)
        self.assertEqual(len({item["title"] for item in selected.values()}), 3)

    def test_daily_platform_selection_ranks_by_recent_pageviews(self):
        pageviews = {
            "categories": {
                "Anime": [{"title": "Frieren: Beyond Journey's End", "recent_views": 1000}],
                "3D Animation": [{"title": "Ne Zha", "recent_views": 900}],
                "Cartoon": [{"title": "Gravity Falls", "recent_views": 800}],
                "Donghua": [{"title": "Link Click", "recent_views": 700}],
                "International Movies": [{"title": "Train to Busan", "recent_views": 600}],
            }
        }
        selected = select_daily_platform_titles(date(2026, 11, 20), pageviews)
        self.assertEqual(selected["youtube"]["title"], "Frieren: Beyond Journey's End")
        self.assertEqual(selected["facebook"]["title"], "Ne Zha")
        self.assertEqual(selected["tiktok"]["title"], "Gravity Falls")

    def test_tiktok_daily_pack_has_cross_platform_follow_cta(self):
        import os
        from unittest.mock import patch
        item = {"title": "Link Click", "category": "Donghua", "recent_wikipedia_views": 100}
        with patch.dict(os.environ, {
            "YOUTUBE_CHANNEL_URL": "https://youtube.com/@nexora",
            "FACEBOOK_PAGE_URL": "https://facebook.com/nexora",
        }):
            result = build_platform_daily_message("tiktok", item, "Verified research")
        self.assertIn("YouTube ကို Subscribe", result)
        self.assertIn("Facebook Page ကို Follow", result)
        self.assertIn("https://youtube.com/@nexora", result)
        self.assertIn("https://facebook.com/nexora", result)

    def test_platform_daily_packs_have_different_format_and_duration(self):
        item = {"title": "Train to Busan", "category": "International Movies"}
        youtube = build_platform_daily_message("youtube", item, "Research")
        facebook = build_platform_daily_message("facebook", item, "Research")
        tiktok = build_platform_daily_message("tiktok", item, "Research")
        self.assertIn("၄၆–၆၀ မိနစ်", youtube)
        self.assertIn("၃ ပိုင်းတိတိ၊ တစ်ပိုင်း ၁၅–၂၀ မိနစ်", youtube)
        self.assertIn("၄၆–၆၀ မိနစ်", facebook)
        self.assertIn("၃ ပိုင်းတိတိ၊ တစ်ပိုင်း ၁၅–၂၀ မိနစ်", facebook)
        self.assertIn("၄–၇ မိနစ်", tiktok)
        self.assertIn("တစ်ပုဒ်တည်း", tiktok)

    def test_source_failure_returns_fallback_without_raising(self):
        from daily_auto import _source_or_fallback

        def unavailable_source():
            raise TimeoutError("temporary upstream timeout")

        self.assertEqual(
            _source_or_fallback("test source", unavailable_source, "fallback brief"),
            "fallback brief",
        )

    def test_source_success_returns_original_result(self):
        from daily_auto import _source_or_fallback

        self.assertEqual(
            _source_or_fallback("test source", lambda: {"found": True}, {}),
            {"found": True},
        )

if __name__ == "__main__":
    unittest.main()
