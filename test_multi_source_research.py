"""Tests for independent anime metadata provider failure handling."""
import multi_source_research as research


def test_provider_exception_does_not_discard_other_results(monkeypatch):
    monkeypatch.setattr(
        research, "fetch_kitsu_anime", lambda title: {"found": False, "status": "no match"},
    )
    monkeypatch.setattr(
        research, "fetch_anilist_synopsis",
        lambda title: {"found": True, "title": title, "year": 2023, "country": "JP",
                       "synopsis": "A sufficiently long synopsis for a test result."},
    )

    def broken_tenrai(_title):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(research, "fetch_tenrai_synopsis", broken_tenrai)
    monkeypatch.setattr(
        research, "fetch_wikidata_metadata",
        lambda title: {"found": True, "title": title, "countries": ["Japan"], "year": "2023"},
    )

    report = research.research_anime_sources("Example Anime")

    assert report["anilist"]["found"] is True
    assert report["kitsu"]["found"] is False
    assert report["tenrai"]["found"] is False
    assert "မရရှိနိုင်ပါ" in report["tenrai"]["status"]
    assert report["wikidata"]["found"] is True
    assert report["eligibility"].startswith("နိုင်ငံအချက်အလက် ရရှိသည်")


def test_non_dictionary_provider_response_is_reported_safely(monkeypatch):
    monkeypatch.setattr(research, "fetch_kitsu_anime", lambda _title: None)
    monkeypatch.setattr(research, "fetch_anilist_synopsis", lambda _title: None)
    monkeypatch.setattr(
        research, "fetch_tenrai_synopsis",
        lambda _title: {"found": False, "status": "not found"},
    )
    monkeypatch.setattr(
        research, "fetch_wikidata_metadata",
        lambda _title: {"found": False, "status": "not found"},
    )

    report = research.research_anime_sources("Example Anime")

    assert report["kitsu"]["found"] is False
    assert report["anilist"]["found"] is False
    assert "မမှန်ကန်သော တုံ့ပြန်မှု" in report["anilist"]["status"]
