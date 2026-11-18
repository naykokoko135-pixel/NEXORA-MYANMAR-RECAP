import json
from unittest.mock import patch

from clip_source_finder import ClipSourceError, search_licensed_video


def _response(payload):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, _limit):
            return json.dumps(payload).encode("utf-8")
    return Response()


def test_returns_only_video_with_allowed_license():
    payload = {"query": {"pages": {
        "1": {"title": "File:licensed.webm", "canonicalurl": "https://commons.wikimedia.org/wiki/File:licensed.webm",
              "imageinfo": [{"mime": "video/webm", "url": "https://upload.wikimedia.org/licensed.webm",
                             "size": 123, "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"},
                             "UsageTerms": {"value": "Attribution required"}, "Artist": {"value": "Creator"}}}]},
        "2": {"title": "File:restricted.mp4", "imageinfo": [{"mime": "video/mp4", "url": "https://example.com/x",
                             "extmetadata": {"LicenseShortName": {"value": "All rights reserved"}}}]},
        "3": {"title": "File:still.jpg", "imageinfo": [{"mime": "image/jpeg", "url": "https://example.com/y",
                             "extmetadata": {"LicenseShortName": {"value": "CC0"}}}]},
    }}}
    with patch("clip_source_finder.urllib.request.urlopen", return_value=_response(payload)):
        result = search_licensed_video("test anime")
    assert len(result) == 1
    assert result[0]["license"] == "CC BY-SA 4.0"
    assert result[0]["artist"] == "Creator"


def test_rejects_empty_query():
    try:
        search_licensed_video(" ")
    except ClipSourceError:
        return
    assert False, "expected ClipSourceError"


def test_network_error_is_safe_message():
    with patch("clip_source_finder.urllib.request.urlopen", side_effect=OSError("offline")):
        try:
            search_licensed_video("sample")
        except ClipSourceError as exc:
            assert "ရှာမရပါ" in str(exc)
        else:
            assert False, "expected ClipSourceError"



def test_searches_verified_alternate_title_when_primary_has_no_result():
    primary = _response({"query": {"pages": {}}})
    alias = _response({"query": {"pages": {
        "7": {"title": "File:Frieren Beyond Journey End.webm",
              "canonicalurl": "https://commons.wikimedia.org/wiki/File:Frieren_Beyond_Journey_End.webm",
              "imageinfo": [{"mime": "video/webm",
                             "url": "https://upload.wikimedia.org/alias.webm",
                             "size": 456,
                             "extmetadata": {"LicenseShortName": {"value": "CC BY 4.0"}}}]}
    }}})
    with patch("clip_source_finder.urllib.request.urlopen", side_effect=[primary, alias]) as mocked:
        result = search_licensed_video("Frieren: Beyond Journey's End", alternate_queries=["Sousou no Frieren"])
    assert mocked.call_count == 2
    assert len(result) == 1
    assert result[0]["license"] == "CC BY 4.0"
