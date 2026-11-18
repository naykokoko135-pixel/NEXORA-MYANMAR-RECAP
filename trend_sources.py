"""Free, public anime trend signals from AniList (series-level, not episode views)."""
import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ANILIST_URL = "https://graphql.anilist.co"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0 (public trend metadata)"
QUERY = """
query {
  Page(page: 1, perPage: 10) {
    media(type: ANIME, sort: TRENDING_DESC, isAdult: false) {
      title { english romaji }
      siteUrl
      trending
      popularity
      averageScore
      episodes
      format
    }
  }
}
"""


def _fetch_json(url=ANILIST_URL, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_anime_trends(limit=10):
    """Return current AniList series trend signals; never imply episode view counts."""
    try:
        payload = _fetch_json(payload={"query": QUERY})
        media = payload.get("data", {}).get("Page", {}).get("media", [])
        items = []
        for entry in media[:max(1, min(int(limit), 10))]:
            title_data = entry.get("title") or {}
            items.append({
                "title": title_data.get("english") or title_data.get("romaji") or "Untitled",
                "url": entry.get("siteUrl", ""),
                "trending": entry.get("trending"),
                "popularity": entry.get("popularity"),
                "score": entry.get("averageScore"),
                "episodes": entry.get("episodes"),
                "format": entry.get("format"),
            })
        return {"ok": bool(items), "source": "AniList", "checked_at": datetime.now(timezone.utc).isoformat(), "items": items, "error": ""}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        return {"ok": False, "source": "AniList", "checked_at": datetime.now(timezone.utc).isoformat(), "items": [], "error": type(exc).__name__}


def format_anime_trends(result):
    """Format transparent, source-attributed series trends for Telegram."""
    lines = [
        "📈 NEXORA — လက်ရှိ Anime Trend (Series-level)",
        f"ရင်းမြစ်: {result.get('source', 'AniList')}",
        f"စစ်ဆေးချိန် (UTC): {result.get('checked_at', 'မသိ')}",
    ]
    if not result.get("ok") or not result.get("items"):
        lines.extend(["လက်ရှိ Trend data မရရှိပါ။", "အဆင့်သတ်မှတ်ချက်ကို မခန့်မှန်းထားပါ။ နောက်တစ်ကြိမ် ပြန်စစ်ပါ။"])
        return "\n".join(lines)
    for index, item in enumerate(result["items"], start=1):
        lines.append(
            f"{index}. {item['title']} — Trend {item.get('trending') if item.get('trending') is not None else 'မရရှိ'}"
            f" | Popularity {item.get('popularity') if item.get('popularity') is not None else 'မရရှိ'}"
            f" | Score {item.get('score') if item.get('score') is not None else 'မရရှိ'}"
        )
        if item.get("url"):
            lines.append(item["url"])
    lines.extend([
        "မှတ်ချက်: ဤအချက်အလက်သည် AniList ပေါ်ရှိ Anime series trend/popularity ဖြစ်ပြီး YouTube view count သို့မဟုတ် Episode တစ်ခုချင်းစီ၏ လူကြည့်များမှု မဟုတ်ပါ။",
        "3D Animation၊ Cartoon နှင့် Donghua အားလုံးကို ကိုယ်စားပြုသည့် ranking ဟု မယူဆပါနှင့်။",
    ])
    return "\n".join(lines)
