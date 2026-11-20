import unittest
from unittest.mock import patch

import bangumi_episode_research as bangumi


def _subject(subject_id=100, name="Sample Anime", name_cn="サンプル"):
    return {"id": subject_id, "type": 2, "nsfw": False, "name": name, "name_cn": name_cn}


class BangumiEpisodeResearchTests(unittest.TestCase):
    def test_exact_subject_and_main_story_episode_metadata(self):
        search = {"data": [_subject()]}
        episodes = {"data": [
            {"id": 501, "type": 0, "ep": 1, "sort": 1, "name": "First", "name_cn": "အပိုင်း ၁",
             "airdate": "2024-01-01", "desc": "Verified community episode description."},
            {"id": 502, "type": 2, "ep": None, "sort": 1, "name": "Opening", "name_cn": "OP",
             "airdate": "", "desc": ""},
            {"id": 503, "type": 0, "ep": 2, "sort": 2, "name": "Second", "name_cn": "",
             "airdate": "2024-01-08", "desc": ""},
        ]}
        with patch.object(bangumi, "_post_json", return_value=search), patch.object(
            bangumi, "_get_json", return_value=episodes
        ):
            result = bangumi.fetch_bangumi_episode_summaries("Sample Anime")
        self.assertTrue(result["found"])
        self.assertEqual([e["number"] for e in result["episodes"]], [1, 2])
        self.assertEqual(result["episodes"][0]["summary_excerpt"], "Verified community episode description.")
        self.assertNotIn("summary_excerpt", result["episodes"][1])
        self.assertIn("/ep/501", result["episodes"][0]["source"])

    def test_rejects_ambiguous_exact_subjects(self):
        with patch.object(bangumi, "_post_json", return_value={"data": [
            _subject(100), _subject(101)
        ]}):
            result = bangumi.fetch_bangumi_episode_summaries("Sample Anime")
        self.assertFalse(result["found"])
        self.assertIn("တစ်ခုတည်း", result["status"])

    def test_rejects_fuzzy_subject(self):
        with patch.object(bangumi, "_post_json", return_value={"data": [
            _subject(name="Sample Anime Special", name_cn="Special")
        ]}):
            result = bangumi.fetch_bangumi_episode_summaries("Sample Anime")
        self.assertFalse(result["found"])

    def test_rejects_non_animation_subject(self):
        with patch.object(bangumi, "_post_json", return_value={"data": [
            {**_subject(), "type": 6}
        ]}):
            result = bangumi.fetch_bangumi_episode_summaries("Sample Anime")
        self.assertFalse(result["found"])

    def test_invalid_title(self):
        self.assertFalse(bangumi.fetch_bangumi_episode_summaries("")["found"])


if __name__ == "__main__":
    unittest.main()
