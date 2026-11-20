"""Exact-match TVMaze series overview research for cartoons and donghua.

The summary is a series-level introduction, not an episode plot. TVMaze data
is community-maintained and must be checked before any recap is published.
"""
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import quote
from urllib.request import Request, urlopen
import json

from animation_title_aliases import animation_title_match_names, animation_title_variants

API_URL = "https://api.tvmaze.com"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0"


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _plain(value):
    parser = _Text()
    parser.feed(str(value or ""))
    return re.sub(r"\s+", " ", unescape("".join(parser.parts))).strip()


def _norm(value):
    value = re.sub(r"\s*\([^)]*\)\s*$", "", str(value or "").casefold())
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _get_json(url):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_tvmaze_synopsis(title):
    """Return one exact title match only; never choose a fuzzy TVMaze result."""
    requested = " ".join(str(title or "").split()).strip()
    if not requested or len(requested) > 120:
        return {"found": False, "status": "ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    try:
        allowed_names = animation_title_match_names(requested)
        shows_by_id = {}
        for term in animation_title_variants(requested):
            payload = _get_json(API_URL + "/search/shows?q=" + quote(term))
            for result in payload if isinstance(payload, list) else []:
                show = result.get("show") or {}
                if show.get("id") is not None:
                    shows_by_id[str(show["id"])] = show
        exact = [show for show in shows_by_id.values()
                 if _norm(show.get("name")) in allowed_names]
        if len(exact) != 1:
            return {
                "found": False,
                "status": "TVmaze တွင် အမည်တိတိကျကျ ကိုက်ညီသော Series တစ်ခုတည်းကို မသတ်မှတ်နိုင်ပါ။",
            }
        show = exact[0]
        country = (
            (show.get("network") or {}).get("country") or
            (show.get("webChannel") or {}).get("country") or {}
        )
        country_name = country.get("name") or ""
        if not country_name:
            return {"found": False, "status": "မူရင်းနိုင်ငံအချက်အလက် မရှိသဖြင့် အိန္ဒိယမဟုတ်ကြောင်း မအတည်ပြုနိုင်ပါ။"}
        if country_name.casefold() in {"india", "republic of india"}:
            return {"found": False, "status": "ဒီ Project မှာ အိန္ဒိယခေါင်းစဉ်များ မထည့်ထားပါ။"}
        summary = _plain(show.get("summary"))
        if len(summary) < 80:
            return {"found": False, "status": "TVmaze မှာ အသုံးပြုနိုင်သော Series မိတ်ဆက်စာ မလုံလောက်ပါ။"}
        return {
            "found": True,
            "provider": "TVmaze",
            "provider_url": show.get("url") or "",
            "tvmaze_id": show.get("id"),
            "title": show.get("name") or requested,
            "genres": show.get("genres") or [],
            "premiered": show.get("premiered") or "",
            "status_label": show.get("status") or "",
            "country": country_name,
            "summary": summary[:3000],
            "scope": "series_overview_not_episode_plot",
            "notice": "TVmaze summary သည် Series မိတ်ဆက်စာသာဖြစ်ပြီး Episode တစ်ခုချင်း ဇာတ်ကွက်မဟုတ်ပါ။",
        }
    except Exception:
        return {"found": False, "status": "TVmaze ရင်းမြစ်ကို ယခုချိတ်ဆက်မရပါ။"}


def fetch_tvmaze_episode_summaries(title, limit=5):
    """Return brief episode-summary research leads for one exact animated series.

    Each provider summary is excerpted to 240 characters maximum. This is
    research material, not a generated recap script or verified scene transcript.
    """
    requested = " ".join(str(title or "").split()).strip()
    try:
        count = int(limit)
    except (TypeError, ValueError):
        count = 5
    count = max(1, min(count, 5))
    if not requested or len(requested) > 120:
        return {"found": False, "status": "ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    try:
        allowed_names = animation_title_match_names(requested)
        shows_by_id = {}
        for term in animation_title_variants(requested):
            payload = _get_json(API_URL + "/search/shows?q=" + quote(term))
            for item in payload if isinstance(payload, list) else []:
                show = item.get("show") or {}
                if show.get("id") is not None:
                    shows_by_id[str(show["id"])] = show
        exact = [show for show in shows_by_id.values()
                 if _norm(show.get("name")) in allowed_names]
        if len(exact) != 1:
            return {"found": False, "status": "TVmaze တွင် အမည်တိတိကျကျ ကိုက်ညီသော Series တစ်ခုတည်းကို မသတ်မှတ်နိုင်ပါ။"}
        show = exact[0]
        genres = [str(x).casefold() for x in show.get("genres", [])]
        if "animation" not in genres:
            return {"found": False, "status": "TVmaze မှာ Animation genre အဖြစ် အတည်မပြုနိုင်ပါ။"}
        country = (
            (show.get("network") or {}).get("country") or
            (show.get("webChannel") or {}).get("country") or {}
        )
        country_name = country.get("name") or ""
        if not country_name:
            return {"found": False, "status": "မူရင်းနိုင်ငံအချက်အလက် မရှိသဖြင့် ရပ်ထားပါတယ်။"}
        if country_name.casefold() in {"india", "republic of india"}:
            return {"found": False, "status": "ဒီ Project မှာ အိန္ဒိယခေါင်းစဉ်များ မထည့်ထားပါ။"}
        show_id = show.get("id")
        if not isinstance(show_id, int):
            return {"found": False, "status": "TVmaze Series ID မရရှိပါ။"}
        episodes = _get_json(f"{API_URL}/shows/{show_id}/episodes")
        results = []
        for episode in episodes if isinstance(episodes, list) else []:
            summary = _plain(episode.get("summary"))
            if len(summary) < 40:
                continue
            results.append({
                "season": episode.get("season"),
                "number": episode.get("number"),
                "title": episode.get("name") or "Untitled episode",
                "airdate": episode.get("airdate") or "",
                "summary_excerpt": summary[:240],
                "source": episode.get("url") or show.get("url") or "",
            })
            if len(results) >= count:
                break
        if not results:
            return {"found": False, "status": "TVmaze မှာ အသုံးပြုနိုင်သော Episode summary မတွေ့ပါ။"}
        return {
            "found": True,
            "provider": "TVmaze",
            "title": show.get("name") or requested,
            "country": country_name,
            "provider_url": show.get("url") or "",
            "episodes": results,
            "scope": "brief_episode_summary_excerpts",
            "notice": "TVmaze episode summaries are brief research excerpts, not a full recap script.",
        }
    except Exception:
        return {"found": False, "status": "TVmaze Episode ရင်းမြစ်ကို ယခုချိတ်ဆက်မရပါ။"}


def fetch_tvmaze_top_rated_episodes(title, limit=5):
    """Return the highest-rated episodes for one exact, non-Indian animated series.

    TVmaze episode ratings are community ratings, not view counts or a measure
    of popularity. Missing ratings are omitted rather than guessed.
    """
    requested = " ".join(str(title or "").split()).strip()
    try:
        count = int(limit)
    except (TypeError, ValueError):
        count = 5
    count = max(1, min(count, 10))
    if not requested or len(requested) > 120:
        return {"found": False, "status": "ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    try:
        payload = _get_json(API_URL + "/search/shows?q=" + quote(requested))
        target = _norm(requested)
        exact = [
            (item.get("show") or {})
            for item in payload if isinstance(payload, list)
            if _norm((item.get("show") or {}).get("name")) == target
        ]
        if len(exact) != 1:
            return {"found": False, "status": "TVmaze တွင် အမည်တိတိကျကျ ကိုက်ညီသော Series တစ်ခုတည်းကို မသတ်မှတ်နိုင်ပါ။"}
        show = exact[0]
        genres = [str(x).casefold() for x in show.get("genres", [])]
        if "animation" not in genres:
            return {"found": False, "status": "TVmaze မှာ Animation genre အဖြစ် အတည်မပြုနိုင်ပါ။"}
        country = (
            (show.get("network") or {}).get("country") or
            (show.get("webChannel") or {}).get("country") or {}
        )
        country_name = country.get("name") or ""
        if not country_name:
            return {"found": False, "status": "မူရင်းနိုင်ငံအချက်အလက် မရှိသဖြင့် ရပ်ထားပါတယ်။"}
        if country_name.casefold() in {"india", "republic of india"}:
            return {"found": False, "status": "ဒီ Project မှာ အိန္ဒိယခေါင်းစဉ်များ မထည့်ထားပါ။"}
        show_id = show.get("id")
        if not isinstance(show_id, int):
            return {"found": False, "status": "TVmaze Series ID မရရှိပါ။"}
        episodes = _get_json(f"{API_URL}/shows/{show_id}/episodes")
        rated = []
        for episode in episodes if isinstance(episodes, list) else []:
            rating = (episode.get("rating") or {}).get("average")
            if isinstance(rating, (int, float)) and not isinstance(rating, bool) and 0 < rating <= 10:
                rated.append({
                    "season": episode.get("season"),
                    "number": episode.get("number"),
                    "title": episode.get("name") or "Untitled episode",
                    "airdate": episode.get("airdate") or "",
                    "rating": float(rating),
                    "source": episode.get("url") or show.get("url") or "",
                    "summary_excerpt": _plain(episode.get("summary"))[:240],
                })
        rated.sort(key=lambda item: (-item["rating"], item["season"] or 999, item["number"] or 999))
        if not rated:
            return {"found": False, "status": "TVmaze မှာ အသုံးပြုနိုင်သော Episode rating မရှိပါ။"}
        return {
            "found": True,
            "provider": "TVmaze",
            "title": show.get("name") or requested,
            "country": country_name,
            "provider_url": show.get("url") or "",
            "episodes": rated[:count],
            "scope": "highest_rated_episodes_not_popularity",
            "notice": "TVmaze community episode ratings are not view counts or popularity rankings.",
        }
    except Exception:
        return {"found": False, "status": "TVmaze Episode rating ရင်းမြစ်ကို ယခုချိတ်ဆက်မရပါ။"}
