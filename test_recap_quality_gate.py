import unittest

from recap_quality_gate import analyze_recap_script, format_recap_qa_report


GOOD_SCRIPT = """Opening Hook
ဒီဇာတ်လမ်းမှာ ဘာတွေဖြစ်လာမလဲ။

ဇာတ်လမ်း
အဓိကဖြစ်ရပ်များကို ကိုယ်ပိုင်စကားဖြင့် ရှင်းပြထားသည်။

အလှည့်အပြောင်း
ဇာတ်ကောင်၏ ဆုံးဖြတ်ချက်ကြောင့် အခြေအနေပြောင်းသွားသည်။

Climax နှင့် အဆုံးသတ်
ဇာတ်လမ်း၏ ရလဒ်ကို ရှင်းပြထားသည်။

ကိုယ်ပိုင်သုံးသပ်ချက်
ကျွန်ုပ်၏ အမြင်ကို ထည့်ထားသည်။ https://example.org/source

Footage အတွက် လိုင်စင်နှင့် ခွင့်ပြုချက်ကို စစ်ဆေးထားသည်။
"""


class RecapQualityGateTests(unittest.TestCase):
    def test_complete_script_reports_review_not_verified(self):
        report = analyze_recap_script("Anime", "Sample Anime", GOOD_SCRIPT)
        self.assertEqual(report["status"], "READY FOR HUMAN REVIEW")
        self.assertEqual(report["issues"], [])
        self.assertIn("ဇာတ်လမ်းမှန်ကန်မှု", report["disclaimer"])

    def test_unknown_category_is_flagged(self):
        report = analyze_recap_script("Indian Movies", "Sample", GOOD_SCRIPT)
        self.assertTrue(any("အမျိုးအစား" in item for item in report["issues"]))

    def test_excluded_titles_are_not_ready(self):
        report = analyze_recap_script("Cartoon", "Motu Patlu", GOOD_SCRIPT)
        self.assertEqual(report["status"], "NOT READY")

    def test_missing_sources_and_sections_are_flagged(self):
        report = analyze_recap_script("Donghua", "Sample", "စာတို")
        self.assertTrue(any("URL" in item for item in report["issues"]))
        self.assertTrue(any("အပိုင်းများ" in item for item in report["issues"]))

    def test_duplicate_paragraphs_are_flagged(self):
        repeated = GOOD_SCRIPT + "\n\n" + GOOD_SCRIPT.split("\n\n")[0]
        report = analyze_recap_script("Anime", "Sample", repeated)
        self.assertTrue(any("ထပ်နေသည်" in item for item in report["issues"]))

    def test_report_formatter(self):
        report = analyze_recap_script("Anime", "Sample", GOOD_SCRIPT)
        formatted = format_recap_qa_report(report)
        self.assertIn("NEXORA RECAP EDITORIAL QA", formatted)
        self.assertIn("READY FOR HUMAN REVIEW", formatted)


if __name__ == "__main__":
    unittest.main()
