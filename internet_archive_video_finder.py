"""Internet Archive video discovery with strict uploader-license filtering.

Archive metadata is uploader supplied and is not an independent copyright
warranty. Results are discovery-only; never auto-download IA media.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import urllib.request

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/"
MAX_FILE_BYTES = 1024 * 1024 * 1024

ALLOWED_LICENSES = {
    f"https://creativecommons.org/licenses/{family}/{version}/"
    for family in ("by", "by-sa")
    for version in ("1.0", "2.0", "2.5", "3.0", "4.0")
} | {
    f"http://creativecommons.org/licenses/{family}/{version}/"
    for family in ("by", "by-sa")
    for version in ("1.0", "2.0", "2.5", "3.0", "4.0")
} | {
    "https://creativecommons.org/publicdomain/zero/1.0/",
    "http://creativecommons.org/publicdomain/zero/1.0/",
    "https://creativecommons.org/publicdomain/mark/1.0/",
    "http://creativecommons.org/publicdomain/mark/1.0/",
}


class InternetArchiveSearchError(ValueError):
    """Raised when Internet Archive discovery is unavailable or malformed."""


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = re.sub(r"\s*\(\d{4}\)\s*$", "", value)
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def _license_label(uri: str) -> str:
    if "publicdomain/zero" in uri:
        return "CC0"
    if "publicdomain/mark" in uri:
        return "Public Domain Mark"
    family, version = uri.rstrip("/").split("/")[-2:]
    return f"CC BY{'-SA' if family == 'by-sa' else ''} {version}"


def _duration_seconds(value) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if ":" in raw:
            parts = [float(part) for part in raw.split(":")]
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            return None
        result = float(raw)
        return result if result > 0 else None
    except (TypeError, ValueError):
        return None


def _request_json(url: str, limit: int = 4_000_000) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NEXORA-Myanmar-Recap/1.0 (Internet Archive public metadata discovery)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read(limit).decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("error"):
        raise InternetArchiveSearchError("Internet Archive metadata response မမှန်ပါ။")
    return payload


def search_internet_archive_licensed_video(query: str, limit: int = 6) -> list[dict]:
    """Find exact-title IA movie records with explicit reusable license metadata."""
    clean = " ".join(str(query or "").split()).strip()
    if not clean or len(clean) > 160:
        raise InternetArchiveSearchError("Internet Archive ရှာဖွေရန် ခေါင်းစဉ် မမှန်ပါ။")
    limit = max(1, min(int(limit), 10))
    escaped = clean.replace("\\", "\\\\").replace('"', '\\"')
    params = urllib.parse.urlencode([
        ("q", f'title:"{escaped}" AND mediatype:movies'),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("rows", str(limit)),
        ("page", "1"),
        ("output", "json"),
    ])
    try:
        search = _request_json(SEARCH_URL + "?" + params)
    except Exception as exc:
        raise InternetArchiveSearchError("Internet Archive search ယခုချိန်တွင် မရရှိပါ။") from exc

    docs = search.get("response", {}).get("docs", [])
    results = []
    seen = set()
    for doc in docs[:limit]:
        identifier = str(doc.get("identifier") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{5,100}", identifier):
            continue
        try:
            item = _request_json(METADATA_URL + urllib.parse.quote(identifier, safe=""))
        except Exception:
            continue
        metadata = item.get("metadata") or {}
        title = str(metadata.get("title") or doc.get("title") or "").strip()
        if _norm(title) != _norm(clean):
            continue
        requested_year_match = re.search(r"\((\d{4})\)\s*$", clean)
        if requested_year_match:
            title_year_match = re.search(r"\((\d{4})\)\s*$", title)
            metadata_year = str(metadata.get("year") or metadata.get("date") or "")
            matched_year = (
                title_year_match.group(1) if title_year_match
                else next(iter(re.findall(r"\d{4}", metadata_year)), "")
            )
            if matched_year != requested_year_match.group(1):
                continue
        if str(metadata.get("mediatype") or "").casefold() != "movies":
            continue
        license_uri = str(metadata.get("licenseurl") or "").strip()
        if license_uri not in ALLOWED_LICENSES:
            continue
        files = []
        for file_info in item.get("files") or []:
            name = str(file_info.get("name") or "").strip()
            fmt = str(file_info.get("format") or "").casefold()
            source = str(file_info.get("source") or "").casefold()
            if source != "original" or not name or name.startswith("__"):
                continue
            if not name.lower().endswith((".mp4", ".m4v", ".mov", ".webm", ".mkv", ".mpeg", ".mpg")):
                continue
            try:
                size = int(file_info.get("size") or 0)
            except (TypeError, ValueError):
                continue
            if size <= 0 or size > MAX_FILE_BYTES:
                continue
            files.append({
                "name": name,
                "format": fmt,
                "size": size,
                "duration_seconds": _duration_seconds(file_info.get("length")),
            })
        if not files:
            continue
        files.sort(key=lambda entry: (entry["duration_seconds"] or 0, entry["size"]), reverse=True)
        key = identifier.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "title": title,
            "identifier": identifier,
            "source": "Internet Archive",
            "source_page": f"https://archive.org/details/{identifier}",
            "license": _license_label(license_uri),
            "license_uri": license_uri,
            "artist": str(metadata.get("creator") or "Unknown"),
            "year": str(metadata.get("year") or metadata.get("date") or ""),
            "runtime_seconds": _duration_seconds(metadata.get("runtime")),
            "files": files[:3],
            "download_enabled": False,
            "reuse_ready": False,
            "notice": (
                "လိုင်စင်သည် uploader ထည့်သွင်းထားသော metadata ဖြစ်ပြီး Internet Archive က "
                "copyright အခြေအနေကို အာမမခံပါ။ Original uploader/rights ကို လူကိုယ်တိုင်စစ်ဆေးပြီးမှသာ အသုံးပြုပါ။"
            ),
        })
    return results
