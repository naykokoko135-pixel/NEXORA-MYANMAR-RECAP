"""Optional TMDB movie metadata cross-check for NEXORA.

TMDB requires a private API Read Access Token. Search excludes adult results
and exact-title/year matching fails closed when a unique record is unavailable.
"""
import json
import os
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from wikidata_metadata import fetch_wikidata_metadata

TMDB_API = "https://api.themoviedb.org/3"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0"


def _norm(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    value = re.sub(r"\s+\(\d{4}\)$", "", value)
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def _tmdb_get(path, params=None):
    token = os.getenv("TMDB_API_READ_ACCESS_TOKEN", "").strip()
    if not token:
        return None
    query = "?" + urlencode(params or {}) if params else ""
    request = Request(
        TMDB_API + path + query,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=18) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_tmdb_movie(title):
    """Return one exact, non-adult TMDB movie record; never select fuzzy results."""
    requested = " ".join(str(title or "").split()).strip()
    normalized = _norm(requested)
    if not normalized or len(requested) > 120:
        return {"found": False, "status": "ရုပ်ရှင်ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    if not os.getenv("TMDB_API_READ_ACCESS_TOKEN", "").strip():
        return {
            "found": False,
            "status": "TMDB API Read Access Token မချိတ်ရသေးပါ။ TMDB ရင်းမြစ်ကို ယခုမစစ်နိုင်ပါ။",
        }
    year_match = re.search(r"\((\d{4})\)$", requested)
    requested_year = year_match.group(1) if year_match else ""
    try:
        payload = _tmdb_get("/search/movie", {
            "query": requested,
            "include_adult": "false",
            "language": "en-US",
            "page": 1,
        }) or {}
        candidates = payload.get("results", [])
        exact = []
        for item in candidates:
            names = (item.get("title"), item.get("original_title"))
            if not any(_norm(name) == normalized for name in names if name):
                continue
            release_date = str(item.get("release_date") or "")
            year = release_date[:4] if len(release_date) >= 4 else ""
            if requested_year and year != requested_year:
                continue
            if item.get("adult") is True:
                continue
            exact.append(item)
        if len(exact) != 1:
            return {
                "found": False,
                "status": (
                    "TMDB တွင် အမည်တိတိကျကျကိုက်ညီသော ရုပ်ရှင်တစ်ကားတည်းကို "
                    "မသတ်မှတ်နိုင်ပါ။ ခုနှစ်ပါရှိလျှင် ခေါင်းစဉ်တွင် (YYYY) ထည့်ပါ။"
                ),
            }
        selected = exact[0]
        movie_id = selected.get("id")
        if not isinstance(movie_id, int) or movie_id <= 0:
            return {"found": False, "status": "TMDB ရုပ်ရှင် ID မမှန်ကန်ပါ။"}
        details = _tmdb_get(
            f"/movie/{movie_id}",
            {"language": "en-US", "append_to_response": "external_ids"},
        ) or {}
        if details.get("adult") is True:
            return {"found": False, "status": "ဒီ Project တွင် အရွယ်ရောက်သူများအတွက် သတ်မှတ်ထားသော ရုပ်ရှင်ကို မထည့်ပါ။"}
        release_date = str(details.get("release_date") or selected.get("release_date") or "")
        return {
            "found": True,
            "provider": "TMDB",
            "provider_url": f"https://www.themoviedb.org/movie/{movie_id}",
            "movie_id": movie_id,
            "title": details.get("title") or selected.get("title") or requested,
            "original_title": details.get("original_title") or selected.get("original_title") or "",
            "year": release_date[:4] if len(release_date) >= 4 else "",
            "original_language": details.get("original_language") or "",
            "countries": [
                str(item.get("name") or "").strip()
                for item in details.get("production_countries", [])
                if isinstance(item, dict) and item.get("name")
            ],
            "overview": re.sub(r"\s+", " ", str(details.get("overview") or selected.get("overview") or "")).strip()[:3000],
            "imdb_id": (details.get("external_ids") or {}).get("imdb_id") or "",
            "adult": False,
            "notice": "TMDB metadata သည် ဇာတ်လမ်းအကျဉ်း/metadata research lead သာဖြစ်ပြီး footage သုံးစွဲခွင့် မပေးပါ။",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
        return {"found": False, "status": "TMDB API ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}


def research_movie_sources(title):
    clean = " ".join(str(title or "").split()).strip()

    # Keep independent catalogue results even if one provider raises an
    # unexpected exception (for example, a changed response schema).
    def safe_fetch(fetcher, source_name):
        try:
            result = fetcher(clean)
            if isinstance(result, dict):
                return result
            return {
                "found": False,
                "status": source_name + " မှ မမှန်ကန်သော တုံ့ပြန်မှု ရရှိပါသည်။",
            }
        except Exception:
            return {
                "found": False,
                "status": source_name + " ရင်းမြစ်ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။",
            }

    tmdb = safe_fetch(fetch_tmdb_movie, "TMDB")
    wikidata = safe_fetch(fetch_wikidata_metadata, "Wikidata")
    tmdb_countries = tmdb.get("countries") or [] if tmdb.get("found") else []
    wd_countries = wikidata.get("countries") or [] if wikidata.get("found") else []
    combined = " ".join(str(x) for x in tmdb_countries + wd_countries).casefold()
    india_flag = "india" in combined or "အိန္ဒိယ" in combined
    years = []
    for source in (tmdb, wikidata):
        year = str(source.get("year") or "").strip()
        if source.get("found") and year and year not in years:
            years.append(year)
    if india_flag:
        eligibility = "အိန္ဒိယမူရင်း/ထုတ်လုပ်မှုပါဝင်ကြောင်း metadata တွေ့ရှိသဖြင့် ဒီ Project အတွက် ပယ်ချထားသည်။"
    elif tmdb_countries or wd_countries:
        eligibility = "ထုတ်လုပ်သည့်နိုင်ငံအချက်အလက် ရရှိသည်။ Co-production ပါဝင်မှုကို ပြန်စစ်ပါ။"
    else:
        eligibility = "မူရင်းနိုင်ငံကို အတည်မပြုနိုင်သေးပါ။ မခန့်မှန်းပါနှင့်။"
    return {
        "title": clean,
        "tmdb": tmdb,
        "wikidata": wikidata,
        "india_excluded": india_flag,
        "year_conflict": len(years) > 1,
        "years": years,
        "eligibility": eligibility,
    }


def format_movie_source_report(report):
    lines = [
        "🎬 NEXORA Multi-Source Movie Research",
        "ခေါင်းစဉ်: " + (report.get("title") or "မရရှိပါ"),
        "",
        "【TMDB】",
    ]
    tmdb = report.get("tmdb") or {}
    if tmdb.get("found"):
        lines.extend([
            "အမည်: " + str(tmdb.get("title") or "မရရှိပါ"),
            "မူရင်းအမည်: " + str(tmdb.get("original_title") or "မရရှိပါ"),
            "နှစ်: " + str(tmdb.get("year") or "မရရှိပါ"),
            "ဘာသာစကား: " + str(tmdb.get("original_language") or "မရရှိပါ"),
            "ထုတ်လုပ်သည့်နိုင်ငံ: " + (", ".join(tmdb.get("countries") or []) or "မရရှိပါ"),
            "ဇာတ်လမ်းအကျဉ်း: " + str(tmdb.get("overview") or "မရရှိပါ"),
            "IMDb ID (TMDB external link): " + str(tmdb.get("imdb_id") or "မရရှိပါ"),
            "Source: " + str(tmdb.get("provider_url") or ""),
            str(tmdb.get("notice") or ""),
        ])
    else:
        lines.append(str(tmdb.get("status") or "TMDB metadata မရရှိပါ။"))
    lines.extend(["", "【Wikidata】"])
    wd = report.get("wikidata") or {}
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
        lines.append("ရလဒ်: အိန္ဒိယမူရင်း/ထုတ်လုပ်မှုပါဝင်မှုကြောင့် ပယ်ချထားသည်။")
    if report.get("year_conflict"):
        lines.append("သတိ: ရင်းမြစ်နှစ်မတူညီပါ (" + ", ".join(report.get("years") or []) + ")။")
    lines.extend([
        "",
        "မှတ်ချက်: TMDB သည် free API use ကို non-commercial use အတွက်သာ ဖော်ပြထားပြီး commercial use အတွက် TMDB နှင့် ဆက်သွယ်ရန်လိုသည်။ Attribution လိုအပ်ချက်ကိုလည်း လိုက်နာပါ။",
        "IMDb ID သည် TMDB external link မှရရှိခြင်းသာဖြစ်ပြီး IMDb database ကို တိုက်ရိုက် query လုပ်ထားခြင်း မဟုတ်ပါ။",
        "ဒီ report သည် metadata research သာဖြစ်ပြီး ဇာတ်လမ်းအပြည့်၊ footage သုံးစွဲခွင့် သို့မဟုတ် video ထုတ်လုပ်ခွင့် မပေးပါ။",
    ])
    return "\n".join(lines)
