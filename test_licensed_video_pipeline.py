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


def test_narrated_renderer_rejects_non_reusable_license_before_network():
    import pytest
    from licensed_narrated_clip import render_licensed_narrated_preview
    from licensed_video_pipeline import LicensedClipError

    with pytest.raises(LicensedClipError):
        render_licensed_narrated_preview(
            {"license": "CC BY-NC 4.0", "url": "https://upload.wikimedia.org/example.webm"},
            b"fake-mp3",
            "1\\n00:00:00,000 --> 00:00:01,000\\nမင်္ဂလာပါ\\n",
            "unused.mp4",
        )


def test_narrated_renderer_rejects_invalid_srt_before_network():
    import pytest
    from licensed_narrated_clip import render_licensed_narrated_preview
    from licensed_video_pipeline import LicensedClipError

    with pytest.raises(LicensedClipError):
        render_licensed_narrated_preview(
            {"license": "CC BY 4.0", "url": "https://upload.wikimedia.org/example.webm"},
            b"fake-mp3",
            "caption without timestamps",
            "unused.mp4",
        )



def test_verified_alternate_title_can_match_commons_filename():
    sources = [{"title": "File:Sousou no Frieren promotional video.webm"}]
    assert choose_matching_source(
        "Frieren: Beyond Journey's End",
        sources,
        alternate_titles=["Sousou no Frieren"],
    ) is sources[0]


def test_short_or_unrelated_alias_does_not_weaken_matching():
    sources = [{"title": "File:Frieren unrelated compilation.webm"}]
    assert choose_matching_source(
        "Frieren: Beyond Journey's End",
        sources,
        alternate_titles=["Frieren"],
    ) is None
