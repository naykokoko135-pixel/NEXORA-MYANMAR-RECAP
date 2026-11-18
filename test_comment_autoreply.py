import unittest

from comment_autoreply import build_reply, classify_comment, platform_comment_capabilities, run_comment_autoreply_cycle


class CommentReplyTests(unittest.TestCase):
    def test_short_positive_myanmar_comment_is_safe(self):
        self.assertEqual(classify_comment("အရမ်းကောင်းတယ်"), "auto_safe")
        self.assertIn("ကျေးဇူးတင်ပါတယ်", build_reply("အရမ်းကောင်းတယ်"))

    def test_short_positive_english_comment_is_safe(self):
        self.assertEqual(classify_comment("Thanks!"), "auto_safe")
        self.assertIn("Thanks for watching", build_reply("Thanks!"))

    def test_questions_and_complaints_require_review(self):
        for value in ("When is the next video?", "မကောင်းဘူး", "ဒီဇာတ်ကားဘယ်လိုလဲ", "not good", "great video but bad audio"):
            self.assertEqual(classify_comment(value), "review")
            self.assertIsNone(build_reply(value))

    def test_contact_details_and_long_comments_require_review(self):
        self.assertEqual(classify_comment("Thanks, email me at a.person@example.com"), "review")
        self.assertEqual(classify_comment("great " * 40), "review")

    def test_emoji_only_comment_is_safe(self):
        self.assertEqual(classify_comment("❤️👍🙏"), "auto_safe")

    def test_autoreply_is_disabled_by_default(self):
        result = run_comment_autoreply_cycle({})
        self.assertFalse(result["enabled"])
        self.assertEqual(result["youtube_sent"], 0)
        self.assertEqual(result["facebook_sent"], 0)

    def test_tiktok_is_draft_only(self):
        capabilities = platform_comment_capabilities()
        self.assertIn("draft-only", capabilities["tiktok"])


if __name__ == "__main__":
    unittest.main()
