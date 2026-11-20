"""Tests for cross-format multi-source research."""
import multi_source_research as research
import tmdb_movie_research
import tvmaze_synopsis


def test_universal_research_queries_anime_movie_and_tv_independently(monkeypatch):
    monkeypatch.setattr(research, "research_anime_sources", lambda title: {
        "title": title, "anilist": {"found": True}, "tenrai": {"found": False},
        "wikidata": {"found": True},
    })
    monkeypatch.setattr(tmdb_movie_research, "research_movie_sources", lambda title: {
        "title": title, "tmdb": {"found": True}, "wikidata": {"found": True},
        "gemini": {"found": False},
    })
    monkeypatch.setattr(tvmaze_synopsis, "fetch_tvmaze_synopsis", lambda title: {
        "found": True, "title": title, "country": "Japan", "genres": ["Animation"],
        "summary": "A test series overview long enough to be useful.",
    })

    report = research.research_all_media_sources("Example Title")

    assert report["anime"]["anilist"]["found"] is True
    assert report["movie"]["tmdb"]["found"] is True
    assert report["series"]["found"] is True


def test_universal_research_keeps_other_tracks_when_one_provider_fails(monkeypatch):
    def broken(_title):
        raise RuntimeError("provider offline")

    monkeypatch.setattr(research, "research_anime_sources", broken)
    monkeypatch.setattr(tmdb_movie_research, "research_movie_sources", lambda title: {
        "title": title, "tmdb": {"found": True}, "wikidata": {"found": False},
        "gemini": {"found": False},
    })
    monkeypatch.setattr(tvmaze_synopsis, "fetch_tvmaze_synopsis", lambda _title: {
        "found": False, "status": "not found",
    })

    report = research.research_all_media_sources("Example Title")

    assert report["anime"]["found"] is False
    assert report["movie"]["tmdb"]["found"] is True
    assert report["series"]["found"] is False


def test_universal_report_labels_all_media_categories():
    report = {
        "title": "Example",
        "anime": {"title": "Example", "anilist": {}, "tenrai": {}, "wikidata": {}},
        "movie": {"title": "Example", "tmdb": {}, "wikidata": {}, "gemini": {}},
        "series": {"found": False, "status": "No TV series match"},
    }
    output = research.format_all_media_source_report(report)
    assert "ANIME / ANIMATION" in output
    assert "MOVIE / FILM" in output
    assert "TV SERIES" in output
