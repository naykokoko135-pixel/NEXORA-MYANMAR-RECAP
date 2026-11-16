import unittest

from research_draft import matching_cached_research


class CachedResearchTests(unittest.TestCase):
    def test_returns_research_for_same_title(self):
        notes = "Auto Research: Avatar\nSource: https://example.org"
        self.assertEqual(matching_cached_research("Avatar", "Avatar", notes), notes)

    def test_title_matching_ignores_case_and_extra_spaces(self):
        notes = "Research result"
        self.assertEqual(matching_cached_research("  AVATAR ", "Avatar", notes), notes)

    def test_does_not_reuse_research_for_a_different_title(self):
        self.assertIsNone(matching_cached_research("Avatar 2", "Avatar", "Research result"))

    def test_does_not_reuse_empty_or_missing_results(self):
        self.assertIsNone(matching_cached_research("Avatar", "Avatar", " "))
        self.assertIsNone(matching_cached_research("Avatar", "", "Research result"))

    def test_does_not_reuse_no_match_result(self):
        self.assertIsNone(matching_cached_research(
            "Unknown Film", "Unknown Film",
            "ကိုက်ညီသော Wikipedia ဆောင်းပါး မတွေ့ပါ။"
        ))


if __name__ == "__main__":
    unittest.main()
