"""Research English-language movie-recap videos on YouTube.

This module returns public metadata for editorial research only. It never
downloads videos, extracts streams, transcripts, scripts, or reuses footage.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_ROOT = "https://www.googleapis.com/youtube/v3"
RECAP_TERMS = (
    "movie recap", "film recap", "movie explained", "film explained",
    "ending explained", "story explained", "full story",
)
BLOCK_TERMS = (
    "try on haul", "underwear", "lingerie", "transparent", "fortnite",
    "gameplay", "battle pass", "skin ranking", "character trailer",
    "reaction", "edit", "amv", "shorts", "short film", "trailer",
)
STOP_WORDS = {"the", "a", "an", "of", "and", "to", "in", "part", "movie", "film"}


class YouTubeRecapResearchError(ValueError):
    """Raised when YouTube recap research is unavailable or invalid."""


def _api(endpoint: str, params: dict) -> dict:
    request = urllib.request.Request(
        API_ROOT + "/" + endpoint + "?" + urllib.parse.urlencode(params),
        headers={"Accept": "application/json", "User-Agent": "NEXORA-Myanmar-Recap/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read(1_500_000).decode("utf-8"))
    except Exception as exc:
        raise YouTubeRecapResearchError("YouTube Data API ရှာဖွေမှု မအောင်မြင်ပါ။") from exc
    if not isinstance(data, dict):
        raise YouTubeRecapResearchError("YouTube API တုံ့ပြန်ချက် မမှန်ကန်ပါ။")
    return data


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", str(text).casefold()) if len(word) > 1 and word not in STOP_WORDS}


def _is_recap(title: str, description: str) -> bool:
    text = (title + " " + description).casefold()
    if any(term in text for term in BLOCK_TERMS):
        return False
    return any(term in text for term in RECAP_TERMS)


def search_youtube_movie_recaps(title: str, limit: int = 8, api_key: str | None = None) -> list[dict]:
    """Return relevant English-language recap research leads ranked by public view count."""
    clean = " ".join(str(title or "").split())
    if not clean or len(clean) > 160:
        raise YouTubeRecapResearchError("ရှာဖွေရန် နိုင်ငံခြားရုပ်ရှင်အမည်ကို မှန်ကန်စွာ ထည့်ပါ။")
    key = str(api_key or os.getenv("YOUTUBE_DATA_API_KEY", "")).strip()
    if not key:
        raise YouTubeRecapResearchError("YOUTUBE_DATA_API_KEY မသတ်မှတ်ရသေးပါ။")
    limit = max(1, min(int(limit), 10))
    query = f'"{clean}" ("movie recap"|"film recap"|"movie explained"|"ending explained")'
    found = _api("search", {
        "part": "snippet", "q": query, "type": "video",
        "maxResults": min(25, limit * 3), "order": "viewCount",
        "relevanceLanguage": "en", "safeSearch": "strict", "key": key,
    })
    ids, snippets = [], {}
    for item in found.get("items", []):
        vid = str((item.get("id") or {}).get("videoId", "")).strip()
        if vid and vid not in snippets:
            ids.append(vid)
            snippets[vid] = item.get("snippet") or {}
    if not ids:
        return []
    details = _api("videos", {
        "part": "snippet,statistics,contentDetails,status",
        "id": ",".join(ids), "key": key,
    })
    target = _tokens(clean)
    results = []
    for item in details.get("items", []):
        vid = str(item.get("id", "")).strip()
        snippet = item.get("snippet") or snippets.get(vid, {})
        title_text = str(snippet.get("title", "")).strip()
        description = str(snippet.get("description", ""))[:5000]
        if not vid or not _is_recap(title_text, description):
            continue
        combined_tokens = _tokens(title_text + " " + description[:1200])
        overlap = len(target & combined_tokens) / max(1, len(target))
        if overlap < 0.5:
            continue
        status = item.get("status") or {}
        if status.get("privacyStatus") not in (None, "public"):
            continue
        stats = item.get("statistics") or {}
        try:
            views = int(stats.get("viewCount", 0))
        except (TypeError, ValueError):
            views = 0
        results.append({
            "title": title_text,
            "channel": str(snippet.get("channelTitle", "Unknown")),
            "published_at": str(snippet.get("publishedAt", "")),
            "views": views,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "relevance": round(overlap, 2),
            "duration": str((item.get("contentDetails") or {}).get("duration", "")),
            "research_only": True,
            "footage_reuse_allowed": False,
        })
    results.sort(key=lambda row: (row["views"], row["relevance"]), reverse=True)
    return results[:limit]


def format_youtube_movie_recaps(title: str, items: list[dict]) -> str:
    if not items:
        return (
            f"နိုင်ငံခြား YouTube Movie Recap — {title}\n"
            "ခေါင်းစဉ်နဲ့ တကယ်ကိုက်ညီတဲ့ English recap ရလဒ် မတွေ့ပါ။ "
            "မသက်ဆိုင်တဲ့ video ကို အစားထိုးမပြထားပါ။"
        )
    lines = [f"🌍 နိုင်ငံခြား YouTube Movie Recap Research — {title}",
             "အောက်ပါစာရင်းသည် Channel/ခေါင်းစဉ်/ကြည့်ရှုမှု လေ့လာရန်သာ ဖြစ်သည်။"]
    for i, item in enumerate(items, 1):
        lines.append(
            f"\n{i}. {item['title']}\n"
            f"Channel: {item['channel']} | Views: {item['views']:,}\n"
            f"တင်သည့်ရက်: {item['published_at']} | Duration: {item['duration']}\n"
            f"Relevance: {item['relevance']:.0%}\n"
            f"Video: {item['url']}"
        )
    lines.append(
        "\nသတိပြုရန်: ဤရလဒ်များကို format/trend research အတွက်သာ အသုံးပြုပါ။ "
        "သူတစ်ပါး၏ recap script၊ narration၊ footage သို့မဟုတ် soundtrack ကို ကူးယူ/ပြန်တင်ရန် "
        "ခွင့်ပြုချက် မဟုတ်ပါ။ NEXORA က video download၊ transcript extraction မလုပ်ပါ။"
    )
    return "\n".join(lines)
