import json
from unittest.mock import patch

from internet_archive_video_finder import (
    ALLOWED_LICENSES,
    InternetArchiveSearchError,
    search_internet_archive_licensed_video,
)


def _response(payload):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, _limit):
            return json.dumps(payload).encode("utf-8")
    return Response()


def test_returns_exact_title_explicit_cc_movie_as_discovery_only():
    search = {"response": {"docs": [{"identifier": "open-film-123", "title": "Open Film (2020)"}]}}
    metadata = {
        "metadata": {
            "title": "Open Film (2020)", "mediatype": "movies",
            "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
            "creator": "Uploader", "runtime": "00:48:00",
        },
        "files": [
            {"name": "open-film.mp4", "source": "original", "format": "MPEG4", "size": "1000000", "length": "2880"},
            {"name": "__ia_thumb.jpg", "source": "derivative", "format": "JPEG", "size": "100"},
        ],
    }
    with patch("internet_archive_video_finder.urllib.request.urlopen",
               side_effect=[_response(search), _response(metadata)]):
        result = search_internet_archive_licensed_video("Open Film")
    assert len(result) == 1
    assert result[0]["license"] == "CC BY 4.0"
    assert result[0]["runtime_seconds"] == 2880
    assert result[0]["files"][0]["name"] == "open-film.mp4"
    assert result[0]["download_enabled"] is False
    assert result[0]["reuse_ready"] is False
    assert "uploader" in result[0]["notice"].lower()


def test_rejects_unlicensed_or_non_reusable_item():
    search = {"response": {"docs": [{"identifier": "restricted-123", "title": "Restricted Film"}]}}
    metadata = {
        "metadata": {
            "title": "Restricted Film", "mediatype": "movies",
            "licenseurl": "https://creativecommons.org/licenses/by-nc/4.0/",
        },
        "files": [{"name": "film.mp4", "source": "original", "size": "100"}],
    }
    with patch("internet_archive_video_finder.urllib.request.urlopen",
               side_effect=[_response(search), _response(metadata)]):
        assert search_internet_archive_licensed_video("Restricted Film") == []


def test_requires_exact_title_match():
    search = {"response": {"docs": [{"identifier": "same-name-123", "title": "Open Film Trailer"}]}}
    metadata = {
        "metadata": {
            "title": "Open Film Trailer", "mediatype": "movies",
            "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
        },
        "files": [{"name": "film.mp4", "source": "original", "size": "100"}],
    }
    with patch("internet_archive_video_finder.urllib.request.urlopen",
               side_effect=[_response(search), _response(metadata)]):
        assert search_internet_archive_licensed_video("Open Film") == []


def test_skips_items_without_original_video_file_or_with_oversize_file():
    search = {"response": {"docs": [{"identifier": "large-video-123", "title": "Open Film"}]}}
    metadata = {
        "metadata": {
            "title": "Open Film", "mediatype": "movies",
            "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
        },
        "files": [
            {"name": "large.mp4", "source": "original", "size": str(2 * 1024**3)},
            {"name": "derivative.mp4", "source": "derivative", "size": "100"},
        ],
    }
    with patch("internet_archive_video_finder.urllib.request.urlopen",
               side_effect=[_response(search), _response(metadata)]):
        assert search_internet_archive_licensed_video("Open Film") == []


def test_license_allowlist_excludes_nc_nd():
    assert "https://creativecommons.org/licenses/by/4.0/" in ALLOWED_LICENSES
    assert "https://creativecommons.org/licenses/by-sa/4.0/" in ALLOWED_LICENSES
    assert "https://creativecommons.org/licenses/by-nc/4.0/" not in ALLOWED_LICENSES
    assert "https://creativecommons.org/licenses/by-nd/4.0/" not in ALLOWED_LICENSES


def test_invalid_query_rejected():
    try:
        search_internet_archive_licensed_video(" ")
    except InternetArchiveSearchError:
        return
    assert False, "expected invalid query error"
