"""Kitsu public anime catalogue integration (free read-only API)."""
import json
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from animation_title_aliases import animation_title_match_names, animation_title_variants

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
        allowed_names = animation_title_match_names(requested)
        records_by_id = {}
        for term in animation_title_variants(requested):
            params = urlencode({"filter[text]": term, "page[limit]": 20})
            payload = _get_json(API_URL + "?" + params)
            records = payload.get("data", []) if isinstance(payload, dict) else []
            for record in records if isinstance(records, list) else []:
                if record.get("id") is not None:
                    records_by_id[str(record["id"])] = record
        exact = []
        for record in records_by_id.values():
            attrs = record.get("attributes") or {}
            names = [attrs.get("canonicalTitle"), *(attrs.get("titles") or {}).values(),
                     str(attrs.get("slug") or "").replace("-", " ")]
            if any(_norm(name) in allowed_names for name in names if name):
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



def fetch_kitsu_episode_summaries(title, limit=5):
    """Fetch short episode research excerpts for one exact Kitsu anime match."""
    requested = " ".join(str(title or "").split()).strip()
    target = _norm(requested)
    try:
        count = max(1, min(int(limit), 5))
    except (TypeError, ValueError):
        count = 5
    if not target or len(requested) > 120:
        return {"found": False, "status": "Anime ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    try:
        allowed_names = animation_title_match_names(requested)
        records_by_id = {}
        for term in animation_title_variants(requested):
            params = urlencode({
                "filter[text]": term,
                "include": "episodes",
                "page[limit]": 20,
            })
            payload = _get_json(API_URL + "?" + params)
            records = payload.get("data", []) if isinstance(payload, dict) else []
            for record in records if isinstance(records, list) else []:
                if record.get("id") is not None:
                    records_by_id[str(record["id"])] = record
        exact = []
        for record in records_by_id.values():
            attrs = record.get("attributes") or {}
            names = [attrs.get("canonicalTitle"), *(attrs.get("titles") or {}).values(),
                     str(attrs.get("slug") or "").replace("-", " ")]
            if any(_norm(name) in allowed_names for name in names if name):
                exact.append(record)
        if len(exact) != 1:
            return {"found": False, "status": "Kitsu တွင် အမည်တိတိကျကျ ကိုက်ညီသော Anime တစ်ခုတည်းကို မသတ်မှတ်နိုင်ပါ။"}
        selected = exact[0]
        selected_attrs = selected.get("attributes") or {}
        age = str(selected_attrs.get("ageRating") or "").upper()
        if age in {"R18", "R"}:
            return {"found": False, "status": "Kitsu မှ အရွယ်ရောက်သူများအတွက် သတ်မှတ်ထားသော Anime ကို ပယ်ချထားသည်။"}
        media_format = str(selected_attrs.get("subtype") or selected_attrs.get("showType") or "").upper()
        if media_format not in {"TV", "TV_SHORT", "ONA", "OVA"}:
            return {"found": False, "status": "Kitsu မှတ်တမ်းသည် TV/Animation Series မဟုတ်သဖြင့် Episode research အဖြစ် မသုံးထားပါ။"}
        relation = ((selected.get("relationships") or {}).get("episodes") or {}).get("data") or []
        allowed_ids = {str(item.get("id")) for item in relation if item.get("id") is not None}
        included = payload.get("included") or []
        episodes = []
        for item in included if isinstance(included, list) else []:
            if item.get("type") != "episodes" or str(item.get("id")) not in allowed_ids:
                continue
            attrs = item.get("attributes") or {}
            synopsis = re.sub(r"\s+", " ", str(attrs.get("synopsis") or attrs.get("description") or "")).strip()
            if len(synopsis) < 35:
                continue
            episodes.append({
                "season": attrs.get("seasonNumber"),
                "number": attrs.get("number"),
                "title": attrs.get("canonicalTitle") or "Untitled episode",
                "airdate": attrs.get("airDate") or "",
                "summary_excerpt": synopsis[:240],
                "source": f"https://kitsu.io/anime/{(selected.get('attributes') or {}).get('slug')}" if (selected.get("attributes") or {}).get("slug") else "https://kitsu.io/",
            })
        episodes.sort(key=lambda x: (
            x.get("season") if isinstance(x.get("season"), int) else 999,
            x.get("number") if isinstance(x.get("number"), int) else 999,
        ))
        if not episodes:
            return {"found": False, "status": "Kitsu တွင် ဖတ်ရှုနိုင်သော Episode synopsis မတွေ့ပါ။"}
        attrs = selected.get("attributes") or {}
        return {
            "found": True,
            "provider": "Kitsu",
            "title": attrs.get("canonicalTitle") or requested,
            "episodes": episodes[:count],
            "scope": "brief_episode_summary_excerpts",
            "notice": "Kitsu episode summaries are brief research excerpts, not a complete recap or verified scene transcript.",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
        return {"found": False, "status": "Kitsu Episode catalogue ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}
