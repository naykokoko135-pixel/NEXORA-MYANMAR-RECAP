"""Bangumi public API fallback for animation episode metadata.

The endpoint exposes community-maintained episode names, numbers, dates and
optional descriptions. Missing descriptions are never synthesized.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from animation_title_aliases import (
    animation_title_match_names, animation_title_variants, normalize_animation_title,
)

SEARCH_URL = "https://api.bgm.tv/v0/search/subjects"
EPISODES_URL = "https://api.bgm.tv/v0/episodes"
USER_AGENT = "NEXORA-Myanmar-Recap/2.2 (free episode research)"


def _norm(value):
    return normalize_animation_title(value)


def _post_json(url, payload):
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=18) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url):
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    with urlopen(request, timeout=18) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bangumi_episode_summaries(title, limit=5):
    """Find one exact, non-NSFW animation subject and return main-story episodes."""
    requested = " ".join(str(title or "").split()).strip()
    if not requested or len(requested) > 120:
        return {"found": False, "status": "Bangumi ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    try:
        allowed = animation_title_match_names(requested)
        subjects = {}
        for variant in animation_title_variants(requested):
            payload = _post_json(SEARCH_URL + "?limit=20&offset=0", {
                "keyword": variant,
                "sort": "match",
                "filter": {"type": [2], "nsfw": False},
            })
            records = payload.get("data", []) if isinstance(payload, dict) else []
            for item in records if isinstance(records, list) else []:
                if not isinstance(item, dict) or item.get("type") != 2 or item.get("nsfw") is True:
                    continue
                if any(_norm(name) in allowed for name in (item.get("name"), item.get("name_cn")) if name):
                    if item.get("id") is not None:
                        subjects[str(item["id"])] = item
        if len(subjects) != 1:
            return {
                "found": False,
                "status": (
                    "Bangumi တွင် ခေါင်းစဉ်တိတိကျကျ ကိုက်ညီသော Animation Series တစ်ခုတည်း "
                    "မသတ်မှတ်နိုင်ပါ။"
                ),
            }

        subject = next(iter(subjects.values()))
        subject_id = subject["id"]
        query = urlencode({"subject_id": subject_id, "type": 0, "limit": 100, "offset": 0})
        payload = _get_json(EPISODES_URL + "?" + query)
        records = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(records, list) or not records:
            return {"found": False, "status": "Bangumi မှ Main Story Episode စာရင်း မရရှိပါ။"}

        episodes = []
        for item in records:
            if not isinstance(item, dict) or item.get("type") != 0:
                continue
            number = item.get("ep")
            if number is None:
                number = item.get("sort")
            title_text = item.get("name_cn") or item.get("name") or ""
            if not title_text and number is None:
                continue
            desc = re.sub(r"\\s+", " ", str(item.get("desc") or "")).strip()
            episode_id = item.get("id")
            episode = {
                "season": None,
                "number": number,
                "title": title_text or f"Episode {number}",
                "airdate": item.get("airdate") or "",
                "source": f"https://bgm.tv/ep/{episode_id}" if episode_id else f"https://bgm.tv/subject/{subject_id}",
            }
            if desc:
                episode["summary_excerpt"] = desc[:240]
            episodes.append(episode)

        episodes.sort(key=lambda ep: (
            float(ep.get("number")) if str(ep.get("number") or "").replace(".", "", 1).isdigit() else 999999,
            ep.get("title", ""),
        ))
        episodes = episodes[:max(1, min(int(limit), 10))]
        if not episodes:
            return {"found": False, "status": "Bangumi မှ အသုံးပြုနိုင်သော Main Story Episode မတွေ့ပါ။"}
        return {
            "found": True,
            "title": subject.get("name_cn") or subject.get("name") or requested,
            "episodes": episodes,
            "country": "",
            "provider": "Bangumi",
            "provider_url": f"https://bgm.tv/subject/{subject_id}",
            "scope": "episode_metadata_with_optional_community_descriptions",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
        return {"found": False, "status": "Bangumi public Episode API ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}
