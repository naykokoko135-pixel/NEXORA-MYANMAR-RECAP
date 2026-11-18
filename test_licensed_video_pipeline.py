from licensed_video_pipeline import choose_matching_source


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
