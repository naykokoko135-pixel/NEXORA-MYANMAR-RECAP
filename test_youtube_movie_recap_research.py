import json
from unittest.mock import patch

from youtube_movie_recap_research import (
    YouTubeRecapResearchError, search_youtube_movie_recaps,
)


def _response(payload):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, _limit): return json.dumps(payload).encode()
    return Response()


def test_requires_api_key():
    with patch.dict("os.environ", {}, clear=True):
        try:
            search_youtube_movie_recaps("Parasite")
        except YouTubeRecapResearchError as exc:
            assert "YOUTUBE_DATA_API_KEY" in str(exc)
        else:
            assert False


def test_keeps_relevant_recap_and_rejects_unrelated_results():
    search = {"items": [
        {"id": {"videoId": "good"}, "snippet": {"title": "Parasite Movie Recap",
         "channelTitle": "Film Recaps", "description": "Parasite movie recap explained",
         "publishedAt": "2026-01-01T00:00:00Z"}},
        {"id": {"videoId": "bad"}, "snippet": {"title": "Parasite Fortnite Skin Ranking",
         "channelTitle": "Gaming", "description": "gameplay battle pass"}},
    ]}
    details = {"items": [
        {"id": "good", "snippet": search["items"][0]["snippet"],
         "statistics": {"viewCount": "1200"}, "contentDetails": {"duration": "PT12M"},
         "status": {"privacyStatus": "public"}},
        {"id": "bad", "snippet": search["items"][1]["snippet"],
         "statistics": {"viewCount": "900000"}, "contentDetails": {},
         "status": {"privacyStatus": "public"}},
    ]}
    with patch("youtube_movie_recap_research.urllib.request.urlopen",
               side_effect=[_response(search), _response(details)]):
        result = search_youtube_movie_recaps("Parasite", api_key="test")
    assert len(result) == 1
    assert result[0]["channel"] == "Film Recaps"
    assert result[0]["footage_reuse_allowed"] is False
