"""Discover YouTube videos explicitly marked Creative Commons Attribution.

This is source discovery only. It never downloads or extracts YouTube media.
Before reusing footage, verify the uploader controls every visual/audio element
and keep the required attribution. Requires YOUTUBE_DATA_API_KEY.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


API_ROOT = "https://www.googleapis.com/youtube/v3"


class YouTubeCCSearchError(ValueError):
    """Raised when YouTube CC source discovery is unavailable or invalid."""


def _get_json(endpoint: str, params: dict) -> dict:
    url = API_ROOT + "/" + endpoint + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "NEXORA-Myanmar-Recap/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read(1_500_000).decode("utf-8"))
    except Exception as exc:
        raise YouTubeCCSearchError("YouTube Data API ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။") from exc
    if not isinstance(payload, dict):
        raise YouTubeCCSearchError("YouTube API တုံ့ပြန်ချက် မမှန်ကန်ပါ။")
    return payload


def search_youtube_cc_videos(query: str, limit: int = 5, api_key: str | None = None) -> list[dict]:
    """Return public YouTube videos whose API metadata declares CC BY.

    Results intentionally contain watch/source URLs only; no stream URL or
    downloader path is returned. A CC label is not proof that the uploader
    owns all included third-party footage, so manual rights review is required.
    """
    clean = " ".join(str(query or "").split())
    if not clean or len(clean) > 180:
        raise YouTubeCCSearchError("YouTube ရှာဖွေရန် ခေါင်းစဉ်ကို မှန်ကန်စွာ ထည့်ပါ။")
    key = str(api_key or os.getenv("YOUTUBE_DATA_API_KEY", "")).strip()
    if not key:
        raise YouTubeCCSearchError("YOUTUBE_DATA_API_KEY မသတ်မှတ်ရသေးပါ။ YouTube CC ရှာဖွေမှုကို ကျော်ထားပါသည်။")
    limit = max(1, min(int(limit), 10))

    search = _get_json("search", {
        "part": "snippet",
        "q": clean,
        "type": "video",
        "videoLicense": "creativeCommon",
        "maxResults": limit,
        "safeSearch": "strict",
        "key": key,
    })
    ids = []
    snippets = {}
    for item in search.get("items", []):
        video_id = str(item.get("id", {}).get("videoId", "")).strip()
        if video_id and video_id not in snippets:
            ids.append(video_id)
            snippets[video_id] = item.get("snippet", {})
    if not ids:
        return []

    details = _get_json("videos", {
        "part": "snippet,status",
        "id": ",".join(ids),
        "key": key,
    })
    results = []
    for item in details.get("items", []):
        video_id = str(item.get("id", "")).strip()
        snippet = item.get("snippet") or snippets.get(video_id, {})
        status = item.get("status") or {}
        if (
            not video_id
            or status.get("license") != "creativeCommon"
            or status.get("privacyStatus") != "public"
            or status.get("uploadStatus") not in (None, "processed")
            or status.get("embeddable") is False
        ):
            continue
        results.append({
            "title": str(snippet.get("title", "Untitled")).strip(),
            "url": "https://www.youtube.com/watch?v=" + video_id,
            "source_page": "https://www.youtube.com/watch?v=" + video_id,
            "license": "Creative Commons Attribution (CC BY)",
            "license_uri": "https://creativecommons.org/licenses/by/4.0/",
            "artist": str(snippet.get("channelTitle", "Unknown")).strip(),
            "published_at": str(snippet.get("publishedAt", "")),
            "usage_terms": "CC BY metadata reported by YouTube API; verify uploader rights and attribute creator, title, source URL, and license.",
            "source": "YouTube",
            "download_enabled": False,
            "reuse_ready": False,
            "media_access": "YouTube watch/embed only; no automatic download or stream extraction.",
        })
    return results


def search_official_trailer_references(query: str, limit: int = 4, api_key: str | None = None) -> list[dict]:
    """Find public trailer/clip reference links; never download or claim reuse rights.

    Search results are deliberately labelled candidates because channel identity
    and the uploader's authority to license the footage are not established by
    YouTube search metadata.
    """
    clean = " ".join(str(query or "").split())
    if not clean or len(clean) > 180:
        raise YouTubeCCSearchError("YouTube trailer ရှာဖွေရန် ခေါင်းစဉ်ကို မှန်ကန်စွာ ထည့်ပါ။")
    key = str(api_key or os.getenv("YOUTUBE_DATA_API_KEY", "")).strip()
    if not key:
        raise YouTubeCCSearchError("YOUTUBE_DATA_API_KEY မသတ်မှတ်ရသေးပါ။ Trailer ရှာဖွေမှုကို ကျော်ထားပါသည်။")
    limit = max(1, min(int(limit), 8))
    candidates = []
    seen = set()
    for suffix in ("official trailer", "official clip"):
        search = _get_json("search", {
            "part": "snippet",
            "q": f"{clean} {suffix}",
            "type": "video",
            "maxResults": limit,
            "safeSearch": "strict",
            "key": key,
        })
        ids = []
        snippets = {}
        for item in search.get("items", []):
            video_id = str(item.get("id", {}).get("videoId", "")).strip()
            if video_id and video_id not in seen:
                seen.add(video_id)
                ids.append(video_id)
                snippets[video_id] = item.get("snippet", {})
        if not ids:
            continue
        details = _get_json("videos", {
            "part": "snippet,status",
            "id": ",".join(ids),
            "key": key,
        })
        for item in details.get("items", []):
            video_id = str(item.get("id", "")).strip()
            status = item.get("status") or {}
            snippet = item.get("snippet") or snippets.get(video_id, {})
            if (
                not video_id
                or status.get("privacyStatus") != "public"
                or status.get("uploadStatus") not in (None, "processed")
                or status.get("embeddable") is False
            ):
                continue
            title = str(snippet.get("title", "Untitled")).strip()
            candidates.append({
                "title": title,
                "url": "https://www.youtube.com/watch?v=" + video_id,
                "source_page": "https://www.youtube.com/watch?v=" + video_id,
                "license": "YouTube Standard License / license status not reusable by default",
                "license_uri": "https://support.google.com/youtube/answer/2797468",
                "artist": str(snippet.get("channelTitle", "Unknown")).strip(),
                "published_at": str(snippet.get("publishedAt", "")),
                "usage_terms": "Reference only. Channel identity and reuse permission are unverified.",
                "source": "YouTube Trailer Reference",
                "download_enabled": False,
                "reuse_ready": False,
                "media_access": "Official trailer/clip candidate watch or embed link only; no download or stream extraction.",
            })
            if len(candidates) >= limit:
                return candidates
    return candidates
