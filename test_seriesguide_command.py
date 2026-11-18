import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import seriesguide_command


class SeriesGuideCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_tvmaze_exact_match_is_primary_source(self):
        update = SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock()))
        context = SimpleNamespace(args=["Example", "Series"])
        with patch("seriesguide_command.fetch_series_episode_guide", return_value={"found": True}) as tvmaze, \
             patch("seriesguide_command.format_series_episode_guide", return_value="TVmaze guide") as format_tvmaze, \
             patch("seriesguide_command.fetch_wikidata_metadata") as wikidata:
            await seriesguide_command.series_guide_cmd(update, context)

        tvmaze.assert_called_once_with("Example Series")
        format_tvmaze.assert_called_once()
        anilist.assert_not_called()
        wikidata.assert_not_called()
        self.assertIn("TVmaze guide", [call.args[0] for call in update.message.reply_text.await_args_list])

    async def test_wikidata_is_used_only_when_tvmaze_has_no_exact_match(self):
        update = SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock()))
        context = SimpleNamespace(args=["Example", "Series"])
        with patch("seriesguide_command.fetch_series_episode_guide", return_value={
            "found": False, "status": "TVmaze exact title not found"
        }), patch("seriesguide_command.fetch_wikidata_metadata", return_value={"found": True}) as wikidata, \
             patch("seriesguide_command.format_wikidata_episode_guide", return_value="Wikidata totals"):
            await seriesguide_command.series_guide_cmd(update, context)

        anilist.assert_not_called()\n        wikidata.assert_called_once_with("Example Series")
        replies = [call.args[0] for call in update.message.reply_text.await_args_list]
        self.assertTrue(any("TVmaze exact title not found" in reply for reply in replies))
        self.assertTrue(any("Wikidata totals" in reply for reply in replies))


    async def test_anilist_is_used_for_curated_anime_after_tvmaze_miss(self):
        update = SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock()))
        context = SimpleNamespace(args=["Frieren:", "Beyond", "Journey's", "End"])
        with patch("seriesguide_command.fetch_series_episode_guide", return_value={
            "found": False, "status": "TVmaze no exact match"
        }), patch("seriesguide_command.fetch_anilist_episode_guide", return_value={
            "found": True, "episode_count": 28
        }) as anilist, patch("seriesguide_command.format_anilist_episode_guide",
                            return_value="AniList episodes: 28") as format_anilist, \\
             patch("seriesguide_command.fetch_wikidata_metadata") as wikidata:
            await seriesguide_command.series_guide_cmd(update, context)

        anilist.assert_called_once_with("Frieren: Beyond Journey's End")
        format_anilist.assert_called_once()
        wikidata.assert_not_called()
        replies = [call.args[0] for call in update.message.reply_text.await_args_list]
        self.assertTrue(any("AniList episodes: 28" in reply for reply in replies))

    async def test_missing_title_shows_usage_without_network_calls(self):
        update = SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock()))
        context = SimpleNamespace(args=[])
        with patch("seriesguide_command.fetch_series_episode_guide") as tvmaze:
            await seriesguide_command.series_guide_cmd(update, context)

        tvmaze.assert_not_called()
        update.message.reply_text.assert_awaited_once()
        self.assertIn("/seriesguide", update.message.reply_text.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
