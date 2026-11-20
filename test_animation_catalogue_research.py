import animation_catalogue_research as catalogues
import pytest


@pytest.fixture(autouse=True)
def prevent_live_catalogue_requests(monkeypatch):
    monkeypatch.setattr(catalogues, "fetch_bcdb_popular_cartoon", lambda _title: {"found": False, "status": "not mocked"})
    monkeypatch.setattr(catalogues, "fetch_blender_open_movie", lambda _title: {"found": False, "status": "not mocked"})


def test_bangumi_requires_unique_exact_animation_title(monkeypatch):
    monkeypatch.setattr(catalogues, "_bangumi_search", lambda _title: {
        "data": [
            {"id": 11, "type": 2, "name": "Example Donghua", "name_cn": "示例动画",
             "summary": "An original animation.", "nsfw": False},
            {"id": 12, "type": 2, "name": "Example Donghua", "name_cn": "示例动画",
             "summary": "Duplicate entry.", "nsfw": False},
            {"id": 13, "type": 1, "name": "Example Donghua", "name_cn": "示例动画",
             "nsfw": False},
        ]
    })
    result = catalogues.fetch_bangumi_animation("Example Donghua")
    assert result["found"] is False
    assert "တစ်ခုတည်း" in result["status"]


def test_bangumi_returns_exact_non_nsfw_animation_record(monkeypatch):
    monkeypatch.setattr(catalogues, "_bangumi_search", lambda _title: {
        "data": [
            {"id": 11, "type": 2, "name": "Example Donghua", "name_cn": "Example Donghua",
             "summary": "An original animated story.", "date": "2025-01-01",
             "score": 8.1, "rank": 20, "nsfw": False},
            {"id": 12, "type": 2, "name": "Example Donghua Special", "name_cn": "",
             "nsfw": False},
        ]
    })
    result = catalogues.fetch_bangumi_animation("Example Donghua")
    assert result["found"] is True
    assert result["media_id"] == 11
    assert result["provider_url"] == "https://bgm.tv/subject/11"


def test_bangumi_rejects_nsfw_and_non_animation_subjects(monkeypatch):
    monkeypatch.setattr(catalogues, "_bangumi_search", lambda _title: {
        "data": [
            {"id": 11, "type": 2, "name": "Example", "name_cn": "", "nsfw": True},
            {"id": 12, "type": 4, "name": "Example", "name_cn": "", "nsfw": False},
        ]
    })
    result = catalogues.fetch_bangumi_animation("Example")
    assert result["found"] is False


def test_donghua_requires_bangumi_and_wikidata_china_origin(monkeypatch):
    monkeypatch.setattr(catalogues, "fetch_bangumi_animation", lambda _title: {
        "found": True, "title": "Example", "provider_url": "https://bgm.tv/subject/11",
    })
    monkeypatch.setattr(catalogues, "_safe_wikidata", lambda _title: {
        "found": True, "title": "Example", "countries": ["China"],
        "description": "Chinese animated television series", "source": "https://www.wikidata.org/wiki/Q11",
    })
    result = catalogues.research_animation_catalogues("Example")
    assert result["donghua"]["found"] is True


def test_bangumi_alone_does_not_prove_donghua_origin(monkeypatch):
    monkeypatch.setattr(catalogues, "fetch_bangumi_animation", lambda _title: {
        "found": True, "title": "Example",
    })
    monkeypatch.setattr(catalogues, "_safe_wikidata", lambda _title: {
        "found": True, "title": "Example", "countries": ["Japan"],
        "description": "Japanese animated television series",
    })
    result = catalogues.research_animation_catalogues("Example")
    assert result["donghua"]["found"] is False
    assert "China" in result["donghua"]["status"]


def test_cartoon_and_3d_classifications_require_explicit_wikidata_description(monkeypatch):
    monkeypatch.setattr(catalogues, "fetch_bangumi_animation", lambda _title: {
        "found": False, "status": "not found",
    })
    monkeypatch.setattr(catalogues, "_safe_wikidata", lambda _title: {
        "found": True, "title": "Example", "description": "American computer-animated film",
        "countries": ["United States"], "year": "2024", "source": "https://www.wikidata.org/wiki/Q1",
    })
    result = catalogues.research_animation_catalogues("Example")
    assert result["cartoon"]["found"] is True
    assert result["3d_animation"]["found"] is True


def test_unknown_3d_technique_is_not_inferred(monkeypatch):
    monkeypatch.setattr(catalogues, "fetch_bangumi_animation", lambda _title: {"found": False})
    monkeypatch.setattr(catalogues, "_safe_wikidata", lambda _title: {
        "found": True, "title": "Example", "description": "Animated feature film",
        "countries": ["United States"],
    })
    result = catalogues.research_animation_catalogues("Example")
    assert result["cartoon"]["found"] is True
    assert result["3d_animation"]["found"] is False


def test_animation_catalogue_report_has_all_three_tracks():
    report = {
        "title": "Example",
        "donghua": {"found": False, "status": "No Donghua match"},
        "cartoon": {"found": False, "status": "No cartoon match"},
        "3d_animation": {"found": False, "status": "No 3D match"},
    }
    output = catalogues.format_animation_catalogue_report(report)
    assert "DONGHUA" in output
    assert "CARTOON" in output
    assert "3D ANIMATION" in output
    assert "\\n" not in output


def test_verified_indian_origin_is_excluded_from_cartoon_and_3d_tracks(monkeypatch):
    monkeypatch.setattr(catalogues, "fetch_bangumi_animation", lambda _title: {"found": False})
    monkeypatch.setattr(catalogues, "_safe_wikidata", lambda _title: {
        "found": True, "title": "Example", "description": "Indian computer-animated film",
        "countries": ["India"],
    })
    result = catalogues.research_animation_catalogues("Example")
    assert result["cartoon"]["found"] is False
    assert result["cartoon"]["india_excluded"] is True
    assert result["3d_animation"]["found"] is False
    assert result["3d_animation"]["india_excluded"] is True


def test_bcdb_cartoon_match_requires_non_japanese_non_chinese_origin(monkeypatch):
    monkeypatch.setattr(catalogues, "fetch_bcdb_popular_cartoon", lambda _title: {
        "found": True, "title": "Example Cartoon", "provider_url": "https://www.bcdb.com/cartoon/3-example",
        "catalogue_url": "https://www.bcdb.com/most-popular",
    })
    monkeypatch.setattr(catalogues, "_safe_wikidata", lambda _title: {
        "found": True, "title": "Example Cartoon", "countries": ["United States"],
        "description": "American animated television series", "year": "2024",
        "source": "https://www.wikidata.org/wiki/Q11",
    })
    result = catalogues.research_animation_catalogues("Example Cartoon")
    assert result["cartoon"]["found"] is True
    assert result["cartoon"]["provider"] == "The Big Cartoon DataBase (BCDB)"
    assert result["cartoon"]["origin_verified"] is True


def test_bcdb_japanese_title_is_not_mislabelled_cartoon(monkeypatch):
    monkeypatch.setattr(catalogues, "fetch_bcdb_popular_cartoon", lambda _title: {
        "found": True, "title": "Example", "provider_url": "https://www.bcdb.com/cartoon/3-example",
    })
    monkeypatch.setattr(catalogues, "_safe_wikidata", lambda _title: {
        "found": True, "title": "Example", "countries": ["Japan"],
        "description": "Japanese animated film",
    })
    result = catalogues.research_animation_catalogues("Example")
    assert result["cartoon"]["found"] is False


def test_blender_open_movie_is_a_3d_catalogue_lead(monkeypatch):
    monkeypatch.setattr(catalogues, "fetch_blender_open_movie", lambda _title: {
        "found": True, "provider": "Blender Studio Open Movies (curated 3D subset)",
        "title": "Big Buck Bunny", "year": 2008,
        "source": "https://studio.blender.org/projects/big-buck-bunny/",
        "catalogue": "https://studio.blender.org/films/",
    })
    monkeypatch.setattr(catalogues, "_safe_wikidata", lambda _title: {
        "found": True, "title": "Big Buck Bunny", "countries": ["Netherlands"],
        "description": "Computer animated short film",
    })
    result = catalogues.research_animation_catalogues("Big Buck Bunny")
    assert result["3d_animation"]["found"] is True
    assert result["3d_animation"]["provider"] == "Blender Studio Open Movies (curated 3D subset)"
