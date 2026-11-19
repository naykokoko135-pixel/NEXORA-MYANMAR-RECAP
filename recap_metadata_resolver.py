"""Resolve recap metadata through multiple catalogues with strict exact-match rules.

Wikidata remains the first structured source. When it cannot identify a title,
NEXORA may fall back to an exact TMDB movie result or an exact AniList/Tenrai
anime result. A provider match must include a known non-Indian country; missing
or conflicting identity data never gets guessed. These sources provide
metadata leads only, not footage rights or episode-level plot verification.
"""
from wikidata_metadata import fetch_wikidata_metadata
from tmdb_movie_research import fetch_tmdb_movie
from multi_source_research import research_anime_sources
import re

COUNTRY_NAMES = {
    "JP": "Japan",
    "CN": "China",
    "KR": "South Korea",
    "TW": "Taiwan",
    "US": "United States",
    "GB": "United Kingdom",
    "FR": "France",
    "DE": "Germany",
    "CA": "Canada",
    "AU": "Australia",
}


def _is_indian(countries):
    return any(
        str(country).strip().casefold() in {"india", "republic of india", "အိန္ဒိယ"}
        for country in (countries or [])
    )


def resolve_recap_metadata(title):
    """Return one exact-match metadata record, preferring Wikidata then alternatives."""
    clean = " ".join(str(title or "").split()).strip()
    if not clean or len(clean) > 120:
        return {"found": False, "status": "ခေါင်းစဉ် မမှန်ကန်ပါ။"}

    wikidata = fetch_wikidata_metadata(clean)
    if wikidata.get("found"):
        return {**wikidata, "provider": "Wikidata"}

    # TMDB is used only when its private read token is configured. It applies
    # exact title and optional year matching and excludes adult results.
    tmdb = fetch_tmdb_movie(clean)
    if tmdb.get("found"):
        countries = tmdb.get("countries") or []
        if _is_indian(countries):
            return {"found": False, "status": "အိန္ဒိယမူရင်း/ပူးတွဲထုတ်လုပ်မှု ဖြစ်ကြောင်း TMDB တွင်တွေ့ရှိသဖြင့် ပယ်ချထားသည်။"}
        if not countries:
            return {"found": False, "status": "TMDB မှတ်တမ်းရှိသော်လည်း မူရင်းနိုင်ငံ မရရှိပါ။ မခန့်မှန်းထားပါ။"}
        return {
            "found": True,
            "provider": "TMDB",
            "title": tmdb.get("title") or clean,
            "title_my": tmdb.get("title") or clean,
            "description": "movie",
            "countries": countries,
            "year": tmdb.get("year") or None,
            "source": tmdb.get("provider_url") or "",
            "enwiki_title": "",
            "mywiki_title": "",
            "tmdb_overview": tmdb.get("overview") or "",
            "imdb_id": tmdb.get("imdb_id") or "",
        }

    # AniList/Tenrai are no-key catalogue sources for animation. Accept only
    # exact catalogue matches with a recognized country code and reject India.
    anime = research_anime_sources(clean)
    if anime.get("india_excluded"):
        return {"found": False, "status": "ဒီ Project မှာ အိန္ဒိယမူရင်းခေါင်းစဉ်များကို မထည့်ပါ။"}
    if anime.get("year_conflict"):
        return {
            "found": False,
            "status": "Anime ရင်းမြစ်များ၏ ထုတ်ဝေသည့်နှစ် မကိုက်ညီပါ။ အတည်မပြုဘဲ ရပ်ထားပါတယ်။",
        }

    requested_year_match = re.search(r"\((\d{4})\)$", clean)
    requested_year = requested_year_match.group(1) if requested_year_match else ""

    anilist = anime.get("anilist") or {}
    tenrai = anime.get("tenrai") or {}
    selected = anilist if anilist.get("found") else tenrai if tenrai.get("found") else {}
    if selected:
        selected_year = str(selected.get("year") or "").strip()
        if requested_year and selected_year != requested_year:
            return {
                "found": False,
                "status": (
                    f"ခေါင်းစဉ်တွင် {requested_year} ဟု တောင်းဆိုထားသော်လည်း "
                    f"Anime ရင်းမြစ်၏နှစ် ({selected_year or 'မရရှိပါ'}) မကိုက်ညီပါ။"
                ),
            }
        country_code = str(anilist.get("country") or "").upper()
        if country_code == "IN":
            return {"found": False, "status": "ဒီ Project မှာ အိန္ဒိယမူရင်းခေါင်းစဉ်များကို မထည့်ပါ။"}
        countries = [COUNTRY_NAMES[country_code]] if country_code in COUNTRY_NAMES else []
        wd = anime.get("wikidata") or {}
        if not countries and wd.get("found"):
            countries = wd.get("countries") or []
        if not countries:
            return {"found": False, "status": "Anime catalogue မှတ်တမ်းရှိသော်လည်း မူရင်းနိုင်ငံကို အတည်မပြုနိုင်ပါ။"}
        if _is_indian(countries):
            return {"found": False, "status": "ဒီ Project မှာ အိန္ဒိယမူရင်းခေါင်းစဉ်များကို မထည့်ပါ။"}
        return {
            "found": True,
            "provider": selected.get("provider") or "AniList/Tenrai",
            "title": selected.get("title") or clean,
            "title_my": "",
            "description": selected.get("format") or "anime",
            "countries": countries,
            "year": str(selected.get("year") or "") or None,
            "source": selected.get("provider_url") or "",
            "enwiki_title": "",
            "mywiki_title": "",
            "anime_synopsis": selected.get("synopsis") or "",
        }

    statuses = [
        wikidata.get("status") or "Wikidata match မရရှိပါ။",
        tmdb.get("status") or "TMDB match မရရှိပါ။",
        anilist.get("status") or "AniList match မရရှိပါ။",
        tenrai.get("status") or "Tenrai match မရရှိပါ။",
    ]
    return {
        "found": False,
        "status": "အခြား metadata ရင်းမြစ်များဖြင့်လည်း အတိအကျ အတည်မပြုနိုင်ပါ။ မခန့်မှန်းဘဲ ရပ်ထားပါတယ်။",
        "provider_statuses": statuses,
    }
