"""Kitsu public anime catalogue integration (free read-only API)."""
import json
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://kitsu.io/api/edge/anime"
USER_AGENT = "NEXORA-Myanmar-Recap/2.1 (free catalogue research)"


def _norm(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _get_json(url):
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.api+json",
    })
    with urlopen(request, timeout=18) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_kitsu_anime(title):
    """Return a unique exact Kitsu title/alias match; never select a fuzzy result."""
    requested = " ".join(str(title or "").split()).strip()
    target = _norm(requested)
    if not target or len(requested) > 120:
        return {"found": False, "status": "Anime ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    try:
        params = urlencode({"filter[text]": requested, "page[limit]": 20})
        payload = _get_json(API_URL + "?" + params)
        records = payload.get("data", []) if isinstance(payload, dict) else []
        exact = []
        for record in records if isinstance(records, list) else []:
            attrs = record.get("attributes") or {}
            names = [
                attrs.get("canonicalTitle"),
                *(attrs.get("titles") or {}).values(),
                attrs.get("slug", "").replace("-", " "),
            ]
            if any(_norm(name) == target for name in names if name):
                exact.append((record, attrs))
        if len(exact) != 1:
            return {"found": False, "status": "Kitsu တွင် အမည်တိတိကျကျ ကိုက်ညီသော Anime တစ်ခုတည်းကို မသတ်မှတ်နိုင်ပါ။"}
        record, attrs = exact[0]
        age = str(attrs.get("ageRating") or "").upper()
        if age in {"R18", "R"}:
            return {"found": False, "status": "Kitsu မှ အရွယ်ရောက်သူများအတွက် သတ်မှတ်ထားသော Anime ကို ပယ်ချထားသည်။"}
        synopsis = re.sub(r"\s+", " ", str(attrs.get("synopsis") or "")).strip()
        if len(synopsis) < 60:
            return {"found": False, "status": "Kitsu မှာ အသုံးပြုနိုင်သော synopsis မလုံလောက်ပါ။"}
        start_date = str(attrs.get("startDate") or "")
        year = start_date[:4] if len(start_date) >= 4 else ""
        anime_id = str(record.get("id") or "")
        return {
            "found": True,
            "provider": "Kitsu (public read-only API)",
            "provider_url": f"https://kitsu.io/anime/{attrs.get('slug')}" if attrs.get("slug") else f"https://kitsu.io/anime/{anime_id}",
            "media_id": anime_id,
            "title": attrs.get("canonicalTitle") or requested,
            "format": attrs.get("subtype") or attrs.get("showType") or "",
            "episodes": attrs.get("episodeCount"),
            "year": year,
            "age_rating": age,
            "average_rating": attrs.get("averageRating"),
            "synopsis": synopsis[:3000],
            "scope": "series_overview_not_episode_plot",
            "notice": "Kitsu synopsis သည် series-level research lead သာဖြစ်ပြီး episode plot အပြည့် သို့မဟုတ် footage အသုံးပြုခွင့် မဟုတ်ပါ။",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
        return {"found": False, "status": "Kitsu အခမဲ့ catalogue ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}
