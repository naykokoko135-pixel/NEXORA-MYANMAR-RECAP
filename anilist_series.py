"""On-demand AniList episode-count lookup for known anime series only.

AniList is a community-assisted catalogue, not an official broadcaster guide.
Requests are made per title; this module does not bulk-collect or persist API data.
"""
import json
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://graphql.anilist.co"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0 (https://github.com/naykokoko135-pixel/NEXORA-MYANMAR-RECAP)"
ANIME_SERIES_TITLES = {
    "Demon Slayer: Kimetsu no Yaiba", "Attack on Titan", "Jujutsu Kaisen",
    "One Piece", "Naruto", "Fullmetal Alchemist: Brotherhood", "Hunter x Hunter",
    "Death Note", "My Hero Academia", "Frieren: Beyond Journey's End",
    "Solo Leveling", "Chainsaw Man", "Haikyu!!", "Violet Evergarden",
    "Dragon Ball Z", "Bleach", "Mob Psycho 100", "Spy × Family", "Vinland Saga",
}
SERIES_FORMATS = {"TV", "TV_SHORT", "ONA"}


def _normalize_title(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    return " ".join(re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).split())


def _request_media(title):
    query = """
    query ($search: String) {
      Page(page: 1, perPage: 10) {
        media(search: $search, type: ANIME, isAdult: false, sort: SEARCH_MATCH) {
          id
          title { english romaji native }
          episodes
          format
          status
          seasonYear
          siteUrl
          isAdult
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"search": title}}).encode("utf-8")
    request = Request(API_URL, data=payload, headers={
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }, method="POST")
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_anilist_episode_guide(title):
    """Return an exact, non-adult anime TV-series episode count or unavailable."""
    clean_title = " ".join((title or "").split()).strip()
    if clean_title not in ANIME_SERIES_TITLES:
        return {"found": False, "status": "ဤခေါင်းစဉ်သည် လက်ရှိ Anime Series allow-list ထဲတွင် မပါသေးပါ။"}
    try:
        payload = _request_media(clean_title)
        media = payload.get("data", {}).get("Page", {}).get("media", [])
        exact = []
        wanted = _normalize_title(clean_title)
        for item in media:
            if not isinstance(item, dict) or item.get("isAdult") is True:
                continue
            titles = item.get("title") or {}
            aliases = [titles.get("english"), titles.get("romaji"), titles.get("native")]
            if any(_normalize_title(alias) == wanted for alias in aliases if alias):
                exact.append(item)

        unique = {item.get("id"): item for item in exact if item.get("id") is not None}
        if not unique:
            return {"found": False, "status": "AniList တွင် အတိအကျကိုက်ညီသော Anime မှတ်တမ်း မတွေ့ပါ။"}
        if len(unique) != 1:
            return {"found": False, "status": "AniList တွင် အမည်တူ Anime version များရှိ၍ အလိုအလျောက် မရွေးထားပါ။"}

        item = next(iter(unique.values()))
        if item.get("format") not in SERIES_FORMATS:
            return {"found": False, "status": "AniList မှတ်တမ်းသည် TV/Web Series ပုံစံမဟုတ်သဖြင့် Episode Guide အဖြစ် မသုံးထားပါ။"}
        count = item.get("episodes")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            return {"found": False, "status": "AniList တွင် Episode အရေအတွက် မရရှိသေးပါ။"}

        return {
            "found": True,
            "title": (item.get("title") or {}).get("english")
                     or (item.get("title") or {}).get("romaji")
                     or clean_title,
            "episode_count": count,
            "format": item.get("format") or "မရရှိပါ",
            "status": item.get("status") or "မရရှိပါ",
            "season_year": item.get("seasonYear"),
            "source": item.get("siteUrl") or "https://anilist.co",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
        return {"found": False, "status": "AniList API ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။ Episode အရေအတွက်ကို မခန့်မှန်းထားပါ။"}


def format_anilist_episode_guide(result):
    """Format only the total episode count; AniList does not provide season breakdown here."""
    if not result or not result.get("found"):
        status = (result or {}).get("status", "AniList Episode အချက်အလက် မရရှိပါ။")
        return "📺 Anime Episode အရေအတွက် (AniList)\n" + status

    lines = [
        "📺 Anime Episode အရေအတွက် (AniList)",
        "ခေါင်းစဉ်: " + result.get("title", "မရရှိပါ"),
        "မီဒီယာပုံစံ: " + result.get("format", "မရရှိပါ"),
        "ထုတ်လွှင့်မှုအခြေအနေ: " + result.get("status", "မရရှိပါ"),
        "Season/ထုတ်လွှင့်သည့်နှစ်: " + (str(result.get("season_year")) if result.get("season_year") else "မရရှိပါ"),
        "စုစုပေါင်း Episode အရေအတွက်: " + str(result.get("episode_count")),
        "Source: " + result.get("source", "https://anilist.co"),
        "လိုင်စင်/အသုံးပြုမှုမှတ်ချက်: AniList API Terms ကို လိုက်နာပြီး AniList ကို ရင်းမြစ်အဖြစ် ဖော်ပြပါ။",
        "သတိပြုရန်: AniList သည် community-assisted database ဖြစ်ပြီး Official Broadcaster Episode Guide မဟုတ်ပါ။ Season တစ်ခုချင်းစီ၏ Episode စာရင်းကို မဖော်ပြပါ။ Official Studio/Broadcaster Source နှင့် ပြန်စစ်ပါ။",
    ]
    return "\n".join(lines)
