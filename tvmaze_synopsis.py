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
        payload = _get_json(API_URL + "/search/shows?q=" + quote(requested))
        exact = []
        target = _norm(requested)
        for result in payload if isinstance(payload, list) else []:
            show = result.get("show") or {}
            if _norm(show.get("name")) == target:
                exact.append(show)
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
