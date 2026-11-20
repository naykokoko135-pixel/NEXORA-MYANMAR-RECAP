import json
from unittest.mock import patch

from youtube_cc_finder import YouTubeCCSearchError, search_youtube_cc_videos


def _response(payload):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, _limit):
            return json.dumps(payload).encode("utf-8")
    return Response()


def test_requires_api_key():
    with patch.dict("os.environ", {}, clear=True):
        try:
            search_youtube_cc_videos("sample")
        except YouTubeCCSearchError as exc:
            assert "YOUTUBE_DATA_API_KEY" in str(exc)
        else:
            assert False, "expected missing API key error"


def test_returns_only_public_cc_videos_and_never_download_url():
    search = {"items": [
        {"id": {"videoId": "abc123"}, "snippet": {
            "title": "Licensed nature footage", "channelTitle": "Creator",
            "publishedAt": "2025-01-01T00:00:00Z"
        }},
        {"id": {"videoId": "bad456"}, "snippet": {"title": "Restricted"}},
    ]}
    details = {"items": [
        {"id": "abc123", "snippet": search["items"][0]["snippet"],
         "status": {"license": "creativeCommon", "privacyStatus": "public",
                    "uploadStatus": "processed", "embeddable": True}},
        {"id": "bad456", "status": {"license": "youtube", "privacyStatus": "public",
                                    "uploadStatus": "processed"}},
    ]}
    with patch("youtube_cc_finder.urllib.request.urlopen",
               side_effect=[_response(search), _response(details)]):
        result = search_youtube_cc_videos("nature", api_key="test-key")
    assert len(result) == 1
    assert result[0]["source"] == "YouTube"
    assert result[0]["license"] == "Creative Commons Attribution (CC BY)"
    assert result[0]["url"] == "https://www.youtube.com/watch?v=abc123"
    assert result[0]["download_enabled"] is False
    assert result[0]["reuse_ready"] is False
    assert "stream" not in result[0]


def test_rejects_invalid_title():
    try:
        search_youtube_cc_videos(" " * 2, api_key="test-key")
    except YouTubeCCSearchError:
        return
    assert False, "expected invalid query error"


def test_filters_non_public_video():
    search = {"items": [{"id": {"videoId": "private1"}, "snippet": {}}]}
    details = {"items": [{"id": "private1", "status": {
        "license": "creativeCommon", "privacyStatus": "private",
        "uploadStatus": "processed"
    }}]}
    with patch("youtube_cc_finder.urllib.request.urlopen",
               side_effect=[_response(search), _response(details)]):
        result = search_youtube_cc_videos("test", api_key="test-key")
    assert result == []
