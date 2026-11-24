"""Trend research + multi-source verification. Never guesses on ambiguous matches."""
import datetime as dt
import random
import re
import urllib.parse

from . import config
from .http import get
from .state import norm, used_titles

WIKI = "https://en.wikipedia.org/w/api.php"
INDIA_LANGS = {"hi", "ta", "te", "ml", "kn", "bn", "mr", "pa", "ur", "gu"}
PLOT_KEYS = ("plot", "synopsis", "premise", "story", "summary", "plot summary", "storyline", "overview")
EXTRA_KEYS = ("cast", "characters", "production", "development", "reception", "release", "themes",
              "music", "legacy", "background", "critical reception", "voice cast", "casting", "analysis")


# ---------------- catalogs ----------------
def anilist(country, fmts):
    q = """query($c:CountryCode,$f:[MediaFormat]){Page(perPage:25){media(type:ANIME,sort:TRENDING_DESC,
    countryOfOrigin:$c,format_in:$f,isAdult:false){id title{romaji english} startDate{year}
    countryOfOrigin format genres popularity trending episodes siteUrl}}}"""
    d = get("https://graphql.anilist.co", json_body={"query": q, "variables": {"c": country, "f": fmts}})
    out = []
    for m in d["data"]["Page"]["media"]:
        t = m["title"]["english"] or m["title"]["romaji"]
        out.append(dict(title=t, alt=m["title"]["romaji"], year=(m["startDate"] or {}).get("year"),
                        country=m["countryOfOrigin"], kind=m["format"], genres=m["genres"],
                        popularity=m["popularity"], catalog="AniList", url=m["siteUrl"], hint="anime"))
    return out


def jikan_fallback():
    d = get("https://api.jikan.moe/v4/top/anime", params={"filter": "airing", "sfw": "true", "limit": 25})
    return [dict(title=m.get("title_english") or m["title"], alt=m["title"], year=m.get("year"),
                 country="JP", kind=m.get("type"), genres=[g["name"] for g in m.get("genres", [])],
                 popularity=m.get("members", 0), catalog="Jikan/MyAnimeList", url=m["url"], hint="anime")
            for m in d["data"]]


def tmdb(path, **p):
    if not config.TMDB_KEY:
        raise RuntimeError("TMDB_API_KEY missing")
    return get("https://api.themoviedb.org/3" + path, params={"api_key": config.TMDB_KEY, **p})


def _tm(r, kind, hint):
    date = r.get("release_date") or r.get("first_air_date") or ""
    return dict(title=r.get("title") or r.get("name"), alt=r.get("original_title") or r.get("original_name"),
                year=int(date[:4]) if date[:4].isdigit() else None, country=r.get("original_language"),
                kind=kind, genres=r.get("genre_ids", []), popularity=r.get("popularity", 0),
                catalog="TMDB", url=f"https://www.themoviedb.org/{kind}/{r['id']}", hint=hint)


def candidates(category):
    if category == "Anime":
        try:
            return anilist("JP", ["TV", "MOVIE", "ONA", "OVA"])
        except Exception:
            return jikan_fallback()
    if category == "Donghua":
        return anilist("CN", ["TV", "MOVIE", "ONA"])
    if category == "Cartoon":
        r = tmdb("/discover/tv", with_genres=16, sort_by="popularity.desc")["results"]
        return [_tm(x, "tv", "TV series") for x in r if x.get("original_language") not in {"ja", "zh", "hi"}]
    if category == "3D Animation":
        kw = tmdb("/search/keyword", query="computer animation")["results"]
        ids = "|".join(str(k["id"]) for k in kw[:3]) or ""
        r = tmdb("/discover/movie", with_genres=16, with_keywords=ids, sort_by="popularity.desc")["results"]
        return [_tm(x, "movie", "film") for x in r if x.get("original_language") not in INDIA_LANGS]
    if category == "International Movies":
        r = tmdb("/discover/movie", sort_by="popularity.desc", without_genres="16,99,10770",
                 **{"vote_count.gte": 300})["results"]
        return [_tm(x, "movie", "film") for x in r if x.get("original_language") not in INDIA_LANGS]
    raise ValueError(category)


# ---------------- wikipedia verification ----------------
def _base(t):
    return norm(re.sub(r"\(.*?\)", "", t or ""))


def wiki_lookup(c):
    """Identity check: page title must match the catalog title and mention the release year."""
    for name in filter(None, {c["title"], c.get("alt")}):
        hits = get(WIKI, params=dict(action="query", list="search", srsearch=f'{name} {c["hint"]}',
                                     srlimit=6, format="json"))["query"]["search"]
        for h in hits:
            if _base(h["title"]) != _base(name):
                continue
            d = get(WIKI, params=dict(action="query", prop="extracts", explaintext=1, redirects=1,
                                      exsectionformat="wiki", titles=h["title"], format="json"))
            page = next(iter(d["query"]["pages"].values()))
            text = page.get("extract", "")
            if c.get("year") and str(c["year"]) not in text[:4000]:
                continue  # ambiguous: do not guess
            return page["title"], text
    return None, None


def split_sections(text):
    parts = re.split(r"\n==+ *(.+?) *==+ *\n", "\n" + text)
    secs = {}
    for i in range(1, len(parts), 2):
        k = parts[i].strip().lower()
        secs[k] = (secs.get(k, "") + "\n" + parts[i + 1]).strip()
    return parts[0].strip(), secs


def pageviews(title, days=30):
    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=days)
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    try:
        d = get("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
                f"{t}/daily/{start:%Y%m%d}/{end:%Y%m%d}")
        return sum(i["views"] for i in d["items"])
    except Exception:
        return 0


def verify(c, platform):
    wt, text = wiki_lookup(c)
    if not wt:
        return None
    intro, secs = split_sections(text)
    plot = "\n".join(v for k, v in secs.items() if k in PLOT_KEYS or k.startswith("plot"))
    extras = {k: v for k, v in secs.items() if k in EXTRA_KEYS and v}
    total = len(plot) + len(intro) + sum(len(v) for v in extras.values())
    if len(plot) < 600 or total < config.PLATFORMS[platform]["min_source"]:
        return None  # not enough factual source to write a truthful script
    return {**c, "wiki_title": wt, "wiki_url": "https://en.wikipedia.org/wiki/" + wt.replace(" ", "_"),
            "intro": intro, "plot": plot, "extras": extras, "views": pageviews(wt),
            "sources": [c["catalog"], "Wikipedia", "Wikimedia Pageviews"]}


def category_order(platform, date=None):
    date = date or dt.date.today()
    i = config.PLATFORM_ORDER.index(platform)
    k = (date.toordinal() + i * 2) % len(config.CATEGORIES)
    return config.CATEGORIES[k:] + config.CATEGORIES[:k]


def pick(platform, taken_cats=(), taken_titles=(), date=None, log=print):
    used = used_titles() | {norm(t) for t in taken_titles}
    order = [c for c in category_order(platform, date) if c not in taken_cats] or category_order(platform, date)
    for cat in order:
        try:
            cands = candidates(cat)
        except Exception as e:
            log(f"[research] {cat} catalog failed: {e}")
            continue
        scored = []
        for c in cands:
            if not c["title"] or norm(c["title"]) in used:
                continue
            if c["country"] in INDIA_LANGS or c["country"] == "IN":
                continue
            scored.append(c)
        scored.sort(key=lambda x: -(x.get("popularity") or 0))
        for c in scored[:10]:
            try:
                v = verify(c, platform)
            except Exception as e:
                log(f"[research] verify error {c['title']}: {e}")
                continue
            if v:
                v["category"] = cat
                v["score"] = v["views"] + (c.get("popularity") or 0)
                return v
    raise RuntimeError(f"No verifiable title found for {platform}")


def pick_daily(date=None, log=print):
    picks, cats, titles = {}, [], []
    for p in config.PLATFORM_ORDER:
        r = pick(p, cats, titles, date, log)
        picks[p] = r
        cats.append(r["category"])
        titles.append(r["title"])
    return picks


def resolve_title(title, platform, log=print):
    """User-supplied title: infer category from catalogs, then verify. No guessing on ambiguity."""
    c = None
    try:
        q = 'query($s:String){Page(perPage:5){media(type:ANIME,search:$s,isAdult:false){title{romaji english} startDate{year} countryOfOrigin format genres popularity siteUrl}}}'
        for m in get("https://graphql.anilist.co", json_body={"query": q, "variables": {"s": title}})["data"]["Page"]["media"]:
            names = [m["title"]["english"], m["title"]["romaji"]]
            if norm(title) in [norm(n) for n in names if n]:
                cat = "Donghua" if m["countryOfOrigin"] == "CN" else "Anime"
                c = dict(title=m["title"]["english"] or m["title"]["romaji"], alt=m["title"]["romaji"],
                         year=m["startDate"]["year"], country=m["countryOfOrigin"], kind=m["format"], genres=m["genres"],
                         popularity=m["popularity"], catalog="AniList", url=m["siteUrl"], hint="anime", category=cat)
                break
    except Exception as e:
        log(f"[resolve] anilist: {e}")
    if not c and config.TMDB_KEY:
        for r in tmdb("/search/multi", query=title)["results"]:
            if r.get("media_type") in ("movie", "tv") and norm(r.get("title") or r.get("name")) == norm(title):
                c = _tm(r, r["media_type"], "film" if r["media_type"] == "movie" else "TV series")
                c["category"] = "Cartoon" if 16 in c["genres"] else "International Movies"
                break
    if not c:
        raise RuntimeError(f"'{title}' ကို catalog တွေမှာ တိတိကျကျ မတွေ့ပါ (ခန့်မှန်းမလုပ်ပါ)")
    if c["country"] in INDIA_LANGS or c["country"] == "IN":
        raise RuntimeError("India titles မလုပ်ရပါ")
    v = verify(c, platform)
    if not v:
        raise RuntimeError("Wikipedia source မလုံလောက်/ရှင်းလင်းမှုမရှိပါ")
    v["category"] = c["category"]
    v["score"] = v["views"]
    return v


def episodes(title):
    d = get("https://api.tvmaze.com/singlesearch/shows", params={"q": title, "embed": "episodes"})
    eps = d["_embedded"]["episodes"]
    seasons = {}
    for e in eps:
        seasons[e["season"]] = seasons.get(e["season"], 0) + 1
    return d["name"], seasons
