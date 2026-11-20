import unittest

from subtitle_builder import build_burmese_srt


class BurmeseSubtitleTests(unittest.TestCase):
    def test_builds_sequential_burmese_srt(self):
        result = build_burmese_srt("ဒီနေ့ ဇာတ်လမ်းကို စတင်ကြည့်ကြရအောင်။\nအဓိကဇာတ်ကောင်က ခရီးတစ်ခုကို စတင်ခဲ့ပါတယ်။")
        self.assertIn("00:00:00,000 -->", result)
        self.assertIn("ဒီနေ့", result)
        self.assertIn("အဓိကဇာတ်ကောင်", result)
        self.assertTrue(result.endswith("\n"))

    def test_splits_long_text(self):
        result = build_burmese_srt("ဇာတ်လမ်းအကြောင်း " * 20)
        self.assertGreater(result.count("-->"), 1)
        captions = [line for line in result.splitlines() if line and not line.isdigit() and "-->" not in line]
        self.assertTrue(all(len(line) <= 42 for line in captions))

    def test_empty_script_rejected(self):
        with self.assertRaises(ValueError):
            build_burmese_srt("   ")

    def test_long_form_script_subtitles_support_45_minute_narration(self):
        result = build_burmese_srt("ဇာတ်လမ်းအကြောင်း " * 4000)
        self.assertIn("-->", result)

    def test_invalid_reading_speed_rejected(self):
        with self.assertRaises(ValueError):
            build_burmese_srt("စမ်းသပ်စာသား", chars_per_second=30)


if __name__ == "__main__":
    unittest.main()
