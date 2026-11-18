"""Find reusable video files with explicit free licenses on Wikimedia Commons.

This deliberately does not scrape streaming sites or treat trailers as reusable.
Only CC0, CC BY, CC BY-SA, and public-domain files are returned.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
import re

API = "https://commons.wikimedia.org/w/api.php"
LICENSE_PATTERN = re.compile(r"^(?:CC0(?:\s|$)|CC BY(?:-SA)?(?:\s|$)|Public domain$)", re.IGNORECASE)


class ClipSourceError(ValueError):
    """Raised when licensed clip discovery fails."""


def search_licensed_video(query: str, limit: int = 8, alternate_queries: list[str] | None = None) -> list[dict]:
    """Search Commons using the requested title and verified metadata aliases.

    Every query is still license-filtered; aliases broaden discovery, not acceptance.
    """
    queries = []
    for raw in [query, *(alternate_queries or [])]:
        clean = " ".join(str(raw or "").split())
        if clean and len(clean) <= 180 and clean.casefold() not in {x.casefold() for x in queries}:
            queries.append(clean)
    if not queries:
        raise ClipSourceError("ရှာဖွေရန် ဇာတ်ကားအမည် သို့မဟုတ် Scene စကားလုံး ထည့်ပါ။")
    limit = max(1, min(int(limit), 10))
    results_by_title = {}
    failures = 0
    for search_query in queries[:4]:
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f'filetype:video "{search_query}"',
            "gsrnamespace": 6,
            "gsrlimit": limit * 3,
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
        }
        url = API + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "NEXORA-Myanmar-Recap/1.0 (licensed media discovery)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read(2_000_000).decode("utf-8"))
        except Exception:
            failures += 1
            continue

        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            title = str(page.get("title", ""))
            if title in results_by_title:
                continue
            info_list = page.get("imageinfo") or []
            if not info_list:
                continue
            info = info_list[0]
            if not str(info.get("mime", "")).startswith("video/"):
                continue
            meta = info.get("extmetadata") or {}
            license_name = str((meta.get("LicenseShortName") or {}).get("value", "")).strip()
            usage_terms = str((meta.get("UsageTerms") or {}).get("value", "")).strip()
            if not LICENSE_PATTERN.match(license_name):
                continue
            results_by_title[title] = {
                "title": title,
                "url": info.get("url", ""),
                "source_page": page.get("canonicalurl") or (
                    "https://commons.wikimedia.org/wiki/" +
                    urllib.parse.quote(title.replace(" ", "_"))
                ),
                "license": license_name,
                "usage_terms": usage_terms,
                "artist": str((meta.get("Artist") or {}).get("value", "Unknown")).strip(),
                "attribution": str((meta.get("Attribution") or {}).get("value", "")).strip(),
                "mime": info.get("mime", ""),
                "size": int(info.get("size", 0) or 0),
            }
            if len(results_by_title) >= limit:
                break
        if len(results_by_title) >= limit:
            break
    if failures == min(len(queries), 4):
        raise ClipSourceError("Wikimedia Commons ရင်းမြစ်ကို ယခုချိန်တွင် ရှာမရပါ။")
    return list(results_by_title.values())
