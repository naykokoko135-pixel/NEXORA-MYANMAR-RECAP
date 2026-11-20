from recap_studio import build_original_recap_notes


def test_builds_original_notes_from_verified_metadata_and_trend_signals():
    report = {
        "title": "Example Film",
        "tmdb": {
            "found": True, "title": "Example Film", "year": "2020",
            "overview": "A person solves a mystery.",
            "provider_url": "https://www.themoviedb.org/movie/1",
            "countries": ["South Korea"],
        },
        "wikidata": {"found": False},
        "india_excluded": False,
    }
    examples = [{
        "channel": "Foreign Recap Channel", "title": "Example Film Movie Recap",
        "views": 100000, "published_at": "2026-01-01",
        "url": "https://youtube.com/watch?v=abc",
    }]
    notes = build_original_recap_notes(report, examples)
    assert "A person solves a mystery." in notes
    assert "views=100,000" in notes
    assert "never translate" in notes
    assert "footage" in notes.lower()


def test_rejects_indian_production():
    report = {
        "title": "Example", "tmdb": {"found": True},
        "wikidata": {"found": False}, "india_excluded": True,
    }
    try:
        build_original_recap_notes(report, [])
    except ValueError as exc:
        assert "အိန္ဒိယ" in str(exc)
    else:
        assert False


def test_requires_verified_catalogue_facts():
    report = {
        "title": "Unknown", "tmdb": {"found": False},
        "wikidata": {"found": False}, "india_excluded": False,
    }
    try:
        build_original_recap_notes(report, [])
    except ValueError as exc:
        assert "အတည်ပြု" in str(exc)
    else:
        assert False
