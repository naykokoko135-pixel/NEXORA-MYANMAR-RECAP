import unittest

from script_writer import classify_recap_title, generate_all_platform_plan


class TitleClassificationTests(unittest.TestCase):
    def test_pororo_is_south_korean_3d_childrens_animation(self):
        self.assertEqual(
            classify_recap_title("Pororo"),
            ("3D Animation / Children's Series", "South Korea"),
        )

    def test_chinese_title_is_donghua(self):
        self.assertEqual(classify_recap_title("Link Click"), ("Donghua", "China"))

    def test_unknown_title_is_not_guessed(self):
        category, region = classify_recap_title("An Unlisted Animation")
        self.assertIn("အတည်ပြုရန်", category)
        self.assertIn("အတည်ပြုရန်", region)

    def test_plan_shows_resolved_category(self):
        plan = generate_all_platform_plan("Pororo")
        self.assertIn("3D Animation / Children's Series", plan)
        self.assertIn("South Korea", plan)
        self.assertNotIn("Anime / 3D Animation / Cartoon / Donghua", plan)


if __name__ == "__main__":
    unittest.main()
