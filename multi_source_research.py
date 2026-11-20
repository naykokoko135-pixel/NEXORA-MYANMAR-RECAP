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
from free_catalogue_research import search_free_catalogue
from kitsu_anime_research import fetch_kitsu_anime
from animation_catalogue_research import research_animation_catalogues, format_animation_catalogue_report

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
    """Query AniList, Kitsu, Tenrai and Wikidata concurrently; keep exact matches only."""
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

    with ThreadPoolExecutor(max_workers=4) as pool:
        kitsu_future = pool.submit(safe_fetch, fetch_kitsu_anime, "Kitsu")
        anilist_future = pool.submit(safe_fetch, fetch_anilist_synopsis, "AniList")
        tenrai_future = pool.submit(safe_fetch, fetch_tenrai_synopsis, "Tenrai")
        wikidata_future = pool.submit(safe_fetch, fetch_wikidata_metadata, "Wikidata")
        kitsu = kitsu_future.result()
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
    for source in (anilist, kitsu, tenrai, wikidata):
        year = str(source.get("year") or "").strip()
        if source.get("found") and year and year not in years:
            years.append(year)
    conflict = len(years) > 1
    return {
        "title": clean,
        "anilist": anilist,
        "kitsu": kitsu,
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
    for key, label in (("anilist", "AniList"), ("kitsu", "Kitsu"), ("tenrai", "Tenrai / MyAnimeList")):
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


def research_all_media_sources(title):
    """Research a title across anime, general film, and TV-series catalogs."""
    from tmdb_movie_research import research_movie_sources
    from tvmaze_synopsis import fetch_tvmaze_synopsis

    clean = " ".join(str(title or "").split()).strip()
    if not clean or len(clean) > 120:
        return {"title": clean, "status": "ခေါင်းစဉ် မမှန်ကန်ပါ။"}

    def safe(fetcher, *args):
        try:
            value = fetcher(*args)
            return value if isinstance(value, dict) else {"found": False, "status": "ရင်းမြစ်မှ မမှန်ကန်သော တုံ့ပြန်မှု ရရှိပါသည်။"}
        except Exception:
            return {"found": False, "status": "ရင်းမြစ်ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}

    with ThreadPoolExecutor(max_workers=5) as pool:
        animation_catalogues_f = pool.submit(safe, research_animation_catalogues, clean)
        anime_f = pool.submit(safe, research_anime_sources, clean)
        movie_f = pool.submit(safe, research_movie_sources, clean)
        series_f = pool.submit(safe, fetch_tvmaze_synopsis, clean)
        free_f = pool.submit(safe, search_free_catalogue, clean)
        anime, movie, series, free_catalogue = anime_f.result(), movie_f.result(), series_f.result(), free_f.result()
    animation_catalogues = animation_catalogues_f.result()
    return {"title": clean, "anime": anime, "movie": movie, "series": series, "free_catalogue": free_catalogue, "animation_catalogues": animation_catalogues}


def format_all_media_source_report(report):
    """Display separate Anime, Movie and TV Series research tracks."""
    if report.get("status"):
        return str(report["status"])
    from tmdb_movie_research import format_movie_source_report

    lines = [
        "🔎 NEXORA Universal Multi-Source Research",
        "ခေါင်းစဉ်: " + str(report.get("title") or "မရရှိပါ"),
        "ရှာဖွေမှု: Anime / Animation, Movies, TV Series နှင့် Wikimedia public catalogue — သီးခြားစစ်ဆေးထားသည်။",
        "",
        "━━━━━━━━【 ANIME / ANIMATION 】━━━━━━━━",
        format_anime_source_report(report.get("anime") or {}),
        "",
        "━━━━━━━━【 CARTOON / DONGHUA / 3D ANIMATION CATALOGUES 】━━━━━━━━",
        format_animation_catalogue_report(report.get("animation_catalogues") or {}),
        "",
        "━━━━━━━━【 MOVIE / FILM 】━━━━━━━━",
        format_movie_source_report(report.get("movie") or {}),
        "",
        "━━━━━━━━【 TV SERIES 】━━━━━━━━",
    ]
    series = report.get("series") or {}
    if series.get("found"):
        lines.extend([
            "အမည်: " + str(series.get("title") or "မရရှိပါ"),
            "နိုင်ငံ: " + str(series.get("country") or "မရရှိပါ"),
            "ပထမဆုံးထုတ်လွှင့်ရက်: " + str(series.get("premiered") or "မရရှိပါ"),
            "အမျိုးအစား: " + (", ".join(series.get("genres") or []) or "မရရှိပါ"),
            "အခြေအနေ: " + str(series.get("status_label") or "မရရှိပါ"),
            "Synopsis: " + str(series.get("summary") or "မရရှိပါ")[:1400],
            "Source: " + str(series.get("provider_url") or ""),
            str(series.get("notice") or ""),
        ])
    else:
        lines.append(str(series.get("status") or "TVmaze ရင်းမြစ် မရရှိပါ။"))
    lines.extend(["", "━━━━━━━━【 FREE CROSS-CATEGORY DISCOVERY 】━━━━━━━━"])
    free = report.get("free_catalogue") or {}
    if free.get("found"):
        for index, item in enumerate(free.get("items") or [], start=1):
            lines.extend([f"{index}. {item.get('title') or 'Untitled'}", str(item.get('excerpt') or "")[:500], "Source: " + str(item.get("url") or "")])
    else:
        lines.append(str(free.get("status") or "Wikimedia public catalogue မရရှိပါ။"))
    lines.append("မှတ်ချက်: Wikimedia သည် Donghua၊ Cartoon၊ 3D Animation၊ Anime၊ ရုပ်ရှင်နှင့် စီးရီးများအတွက် cross-category discovery lead သာဖြစ်ပြီး သီးသန့် catalogue အပြည့်အစုံ မဟုတ်ပါ။")
    lines.extend([
        "",
        "မှတ်ချက်: Catalogue တစ်ခုတွင် မတွေ့ခြင်းသည် အခြား catalogue များတွင် မရှိကြောင်း မဆိုလိုပါ။",
        "ဒီ report သည် research lead သာဖြစ်ပြီး footage/license ခွင့်ပြုချက် မပေးပါ။",
    ])
    return "\n".join(lines)
