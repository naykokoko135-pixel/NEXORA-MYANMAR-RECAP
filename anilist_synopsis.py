"""Fetch exact-match anime series synopsis from the public AniList GraphQL API.

AniList descriptions are series-level editorial summaries, not episode scripts.
They are returned as research leads and are never passed to the recap renderer.
"""
import re
from html import unescape
from html.parser import HTMLParser
from urllib.request import Request, urlopen
import json

API_URL = "https://graphql.anilist.co"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0"


class _DescriptionText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _plain_text(value):
    parser = _DescriptionText()
    parser.feed(str(value or ""))
    return re.sub(r"\s+", " ", unescape("".join(parser.parts))).strip()


def _norm(value):
    value = re.sub(r"\([^)]*\)", " ", str(value or "").casefold())
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _graphql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = Request(
        API_URL,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_anilist_synopsis(title):
    """Return an exact-title anime series overview; never guess a fuzzy result."""
    requested = " ".join(str(title or "").split()).strip()
    normalized = _norm(requested)
    if not normalized or len(requested) > 120:
        return {"found": False, "status": "Anime ခေါင်းစဉ် မမှန်ကန်ပါ။"}

    query = """
    query ($search: String) {
      Page(page: 1, perPage: 10) {
        media(search: $search, type: ANIME) {
          id
          title { romaji english native }
          synonyms
          description(asHtml: true)
          siteUrl
          format
          episodes
          seasonYear
          countryOfOrigin
        }
      }
    }
    """
    try:
        payload = _graphql(query, {"search": requested})
        if payload.get("errors"):
            return {"found": False, "status": "AniList ရင်းမြစ်ကို ယခုဖတ်မရပါ။"}
        candidates = payload.get("data", {}).get("Page", {}).get("media", [])
        exact = []
        for item in candidates:
            titles = item.get("title") or {}
            names = list(titles.values()) + list(item.get("synonyms") or [])
            if any(_norm(name) == normalized for name in names if name):
                exact.append(item)
        if len(exact) != 1:
            return {
                "found": False,
                "status": (
                    "AniList တွင် အမည်တိတိကျကျ ကိုက်ညီသော Anime တစ်ခုတည်းကို "
                    "မသတ်မှတ်နိုင်ပါ။"
                ),
            }

        item = exact[0]
        if str(item.get("countryOfOrigin") or "").upper() == "IN":
            return {"found": False, "status": "ဒီ Project မှာ အိန္ဒိယခေါင်းစဉ်များ မထည့်ထားပါ။"}
        description = _plain_text(item.get("description"))
        if len(description) < 100:
            return {"found": False, "status": "AniList မှာ အသုံးပြုနိုင်သော synopsis မလုံလောက်ပါ။"}
        return {
            "found": True,
            "provider": "AniList",
            "provider_url": item.get("siteUrl", ""),
            "media_id": item.get("id"),
            "title": (item.get("title") or {}).get("english")
                or (item.get("title") or {}).get("romaji")
                or requested,
            "format": item.get("format") or "",
            "episodes": item.get("episodes"),
            "year": item.get("seasonYear"),
            "country": item.get("countryOfOrigin") or "",
            "synopsis": description[:3500],
            "scope": "series_overview_not_episode_plot",
            "notice": (
                "AniList synopsis သည် series အဆင့် မိတ်ဆက်စာသာဖြစ်ပြီး "
                "episode တစ်ခုချင်း၏ ဇာတ်ကွက်အကျဉ်း မဟုတ်ပါ။"
            ),
        }
    except Exception:
        return {"found": False, "status": "AniList ရင်းမြစ်ကို ယခုချိတ်ဆက်မရပါ။"}
