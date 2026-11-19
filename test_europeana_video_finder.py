import json
from unittest.mock import patch

from europeana_video_finder import (
    ALLOWED_RIGHTS,
    EuropeanaSearchError,
    search_europeana_licensed_video,
)


def _response(payload):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, _limit):
            return json.dumps(payload).encode("utf-8")
    return Response()


def _binding(value):
    return {"value": value}


def test_returns_only_https_video_with_allowed_rights():
    payload = {"results": {"bindings": [
        {
            "title": _binding("Historic film collection"),
            "webResource": _binding("https://media.example.org/film.mp4"),
            "rights": _binding("http://creativecommons.org/licenses/by/4.0/"),
            "providedCHO": _binding("https://data.europeana.eu/item/123"),
            "creator": _binding("Archive"),
            "recordRights": _binding("http://creativecommons.org/licenses/by/4.0/"),
        },
        {
            "title": _binding("Restricted video"),
            "webResource": _binding("https://media.example.org/restricted.mp4"),
            "rights": _binding("http://rightsstatements.org/vocab/InC/1.0/"),
            "providedCHO": _binding("https://data.europeana.eu/item/456"),
        },
        {
            "title": _binding("Unsafe URL"),
            "webResource": _binding("http://media.example.org/insecure.mp4"),
            "rights": _binding("http://creativecommons.org/licenses/by/4.0/"),
            "providedCHO": _binding("https://data.europeana.eu/item/000"),
        },
    ]}}
    with patch("europeana_video_finder.urllib.request.urlopen", return_value=_response(payload)):
        results = search_europeana_licensed_video("Historic film")
    assert len(results) == 1
    assert results[0]["license"] == "CC BY 4.0"
    assert results[0]["artist"] == "Archive"
    assert results[0]["download_enabled"] is False


def test_rejects_empty_or_oversized_query():
    import pytest
    with pytest.raises(EuropeanaSearchError):
        search_europeana_licensed_video(" ")
    with pytest.raises(EuropeanaSearchError):
        search_europeana_licensed_video("x" * 161)


def test_network_error_returns_safe_message():
    import pytest
    with patch("europeana_video_finder.urllib.request.urlopen", side_effect=OSError("offline")):
        with pytest.raises(EuropeanaSearchError, match="SPARQL"):
            search_europeana_licensed_video("Historic film")


def test_rights_allowlist_excludes_nc_and_nd():
    assert "http://creativecommons.org/licenses/by/4.0/" in ALLOWED_RIGHTS
    assert "http://creativecommons.org/licenses/by-sa/4.0/" in ALLOWED_RIGHTS
    assert "http://creativecommons.org/licenses/by-nc/4.0/" not in ALLOWED_RIGHTS
    assert "http://creativecommons.org/licenses/by-nd/4.0/" not in ALLOWED_RIGHTS


def test_sparql_uses_europeana_video_proxy_structure():
    captured = []

    def fake_urlopen(request, timeout):
        from urllib.parse import parse_qs, urlparse
        captured.append(parse_qs(urlparse(request.full_url).query)["query"][0])
        return _response({"results": {"bindings": []}})

    with patch("europeana_video_finder.urllib.request.urlopen", side_effect=fake_urlopen):
        search_europeana_licensed_video("Historic film")

    query = captured[0]
    assert "?proxy ore:proxyIn ?aggregation" in query
    assert 'edm:type "VIDEO"' in query
    assert "dc:title ?title" in query
    assert "(edm:isShownBy|edm:hasView) ?webResource" in query
    assert "edm:rights ?rights" in query


def test_search_uses_verified_alternate_titles_in_title_filter():
    from urllib.parse import parse_qs, urlparse

    captured = []

    def fake_urlopen(request, timeout):
        captured.append(parse_qs(urlparse(request.full_url).query)["query"][0])
        return _response({"results": {"bindings": []}})

    with patch("europeana_video_finder.urllib.request.urlopen", side_effect=fake_urlopen):
        search_europeana_licensed_video(
            "Frieren: Beyond Journey's End",
            alternate_queries=[
                "Sousou no Frieren",
                "Frieren: Beyond Journey's End",
                "ဥပမာခေါင်းစဉ်",
                "Ignored fifth alias",
            ],
        )

    query = captured[0]
    assert 'LCASE("Frieren: Beyond Journey\\'s End")' in query
    assert 'LCASE("Sousou no Frieren")' in query
    assert 'LCASE("ဥပမာခေါင်းစဉ်")' in query
    assert "Ignored fifth alias" not in query


def test_rejects_non_europeana_source_page_but_keeps_discovery_record():
    payload = {"results": {"bindings": [{
        "title": _binding("Historic film collection"),
        "webResource": _binding("https://media.example.org/film.mp4"),
        "rights": _binding("http://creativecommons.org/licenses/by/4.0/"),
        "providedCHO": _binding("https://untrusted.example.org/item/123"),
    }]}}
    with patch("europeana_video_finder.urllib.request.urlopen", return_value=_response(payload)):
        results = search_europeana_licensed_video("Historic film")
    assert len(results) == 1
    assert results[0]["source_page"] == ""
    assert results[0]["download_enabled"] is False


def test_normalizes_only_europeana_http_item_page_to_https():
    payload = {"results": {"bindings": [{
        "title": _binding("Historic film collection"),
        "webResource": _binding("https://media.example.org/film.mp4"),
        "rights": _binding("http://creativecommons.org/licenses/by/4.0/"),
        "providedCHO": _binding("http://data.europeana.eu/item/123"),
    }]}}
    with patch("europeana_video_finder.urllib.request.urlopen", return_value=_response(payload)):
        results = search_europeana_licensed_video("Historic film")
    assert results[0]["source_page"] == "https://data.europeana.eu/item/123"
