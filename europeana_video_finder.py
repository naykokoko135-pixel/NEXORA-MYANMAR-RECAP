"""Discover openly licensed video records in Europeana via its public SPARQL endpoint.

This module lists candidate source records only. It does not download partner-hosted
media: a record's rights metadata must be reviewed and a safe host policy established
before any automatic media fetching is enabled.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request


SPARQL_ENDPOINT = "https://sparql.europeana.eu/"
ALLOWED_RIGHTS = {
    f"http://creativecommons.org/licenses/{family}/{version}/"
    for family in ("by", "by-sa")
    for version in ("1.0", "2.0", "2.5", "3.0", "4.0")
} | {
    f"https://creativecommons.org/licenses/{family}/{version}/"
    for family in ("by", "by-sa")
    for version in ("1.0", "2.0", "2.5", "3.0", "4.0")
} | {
    "http://creativecommons.org/publicdomain/zero/1.0/",
    "https://creativecommons.org/publicdomain/zero/1.0/",
    "http://creativecommons.org/publicdomain/mark/1.0/",
    "https://creativecommons.org/publicdomain/mark/1.0/",
}


class EuropeanaSearchError(ValueError):
    """Raised when Europeana SPARQL discovery is unavailable or malformed."""


def _sparql_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _license_label(uri: str) -> str:
    if "publicdomain/zero" in uri:
        return "CC0"
    if "publicdomain/mark" in uri:
        return "Public Domain Mark"
    tail = uri.rstrip("/").split("/")[-2:]
    family, version = tail
    return f"CC BY{'-SA' if family == 'by-sa' else ''} {version}"


def _clean_queries(query: str, alternate_queries: list[str] | None) -> list[str]:
    values = []
    for raw in [query, *(alternate_queries or [])]:
        clean = " ".join(str(raw or "").split())
        if clean and len(clean) <= 160 and clean.casefold() not in {v.casefold() for v in values}:
            values.append(clean)
    return values[:4]


def search_europeana_licensed_video(
    query: str,
    limit: int = 6,
    alternate_queries: list[str] | None = None,
) -> list[dict]:
    """Return title-matched VIDEO records with explicitly reusable rights URIs.

    Verified alternate titles broaden metadata discovery only; they do not relax
    the rights allowlist. Europeana metadata is CC0, but linked media remains
    governed by its own rights statement. Results are discovery-only.
    """
    queries = _clean_queries(query, alternate_queries)
    if not queries:
        raise EuropeanaSearchError("Europeana ရှာဖွေရန် ခေါင်းစဉ်အမည် မမှန်ပါ။")
    limit = max(1, min(int(limit), 10))
    title_filters = " ||\n  ".join(
        f"CONTAINS(LCASE(STR(?title)), LCASE({_sparql_literal(term)}))"
        for term in queries
    )
    rights_values = ", ".join(f"<{uri}>" for uri in sorted(ALLOWED_RIGHTS))
    sparql = f"""
PREFIX edm: <http://www.europeana.eu/schemas/edm/>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX ore: <http://www.openarchives.org/ore/terms/>
SELECT DISTINCT ?title ?webResource ?rights ?providedCHO ?creator ?recordRights WHERE {{
  ?proxy ore:proxyIn ?aggregation ;
         edm:type "VIDEO" ;
         dc:title ?title .
  ?aggregation edm:rights ?rights ;
               (edm:isShownBy|edm:hasView) ?webResource ;
               edm:aggregatedCHO ?providedCHO .
  OPTIONAL {{ ?proxy dc:creator ?creator }}
  FILTER(
  {title_filters}
  )
  FILTER(?rights IN ({rights_values}))
}}
LIMIT {limit}
"""
    params = urllib.parse.urlencode({
        "query": sparql,
        "format": "application/sparql-results+json",
    })
    request = urllib.request.Request(
        SPARQL_ENDPOINT + "?" + params,
        headers={
            "User-Agent": "NEXORA-Myanmar-Recap/1.0 (open licensed video discovery)",
            "Accept": "application/sparql-results+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read(2_000_000).decode("utf-8"))
    except Exception as exc:
        raise EuropeanaSearchError("Europeana SPARQL ရှာဖွေမှု ယခုချိန်တွင် မရရှိပါ။") from exc

    bindings = payload.get("results", {}).get("bindings", [])
    results = []
    seen = set()
    for item in bindings:
        title = str((item.get("title") or {}).get("value", "")).strip()
        media_url = str((item.get("webResource") or {}).get("value", "")).strip()
        rights_uri = str((item.get("rights") or {}).get("value", "")).strip()
        source_page = str((item.get("providedCHO") or {}).get("value", "")).strip()
        if not title or not media_url.startswith("https://") or rights_uri not in ALLOWED_RIGHTS:
            continue
        # Only expose Europeana item pages as source links; do not surface arbitrary
        # provider-supplied page URLs as trusted navigation targets.
        parsed_page = urllib.parse.urlparse(source_page)
        if parsed_page.scheme == "http" and parsed_page.hostname == "data.europeana.eu":
            source_page = parsed_page._replace(scheme="https").geturl()
        parsed_page = urllib.parse.urlparse(source_page)
        if parsed_page.scheme != "https" or parsed_page.hostname != "data.europeana.eu":
            source_page = ""
        key = (title.casefold(), media_url)
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "title": title,
            "url": media_url,
            "source_page": source_page,
            "license": _license_label(rights_uri),
            "license_uri": rights_uri,
            "artist": str((item.get("creator") or {}).get("value", "Unknown")).strip(),
            "usage_terms": "Europeana record rights metadata; verify the linked provider page before reuse.",
            "mime": "video/unknown",
            "source": "Europeana",
            "download_enabled": False,
        })
    return results
