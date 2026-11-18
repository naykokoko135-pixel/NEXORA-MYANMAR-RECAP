from licensed_video_pipeline import choose_matching_source
from clip_source_finder import LICENSE_PATTERN


def test_choose_requires_strong_title_match():
    sources = [
        {"title": "File:Unrelated animation.webm"},
        {"title": "File:Frieren Beyond Journey End trailer.webm", "license": "CC BY-SA"},
    ]
    selected = choose_matching_source("Frieren Beyond Journey's End", sources)
    assert selected is sources[1]


def test_no_weak_title_match():
    assert choose_matching_source("Frieren Beyond Journey's End", [
        {"title": "File:Anime compilation.webm"}
    ]) is None


def test_license_filter_accepts_only_reusable_license_families():
    assert LICENSE_PATTERN.match("CC0 1.0")
    assert LICENSE_PATTERN.match("CC BY 4.0")
    assert LICENSE_PATTERN.match("CC BY-SA 4.0")
    assert LICENSE_PATTERN.match("Public domain")
    assert not LICENSE_PATTERN.match("CC BY-NC 4.0")
    assert not LICENSE_PATTERN.match("CC BY-ND 4.0")
    assert not LICENSE_PATTERN.match("CC BY-NC-SA 4.0")
