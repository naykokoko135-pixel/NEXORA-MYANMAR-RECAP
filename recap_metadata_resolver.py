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


def _wikidata_describes_film(metadata):
    """Only cross-check a Wikidata film item against TMDB's movie catalogue."""
    metadata = metadata or {}
    # Search may resolve an exact Burmese/Japanese label whose localized
    # description does not contain the English words "film" or "movie".
    # Prefer explicit English description as an additional classification
    # signal; remain conservative if neither description identifies a film.
    descriptions = " ".join(
        str(metadata.get(key) or "")
        for key in ("description", "description_en")
    ).casefold()
    return "film" in descriptions or "movie" in descriptions


def _has_exact_anime_record(report):
    report = report or {}
    return any(
        (report.get(key) or {}).get("found")
        for key in ("anilist", "tenrai")
    )


def resolve_recap_metadata(title):
    """Return one exact-match metadata record, preferring Wikidata then alternatives."""
    clean = " ".join(str(title or "").split()).strip()
    if not clean or len(clean) > 120:
        return {"found": False, "status": "ခေါင်းစဉ် မမှန်ကန်ပါ။"}

    # Each catalogue is independent. A provider outage or unexpected schema
    # error must not prevent the resolver from consulting the other sources.
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

    wikidata = safe_fetch(fetch_wikidata_metadata, "Wikidata")
    anime = None

    # TMDB's /search/movie endpoint is a movie-only catalogue. Do not let a
    # same-named film result overwrite a Wikidata-identified TV/anime series.
    # When Wikidata has no exact record, check anime catalogues too before
    # accepting a TMDB movie so cross-category title collisions fail closed.
    should_query_tmdb = (
        not wikidata.get("found") or _wikidata_describes_film(wikidata)
    )
    tmdb = safe_fetch(fetch_tmdb_movie, "TMDB") if should_query_tmdb else {
        "found": False, "status": "Wikidata က ရုပ်ရှင်မဟုတ်သော screen work အဖြစ် ခွဲခြားထားသဖြင့် TMDB movie lookup ကို ကျော်ထားသည်။"
    }
    if tmdb.get("found") and _is_indian(tmdb.get("countries") or []):
        return {"found": False, "status": "အိန္ဒိယမူရင်း/ပူးတွဲထုတ်လုပ်မှု ဖြစ်ကြောင်း TMDB တွင်တွေ့ရှိသဖြင့် ပယ်ချထားသည်။"}
    if tmdb.get("found") and not wikidata.get("found"):
        anime = safe_fetch(research_anime_sources, "Anime catalogue")
        if anime.get("india_excluded"):
            return {"found": False, "status": "ဒီ Project မှာ အိန္ဒိယမူရင်းခေါင်းစဉ်များကို မထည့်ပါ။"}
        if _has_exact_anime_record(anime):
            return {
                "found": False,
                "status": "ဒီခေါင်းစဉ်သည် TMDB ရုပ်ရှင်နှင့် Anime catalogue နှစ်ခုလုံးတွင် အတိအကျတွေ့ရသည်။ အမျိုးအစားမသေချာသဖြင့် မရွေးချယ်ထားပါ။ ခေါင်းစဉ်နှင့် ခုနှစ်/အမျိုးအစားကို ပြန်စစ်ပါ။",
            }
    if tmdb.get("found"):
        countries = tmdb.get("countries") or []
        wikidata_countries = wikidata.get("countries") or [] if wikidata.get("found") else []
        tmdb_year = str(tmdb.get("year") or "").strip()
        wikidata_year = str(wikidata.get("year") or "").strip() if wikidata.get("found") else ""
        # If two independent catalogues both identify the work, reject material
        # conflicts instead of silently preferring one provider.
        if tmdb_year and wikidata_year and tmdb_year != wikidata_year:
            return {
                "found": False,
                "status": (
                    f"TMDB နှစ် ({tmdb_year}) နဲ့ Wikidata နှစ် ({wikidata_year}) "
                    "မကိုက်ညီပါ။ ရင်းမြစ်ကို လူကိုယ်တိုင် ပြန်စစ်ရန်လိုပါတယ်။"
                ),
            }
        if _is_indian(countries) or _is_indian(wikidata_countries):
            return {"found": False, "status": "အိန္ဒိယမူရင်း/ပူးတွဲထုတ်လုပ်မှု ဖြစ်ကြောင်း TMDB တွင်တွေ့ရှိသဖြင့် ပယ်ချထားသည်။"}
        if not countries:
            return {"found": False, "status": "TMDB မှတ်တမ်းရှိသော်လည်း မူရင်းနိုင်ငံ မရရှိပါ။ မခန့်မှန်းထားပါ။"}
        if wikidata_countries:
            tmdb_set = {x.strip().casefold() for x in countries if x.strip()}
            wikidata_set = {x.strip().casefold() for x in wikidata_countries if x.strip()}
            if tmdb_set.isdisjoint(wikidata_set):
                return {
                    "found": False,
                    "status": "TMDB နဲ့ Wikidata တို့၏ ထုတ်လုပ်/မူရင်းနိုင်ငံ အချက်အလက် မတူညီပါ။ လူကိုယ်တိုင် ပြန်စစ်ရန်လိုပါတယ်။",
                }
        return {
            "found": True,
            "provider": "TMDB + Wikidata" if wikidata.get("found") else "TMDB",
            "metadata_source": "TMDB",
            "metadata_confidence": "cross_checked" if wikidata.get("found") else "single_catalogue_exact_match",
            "source_urls": [u for u in (tmdb.get("provider_url"), wikidata.get("source")) if u],
            "title": tmdb.get("title") or clean,
            "title_my": tmdb.get("title") or clean,
            "description": "movie",
            "countries": countries,
            "year": tmdb.get("year") or None,
            "source": tmdb.get("provider_url") or "",
            "wikidata_crosscheck": bool(wikidata.get("found")),
            "enwiki_title": "",
            "mywiki_title": "",
            "tmdb_overview": tmdb.get("overview") or "",
            "imdb_id": tmdb.get("imdb_id") or "",
        }

    if wikidata.get("found"):
        # Wikidata often identifies an anime correctly but has no usable
        # Wikipedia Plot section. Supplement missing sitelinks with an exact
        # AniList/Tenrai catalogue synopsis without replacing Wikidata identity
        # or country metadata.
        synopsis_fields = {}
        if not wikidata.get("anime_synopsis"):
            anime = safe_fetch(research_anime_sources, "Anime catalogue")
            if anime.get("india_excluded"):
                return {"found": False, "status": "ဒီ Project မှာ အိန္ဒိယမူရင်းခေါင်းစဉ်များကို မထည့်ပါ။"}
            anilist = anime.get("anilist") or {}
            tenrai = anime.get("tenrai") or {}
            wikidata_year = str(wikidata.get("year") or "").strip()
            # research_anime_sources only marks a provider record found after
            # its own exact title/alias matcher has accepted the user's query.
            # Its canonical English title may legitimately differ from the
            # Wikidata label (romanization, punctuation, localized label).
            # Keep the query provenance exact and compare the year per provider;
            # a disagreement from a *different* catalogue must not suppress a
            # synopsis whose own year matches Wikidata.
            query_provenance_matches = (
                str(anime.get("title") or "").strip().casefold() == clean.casefold()
            )
            wikidata_title = " ".join(str(wikidata.get("title") or "").casefold().split())
            for candidate in (anilist, tenrai):
                if not candidate.get("found"):
                    continue
                anime_year = str(candidate.get("year") or "").strip()
                anime_title = " ".join(str(candidate.get("title") or "").casefold().split())
                if not wikidata_year or not anime_year or wikidata_year != anime_year:
                    continue
                # Backward-compatible test/fixture support: when query
                # provenance is absent, require the old exact canonical title.
                if not query_provenance_matches and (
                    not wikidata_title or not anime_title or wikidata_title != anime_title
                ):
                    continue
                country_code = str(candidate.get("country") or "").upper()
                if country_code == "IN" or _is_indian(wikidata.get("countries") or []):
                    continue
                synopsis = str(candidate.get("synopsis") or "").strip()
                synopsis_url = str(candidate.get("provider_url") or "").strip()
                if len(synopsis) >= 100 and synopsis_url.startswith("https://"):
                    synopsis_fields = {
                        "anime_synopsis": synopsis[:3500],
                        "anime_synopsis_source": synopsis_url,
                        "anime_synopsis_provider": candidate.get("provider") or "AniList/Tenrai",
                    }
                    break
        return {
            **wikidata,
            **synopsis_fields,
            "provider": "Wikidata",
            "metadata_source": "Wikidata",
            "metadata_confidence": "exact_title_match",
            "source_urls": [
                u for u in (
                    wikidata.get("source"),
                    synopsis_fields.get("anime_synopsis_source"),
                ) if u
            ],
        }

    # AniList/Tenrai are no-key catalogue sources for animation. Accept only
    # exact catalogue matches with a recognized country code and reject India.
    if anime is None:
        anime = safe_fetch(research_anime_sources, "Anime catalogue")
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
            "metadata_source": selected.get("provider") or "AniList/Tenrai",
            "metadata_confidence": "exact_catalogue_match_with_country_check",
            "source_urls": [u for u in (selected.get("provider_url"), (wd.get("source") if wd.get("found") else "")) if u],
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
