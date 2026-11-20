import bcdb_cartoon_catalogue as bcdb


def test_bcdb_parser_extracts_only_cartoon_records_and_periods():
    html = """
    <h2>Most viewed of all time</h2>
    <ol><li><a href="/cartoon/3-the-lion-king">The Lion King</a></li></ol>
    <h2>Most viewed this month November 2026</h2>
    <ol><li><a href="https://www.bcdb.com/cartoon/4-cinderella">Cinderella</a></li></ol>
    <a href="/search?q=lion">Search</a>
    """
    parser = bcdb._PopularPageParser()
    parser.feed(html)
    assert len(parser.items) == 2
    assert parser.items[0]["title"] == "The Lion King"
    assert parser.items[0]["period"] == "all_time"
    assert parser.items[1]["title"] == "Cinderella"
    assert parser.items[1]["period"] == "this_month"


def test_bcdb_exact_popular_title_match_and_year_suffix(monkeypatch):
    monkeypatch.setattr(bcdb, "_fetch_popular_catalogue", lambda: [
        {"id": "3", "title": "The Lion King", "url": "https://www.bcdb.com/cartoon/3-the-lion-king",
         "period": "all_time"},
    ])
    result = bcdb.fetch_bcdb_popular_cartoon("The Lion King (1994)")
    assert result["found"] is True
    assert result["media_id"] == "3"
    assert result["license"] == "CC BY 4.0 for BCDB facts and compilation; artwork excluded"


def test_bcdb_does_not_fuzzy_match_or_claim_absence(monkeypatch):
    monkeypatch.setattr(bcdb, "_fetch_popular_catalogue", lambda: [
        {"id": "3", "title": "The Lion King", "url": "https://www.bcdb.com/cartoon/3-the-lion-king",
         "period": "all_time"},
    ])
    result = bcdb.fetch_bcdb_popular_cartoon("Lion King")
    assert result["found"] is False
    assert "မတွေ့ပါ" in result["status"]


def test_bcdb_fetch_uses_only_allowed_popular_url():
    assert bcdb.POPULAR_URL == "https://www.bcdb.com/most-popular"
    assert "/search" not in bcdb.POPULAR_URL
    assert bcdb.CRAWL_DELAY_SECONDS >= 5
