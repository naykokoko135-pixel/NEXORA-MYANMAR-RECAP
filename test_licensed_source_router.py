from pathlib import Path
from unittest.mock import patch

from licensed_source_router import (
    LicensedSourceRouterError,
    discover_and_download_licensed_source,
)


def test_commons_is_preferred_when_exact_title_source_downloads(tmp_path):
    source = {"title": "File:Exact Film.mp4", "mime": "video/mp4"}
    expected = tmp_path / "licensed_source.mp4"
    with (
        patch("clip_source_finder.search_licensed_video", return_value=[source]),
        patch("licensed_video_pipeline.download_licensed_source", return_value=expected),
    ):
        path, selected, provider = discover_and_download_licensed_source("Exact Film", tmp_path)
    assert path == expected
    assert selected is source
    assert provider == "Wikimedia Commons"


def test_archive_fallback_only_uses_download_enabled_cc0_or_public_domain(tmp_path):
    cc_by = {"title": "Exact Film", "license": "CC BY 4.0", "download_enabled": False}
    pd = {
        "title": "Exact Film",
        "license": "Public Domain Mark",
        "license_uri": "https://creativecommons.org/publicdomain/mark/1.0/",
        "download_enabled": True,
    }
    expected = tmp_path / "archive_movie.mp4"
    with (
        patch("clip_source_finder.search_licensed_video", return_value=[]),
        patch("internet_archive_video_finder.search_internet_archive_licensed_video", return_value=[cc_by, pd]),
        patch("internet_archive_pipeline.download_internet_archive_source", return_value=expected),
    ):
        path, selected, provider = discover_and_download_licensed_source("Exact Film", tmp_path)
    assert path == expected
    assert selected is pd
    assert provider == "Internet Archive (CC0/Public Domain Mark)"


def test_no_archive_auto_download_for_cc_by_only_records(tmp_path):
    cc_by = {"title": "Exact Film", "license": "CC BY 4.0", "download_enabled": False}
    with (
        patch("clip_source_finder.search_licensed_video", return_value=[]),
        patch("internet_archive_video_finder.search_internet_archive_licensed_video", return_value=[cc_by]),
        patch("internet_archive_pipeline.download_internet_archive_source") as download,
    ):
        try:
            discover_and_download_licensed_source("Exact Film", tmp_path)
        except LicensedSourceRouterError as exc:
            assert "CC0/Public Domain Mark" in str(exc)
        else:
            raise AssertionError("Expected safe source router to reject CC BY auto-download")
    download.assert_not_called()


def test_commons_download_failure_falls_back_to_archive(tmp_path):
    source = {"title": "File:Exact Film.mp4", "mime": "video/mp4"}
    pd = {
        "title": "Exact Film",
        "license": "CC0",
        "license_uri": "https://creativecommons.org/publicdomain/zero/1.0/",
        "download_enabled": True,
    }
    expected = tmp_path / "archive_movie.mp4"
    with (
        patch("clip_source_finder.search_licensed_video", return_value=[source]),
        patch("licensed_video_pipeline.download_licensed_source", side_effect=RuntimeError("CDN blocked")),
        patch("internet_archive_video_finder.search_internet_archive_licensed_video", return_value=[pd]),
        patch("internet_archive_pipeline.download_internet_archive_source", return_value=expected),
    ):
        path, selected, provider = discover_and_download_licensed_source("Exact Film", tmp_path)
    assert path == expected
    assert selected is pd
    assert provider.startswith("Internet Archive")


def test_no_provider_match_returns_diagnostics(tmp_path):
    with (
        patch("clip_source_finder.search_licensed_video", return_value=[]),
        patch("internet_archive_video_finder.search_internet_archive_licensed_video", return_value=[]),
    ):
        try:
            discover_and_download_licensed_source("Missing Film", tmp_path)
        except LicensedSourceRouterError as exc:
            assert "Commons" in str(exc)
            assert "Internet Archive" in str(exc)
        else:
            raise AssertionError("Expected no-match error")
