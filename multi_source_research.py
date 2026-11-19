"""Conservative multi-source anime metadata research for NEXORA.

AniList and Tenrai/MAL catalogue data are discovery leads, not verified episode
plots. Wikidata is used only for structured country/year cross-checks.
"""
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import re
import unicodedata

from anilist_synopsis import fetch_anilist_synopsis
from wikidata_metadata import fetch_wikidata_metadata

TENRAI_API = "https://api.tenrai.org/v1/anime"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0"


def _norm(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    value = re.sub(r"\s+\(\d{4}\)$", "", value)
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def fetch_tenrai_synopsis(title):
    """Fetch one exact, strict-SFW Tenrai/MAL catalogue match; never fuzzy-pick."""
    requested = " ".join(str(title or "").split()).strip()
    normalized = _norm(requested)
    if not normalized or len(requested) > 120:
        return {"found": False, "status": "Anime ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    params = urlencode({"q": requested, "limit": 10, "sfw-strict": "true"})
    request = Request(
        TENRAI_API + "?" + params,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=18) as response:
            payload = json.loads(response.read().decode("utf-8"))
        candidates = payload.get("data", []) if isinstance(payload, dict) else []
        exact = []
        for item in candidates:
            names = [
                item.get("title"), item.get("title_english"),
                item.get("title_japanese"),
            ] + list(item.get("title_synonyms") or [])
            if any(_norm(name) == normalized for name in names if name):
                exact.append(item)
        if len(exact) != 1:
            return {
                "found": False,
                "status": (
                    "Tenrai/MyAnimeList catalogue တွင် အမည်တိတိကျကျ ကိုက်ညီသော "
                    "Anime တစ်ခုတည်းကို မသတ်မှတ်နိုင်ပါ။"
                ),
            }
        item = exact[0]
        synopsis = re.sub(r"\s+", " ", str(item.get("synopsis") or "")).strip()
        if len(synopsis) < 60:
            return {"found": False, "status": "Tenrai မှာ အသုံးပြုနိုင်သော synopsis မလုံလောက်ပါ။"}
        aired = item.get("aired") or {}
        from_date = aired.get("from") or {}
        year = from_date.get("year") or item.get("year")
        mal_id = item.get("mal_id")
        return {
            "found": True,
            "provider": "Tenrai (unofficial MyAnimeList catalogue)",
            "provider_url": item.get("url") or (
                f"https://myanimelist.net/anime/{mal_id}" if mal_id else ""
            ),
            "media_id": mal_id,
            "title": item.get("title_english") or item.get("title") or requested,
            "format": item.get("type") or "",
            "episodes": item.get("episodes"),
            "year": str(year) if year else "",
            "synopsis": synopsis[:3500],
            "scope": "series_overview_not_episode_plot",
            "notice": (
                "Tenrai သည် MyAnimeList အများပြည်သူ catalog ကို ပေးသော unofficial "
                "ဝန်ဆောင်မှုဖြစ်သည်။ အချက်အလက်အမှား/ပြတ်တောက်မှု ဖြစ်နိုင်သည်။"
            ),
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
        return {"found": False, "status": "Tenrai ရင်းမြစ်ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}


def research_anime_sources(title):
    """Query AniList, Tenrai and Wikidata concurrently and report only exact matches."""
    clean = " ".join(str(title or "").split()).strip()
    if not clean or len(clean) > 120:
        return {"title": clean, "status": "ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    # Isolate provider failures: one unexpected exception must not discard
    # successful results from the other independent catalogues.
    def safe_fetch(fetcher, source_name):
        try:
            result = fetcher(clean)
            if isinstance(result, dict):
                return result
            return {"found": False, "status": source_name + " မှ မမှန်ကန်သော တုံ့ပြန်မှု ရရှိပါသည်။"}
        except Exception:
            return {"found": False, "status": source_name + " ရင်းမြစ်ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}

    with ThreadPoolExecutor(max_workers=3) as pool:
        anilist_future = pool.submit(safe_fetch, fetch_anilist_synopsis, "AniList")
        tenrai_future = pool.submit(safe_fetch, fetch_tenrai_synopsis, "Tenrai")
        wikidata_future = pool.submit(safe_fetch, fetch_wikidata_metadata, "Wikidata")
        anilist = anilist_future.result()
        tenrai = tenrai_future.result()
        wikidata = wikidata_future.result()

    country_values = (wikidata.get("countries") or []) if wikidata.get("found") else []
    country_code = str(anilist.get("country") or "").upper() if anilist.get("found") else ""
    country_text = " ".join(str(x) for x in country_values).casefold()
    india_flag = country_code == "IN" or "india" in country_text or "အိန္ဒိယ" in country_text
    if india_flag:
        eligibility = "ဒီ Project မှာ အိန္ဒိယမူရင်းခေါင်းစဉ်များကို မထည့်ပါ။"
    elif country_values or country_code:
        eligibility = "နိုင်ငံအချက်အလက် ရရှိသည်။ ထုတ်လုပ်သူ/တရားဝင်ရင်းမြစ်ဖြင့် ထပ်စစ်ရန် လိုအပ်သည်။"
    else:
        eligibility = "မူရင်းနိုင်ငံကို အတည်မပြုနိုင်သေးပါ။ အမျိုးအစား/နိုင်ငံကို မခန့်မှန်းပါနှင့်။"

    years = []
    for source in (anilist, tenrai, wikidata):
        year = str(source.get("year") or "").strip()
        if source.get("found") and year and year not in years:
            years.append(year)
    conflict = len(years) > 1
    return {
        "title": clean,
        "anilist": anilist,
        "tenrai": tenrai,
        "wikidata": wikidata,
        "eligibility": eligibility,
        "india_excluded": india_flag,
        "year_conflict": conflict,
        "years": years,
    }


def format_anime_source_report(report):
    """Format a transparent source-by-source report without inventing missing data."""
    lines = [
        "🔎 NEXORA Multi-Source Anime Research",
        "ခေါင်းစဉ်: " + (report.get("title") or "မရရှိပါ"),
        "",
    ]
    for key, label in (("anilist", "AniList"), ("tenrai", "Tenrai / MyAnimeList")):
        item = report.get(key) or {}
        lines.append("【" + label + "】")
        if item.get("found"):
            lines.extend([
                "အမည်: " + str(item.get("title") or "မရရှိပါ"),
                "Format: " + str(item.get("format") or "မရရှိပါ"),
                "ထုတ်လွှင့်နှစ်: " + str(item.get("year") or "မရရှိပါ"),
                "အပိုင်း: " + str(item.get("episodes") or "မရရှိပါ"),
                "Synopsis: " + str(item.get("synopsis") or "မရရှိပါ")[:1400],
                "Source: " + str(item.get("provider_url") or "မရရှိပါ"),
                str(item.get("notice") or ""),
            ])
        else:
            lines.append(str(item.get("status") or "ရင်းမြစ် မရရှိပါ။"))
        lines.append("")
    wd = report.get("wikidata") or {}
    lines.append("【Wikidata metadata cross-check】")
    if wd.get("found"):
        lines.extend([
            "နိုင်ငံ: " + (", ".join(wd.get("countries") or []) or "မရရှိပါ"),
            "နှစ်: " + str(wd.get("year") or "မရရှိပါ"),
            "အမျိုးအစား: " + (", ".join(wd.get("genres") or []) or "မရရှိပါ"),
            "Source: " + str(wd.get("source") or ""),
        ])
    else:
        lines.append(str(wd.get("status") or "Wikidata metadata မရရှိပါ။"))
    lines.extend(["", "စစ်ဆေးချက်: " + str(report.get("eligibility") or "မရရှိပါ")])
    if report.get("india_excluded"):
        lines.append("ရလဒ်: အိန္ဒိယမူရင်းဖြစ်ကြောင်း တွေ့ရှိသဖြင့် ဒီ Project အတွက် ပယ်ချထားသည်။")
    if report.get("year_conflict"):
        lines.append("သတိ: ရင်းမြစ်များတွင် နှစ်မတူညီပါ (" + ", ".join(report.get("years") or []) + ")။ လူကိုယ်တိုင် ပြန်စစ်ပါ။")
    lines.extend([
        "",
        "မှတ်ချက်: Synopsis များသည် series-level မိတ်ဆက်စာများသာဖြစ်ပြီး episode ဇာတ်ကွက်အပြည့် မဟုတ်ပါ။",
        "ဒီ report သည် research lead သာဖြစ်ပြီး /recapvideo အတွက် footage/license ခွင့်ပြုချက် မပေးပါ။",
    ])
    return "\n".join(lines)
