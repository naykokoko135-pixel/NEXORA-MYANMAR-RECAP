import kitsu_anime_research as kitsu


def _record(record_id="10", **overrides):
    attrs = {
        "canonicalTitle": "Sample Anime",
        "titles": {"en": "Sample Anime", "ja_jp": "サンプル"},
        "slug": "sample-anime",
        "synopsis": "A useful synopsis. " + ("More story context. " * 12),
        "subtype": "TV",
        "episodeCount": 12,
        "startDate": "2024-04-01",
        "ageRating": "PG",
        "averageRating": "78.5",
    }
    attrs.update(overrides)
    return {"id": record_id, "attributes": attrs}


def test_exact_title_returns_catalogue_metadata(monkeypatch):
    monkeypatch.setattr(kitsu, "_get_json", lambda _url: {"data": [_record()]})
    result = kitsu.fetch_kitsu_anime("Sample Anime")
    assert result["found"] is True
    assert result["media_id"] == "10"
    assert result["year"] == "2024"
    assert result["scope"] == "series_overview_not_episode_plot"


def test_rejects_fuzzy_or_ambiguous_results(monkeypatch):
    monkeypatch.setattr(kitsu, "_get_json", lambda _url: {
        "data": [_record(), _record("11", canonicalTitle="Sample Anime Special")]
    })
    assert kitsu.fetch_kitsu_anime("Sample Anime")["found"] is True


def test_rejects_multiple_exact_records(monkeypatch):
    monkeypatch.setattr(kitsu, "_get_json", lambda _url: {
        "data": [_record(), _record("11")]
    })
    assert kitsu.fetch_kitsu_anime("Sample Anime")["found"] is False


def test_rejects_adult_rating(monkeypatch):
    monkeypatch.setattr(kitsu, "_get_json", lambda _url: {
        "data": [_record(ageRating="R18")]
    })
    result = kitsu.fetch_kitsu_anime("Sample Anime")
    assert result["found"] is False
    assert "အရွယ်ရောက်သူ" in result["status"]


def test_rejects_empty_title():
    assert kitsu.fetch_kitsu_anime("")["found"] is False



def test_episode_summaries_require_exact_anime_and_match_relationship_ids(monkeypatch):
    anime = _record()
    anime["relationships"] = {"episodes": {"data": [
        {"id": "ep2", "type": "episodes"}, {"id": "ep1", "type": "episodes"}
    ]}}
    monkeypatch.setattr(kitsu, "_get_json", lambda _url: {
        "data": [anime],
        "included": [
            {"id": "ep1", "type": "episodes", "attributes": {
                "seasonNumber": 1, "number": 1, "canonicalTitle": "First",
                "airDate": "2024-01-01", "synopsis": "A real episode overview. " * 8,
            }},
            {"id": "ep2", "type": "episodes", "attributes": {
                "seasonNumber": 1, "number": 2, "canonicalTitle": "Second",
                "airDate": "2024-01-08", "synopsis": "Another episode overview. " * 8,
            }},
            {"id": "unrelated", "type": "episodes", "attributes": {
                "seasonNumber": 1, "number": 3, "canonicalTitle": "Unrelated",
                "synopsis": "This episode does not belong to the selected anime. " * 4,
            }},
        ],
    })
    result = kitsu.fetch_kitsu_episode_summaries("Sample Anime", 5)
    assert result["found"] is True
    assert [item["title"] for item in result["episodes"]] == ["First", "Second"]
    assert result["scope"] == "brief_episode_summary_excerpts"


def test_episode_summaries_reject_adult_anime(monkeypatch):
    anime = _record(ageRating="R18")
    anime["relationships"] = {"episodes": {"data": []}}
    monkeypatch.setattr(kitsu, "_get_json", lambda _url: {"data": [anime], "included": []})
    result = kitsu.fetch_kitsu_episode_summaries("Sample Anime")
    assert result["found"] is False
    assert "အရွယ်ရောက်သူ" in result["status"]
