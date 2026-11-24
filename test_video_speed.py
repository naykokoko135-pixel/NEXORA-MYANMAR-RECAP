import pytest

from video_speed import (
    build_video_speed_filter,
    normalize_video_speed,
    required_source_duration,
)


@pytest.mark.parametrize("raw, expected", [
    ("0.5", 0.5),
    ("0.75x", 0.75),
    ("1", 1.0),
    ("1.25", 1.25),
    ("2x", 2.0),
])
def test_normalize_video_speed(raw, expected):
    assert normalize_video_speed(raw) == expected


def test_speed_filter_changes_video_only():
    assert build_video_speed_filter(1.0) == ""
    assert build_video_speed_filter(0.5) == "setpts=PTS/0.5000"
    assert build_video_speed_filter(2.0) == "setpts=PTS/2.0000"


def test_source_coverage_scales_with_playback_speed():
    assert required_source_duration(20, 0.5) == 10
    assert required_source_duration(20, 1.0) == 20
    assert required_source_duration(20, 2.0) == 40


@pytest.mark.parametrize("raw", ["0.1", "2.5", "fast", "", None])
def test_reject_invalid_speed(raw):
    with pytest.raises(ValueError):
        normalize_video_speed(raw)
