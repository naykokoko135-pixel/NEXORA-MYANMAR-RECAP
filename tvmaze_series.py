"""Free TVmaze series and episode metadata lookup.

TVmaze's public API is keyless and licensed CC BY-SA 4.0, requiring attribution and ShareAlike compliance. This module provides
catalogue metadata only; it is not an official broadcaster episode guide.
"""
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://api.tvmaze.com"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0 (https://github.com/naykokoko135-pixel/NEXORA-MYANMAR-RECAP)"
MAX_EXAMPLE_EPISODES = 4


def _normalize_title(value):
    value = str(value or "").casefold().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _request_json(url):
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    for attempt in range(2):
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            # TVmaze documents HTTP 429 and recommends backing off briefly.
            # Retry only once, and cap server-provided delays to keep bot runs bounded.
            if exc.code != 429 or attempt != 0:
                raise
            try:
                retry_after = float(exc.headers.get("Retry-After", "1"))
            except (TypeError, ValueError):
                retry_after = 1.0
            time.sleep(max(0.0, min(retry_after, 2.0)))
    raise RuntimeError("TVmaze request retry exhausted.")


def fetch_series_episode_guide(title):
    """Return exact-title TVmaze series metadata or a transparent unavailable status."""
    clean_title = " ".join((title or "").split()).strip()
    if not clean_title or len(clean_title) > 120:
        return {"found": False, "status": "ဇာတ်လမ်းတွဲခေါင်းစဉ် မမှန်ကန်ပါ။"}

    try:
        query = urlencode({"q": clean_title})
        search_payload = _request_json(API_URL + "/search/shows?" + query)
        exact = [
            item.get("show", {})
            for item in search_payload
            if _normalize_title(item.get("show", {}).get("name", "")) == _normalize_title(clean_title)
        ]
        if not exact:
            return {
                "found": False,
                "status": "TVmaze တွင် ခေါင်းစဉ်အတိအကျ မတွေ့ပါ။ အခြား Official Episode Guide ဖြင့် စစ်ဆေးရန်လိုသည်။",
            }

        # Do not silently select between duplicate exact-name shows.
        unique = {item.get("id"): item for item in exact if item.get("id") is not None}
        if len(unique) != 1:
            return {
                "found": False,
                "status": "အမည်တူ ဇာတ်လမ်းတွဲများစွာရှိ၍ မှန်ကန်သည့် version ကို အလိုအလျောက် မရွေးထားပါ။",
            }

        show = next(iter(unique.values()))
        show_id = show["id"]
        episodes = _request_json(f"{API_URL}/shows/{show_id}/episodes")
        if not isinstance(episodes, list):
            return {"found": False, "status": "TVmaze Episode စာရင်းပုံစံ မမှန်ကန်ပါ။"}

        seasons = {}
        specials = 0
        valid_episode_count = 0
        examples = []
        for episode in episodes:
            if not isinstance(episode, dict) or not isinstance(episode.get("number"), int):
                continue
            season = episode.get("season")
            if not isinstance(season, int):
                continue
            valid_episode_count += 1
            if season <= 0:
                specials += 1
            else:
                seasons[season] = seasons.get(season, 0) + 1
            if len(examples) < MAX_EXAMPLE_EPISODES and season > 0:
                examples.append({
                    "season": season,
                    "episode": episode["number"],
                    "name": episode.get("name") or "ခေါင်းစဉ်မရရှိပါ",
                    "airdate": episode.get("airdate") or "မရရှိပါ",
                })

        if not valid_episode_count:
            status = "ဇာတ်လမ်းတွဲကို တွေ့သော်လည်း Episode အချက်အလက် မရရှိပါ။"
        else:
            status = "TVmaze မှတ်တမ်းရရှိပါပြီ။ ထုတ်လွှင့်သူ၏ Official Episode Guide နှင့် ထပ်မံတိုက်စစ်ပါ။"

        return {
            "found": bool(valid_episode_count),
            "title": show.get("name", clean_title),
            "show_id": show_id,
            "show_type": show.get("type") or "မရရှိပါ",
            "status": show.get("status") or "မရရှိပါ",
            "premiered": show.get("premiered") or "မရရှိပါ",
            "ended": show.get("ended") or "မရရှိပါ",
            "network": (show.get("network") or {}).get("name")
                       or (show.get("webChannel") or {}).get("name")
                       or "မရရှိပါ",
            "season_count": len(seasons),
            "episode_count": sum(seasons.values()),
            "special_count": specials,
            "seasons": dict(sorted(seasons.items())),
            "examples": examples,
            "source": f"https://www.tvmaze.com/shows/{show_id}",
            "episodes_source": f"https://www.tvmaze.com/shows/{show_id}/episodes",
            "status_note": status,
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
        return {
            "found": False,
            "status": "TVmaze API ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။ Episode အရေအတွက်ကို မခန့်မှန်းထားပါ။",
        }


def format_series_episode_guide(result):
    """Format a compact, attributed episode guide for Telegram."""
    if not result or not result.get("found"):
        status = (result or {}).get("status", "Episode အချက်အလက် မရရှိပါ။")
        return "📺 Season / Episode စစ်ဆေးမှု\n" + status

    lines = [
        "📺 Season / Episode စစ်ဆေးမှု (TVmaze)",
        "ခေါင်းစဉ်: " + result.get("title", "မရရှိပါ"),
        "ထုတ်လွှင့်မှုအခြေအနေ: " + result.get("status", "မရရှိပါ"),
        "ပထမဆုံးထုတ်လွှင့်ရက်: " + result.get("premiered", "မရရှိပါ"),
        "နောက်ဆုံးထုတ်လွှင့်ရက်: " + result.get("ended", "မရရှိပါ"),
        "Network / Web Channel: " + result.get("network", "မရရှိပါ"),
        "Season အရေအတွက်: " + str(result.get("season_count", 0)),
        "စာရင်းတွင်ပါသော Episode အရေအတွက်: " + str(result.get("episode_count", 0)),
        "Special Episode: " + str(result.get("special_count", 0)),
    ]
    for season, count in result.get("seasons", {}).items():
        lines.append(f"Season {season}: {count} Episodes")
    examples = result.get("examples", [])
    if examples:
        lines.append("Episode နမူနာ:")
        for episode in examples:
            lines.append(
                f"- S{episode['season']}E{episode['episode']}: {episode['name']} "
                f"({episode['airdate']})"
            )
    lines.extend([
        "Show Source: " + result.get("source", ""),
        "Episode Guide: " + result.get("episodes_source", ""),
        "အခြေအနေ: " + result.get("status_note", "ထပ်မံစစ်ဆေးရန်"),
        "လိုင်စင်မှတ်ချက်: TVmaze ဒေတာသည် CC BY-SA 4.0 ဖြစ်သည်။ TVmaze ကို ရင်းမြစ်အဖြစ် ဖော်ပြပြီး ShareAlike စည်းကမ်းကို လိုက်နာပါ။",
        "သတိပြုရန်: TVmaze စာရင်းသည် တရားဝင်ထုတ်လွှင့်သူ၏ အတည်ပြုချက် မဟုတ်ပါ။ Season/Episode အရေအတွက်ကို Official Guide နှင့် ပြန်စစ်ပါ။",
    ])
    return "\n".join(lines)
