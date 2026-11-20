"""Free animation catalogue discovery for Donghua, cartoons, and 3D animation.

Bangumi is an East-Asian animation catalogue, not a definitive Donghua-only
database. A Donghua classification requires an independent China-origin
cross-check from Wikidata. Cartoon and 3D labels are conservative Wikidata
discovery leads, not proof of production technique or footage rights.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from wikidata_metadata import fetch_wikidata_metadata
from bcdb_cartoon_catalogue import fetch_bcdb_popular_cartoon
from blender_open_movies_catalogue import fetch_blender_open_movie

BANGUMI_SEARCH_URL = "https://api.bgm.tv/v0/search/subjects"
USER_AGENT = "NEXORA-Myanmar-Recap/2.0 (free animation catalogue research)"


def _norm(value):
    import unicodedata
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def _bangumi_search(title):
    body = json.dumps({
        "keyword": title,
        "sort": "match",
        "filter": {"type": [2], "nsfw": False},
    }).encode("utf-8")
    request = Request(
        BANGUMI_SEARCH_URL + "?limit=10&offset=0",
        data=body,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=18) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bangumi_animation(title):
    """Return one exact non-NSFW Bangumi animation record; reject ambiguous hits."""
    requested = " ".join(str(title or "").split()).strip()
    if not requested or len(requested) > 120:
        return {"found": False, "status": "Bangumi ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    try:
        payload = _bangumi_search(requested)
        candidates = payload.get("data", []) if isinstance(payload, dict) else []
        exact = []
        target = _norm(requested)
        for item in candidates if isinstance(candidates, list) else []:
            if item.get("type") != 2 or item.get("nsfw") is True:
                continue
            names = [item.get("name"), item.get("name_cn")]
            if any(_norm(name) == target for name in names if name):
                exact.append(item)
        # De-duplicate the same catalogue item if the API repeats it.
        by_id = {str(item.get("id")): item for item in exact if item.get("id") is not None}
        if len(by_id) != 1:
            return {
                "found": False,
                "status": (
                    "Bangumi တွင် အမည်တိတိကျကျ ကိုက်ညီသော Animation တစ်ခုတည်းကို "
                    "မသတ်မှတ်နိုင်ပါ။"
                ),
            }
        item = next(iter(by_id.values()))
        subject_id = item.get("id")
        summary = re.sub(r"\\s+", " ", str(item.get("summary") or "")).strip()
        return {
            "found": True,
            "provider": "Bangumi public animation catalogue",
            "media_id": subject_id,
            "title": item.get("name_cn") or item.get("name") or requested,
            "original_title": item.get("name") or "",
            "summary": summary[:2500],
            "date": str(item.get("date") or ""),
            "score": item.get("score"),
            "rank": item.get("rank"),
            "provider_url": f"https://bgm.tv/subject/{subject_id}",
            "scope": "catalogue_record_not_verified_plot",
            "notice": (
                "Bangumi သည် အရှေ့အာရှ Animation catalogue ဖြစ်သည်။ "
                "တစ်ခုတည်းဖြင့် Donghua မူရင်းနိုင်ငံကို မဆုံးဖြတ်ပါ။"
            ),
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
        return {"found": False, "status": "Bangumi public API ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}


def _safe_wikidata(title):
    try:
        return fetch_wikidata_metadata(title)
    except Exception:
        return {"found": False, "status": "Wikidata ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}


def _description_matches(description, category):
    text = _norm(description)
    if category == "cartoon":
        return any(term in text for term in (
            "cartoon", "animated television series", "animated series",
            "animated film", "animated feature film", "animated short film",
        ))
    if category == "3d_animation":
        return any(term in text for term in (
            "3d animated", "3d computer animation", "computer animated",
            "computer animation film", "computer generated animation",
            "cgi animated", "computer generated imagery",
        ))
    return False


def research_animation_catalogues(title):
    """Research separate category leads; never infer 3D technique or China origin."""
    clean = " ".join(str(title or "").split()).strip()
    if not clean or len(clean) > 120:
        invalid = {"found": False, "status": "ခေါင်းစဉ် မမှန်ကန်ပါ။"}
        return {
            "title": clean, "donghua": invalid, "cartoon": invalid,
            "3d_animation": invalid,
        }

    with ThreadPoolExecutor(max_workers=3) as pool:
        bangumi_future = pool.submit(fetch_bangumi_animation, clean)
        bcdb_future = pool.submit(fetch_bcdb_popular_cartoon, clean)
        wikidata_future = pool.submit(_safe_wikidata, clean)
        bangumi = bangumi_future.result()
        bcdb = bcdb_future.result()
        wikidata = wikidata_future.result()
    blender = fetch_blender_open_movie(clean)

    countries = [str(value) for value in (wikidata.get("countries") or [])] if wikidata.get("found") else []
    country_text = " ".join(countries).casefold()
    china_origin = any(term in country_text for term in ("china", "people's republic of china", "တရုတ်"))
    india_origin = any(term in country_text for term in ("india", "အိန္ဒိယ"))
    japan_origin = any(term in country_text for term in ("japan", "ဂျပန်"))

    if bangumi.get("found") and china_origin:
        donghua = {
            "found": True,
            "classification": "China-origin animation candidate",
            "bangumi": bangumi,
            "wikidata": wikidata,
            "notice": "Bangumi record + Wikidata China-origin metadata; verify studio and official release sources.",
        }
    elif bangumi.get("found"):
        donghua = {
            "found": False,
            "bangumi": bangumi,
            "wikidata": wikidata,
            "status": (
                "Bangumi တွင် Animation မှတ်တမ်းရှိသော်လည်း Wikidata မှ China မူရင်းနိုင်ငံ "
                "အတည်ပြုချက် မရသေးပါ။ Donghua ဟု မသတ်မှတ်ထားပါ။"
            ),
        }
    else:
        donghua = {
            "found": False, "bangumi": bangumi, "wikidata": wikidata,
            "status": "Donghua အဖြစ် မသတ်မှတ်နိုင်သေးပါ။",
        }

    if india_origin:
        cartoon = {
            "found": False,
            "status": "Wikidata တွင် အိန္ဒိယမူရင်းနိုင်ငံကို တွေ့ရှိသဖြင့် ဒီ Project အတွက် ပယ်ချထားပါသည်။",
            "india_excluded": True,
            "bcdb": bcdb,
        }
    elif japan_origin or china_origin:
        cartoon = {
            "found": False,
            "status": "Wikidata မူရင်းနိုင်ငံအရ Japan/China ဖြစ်နေသဖြင့် Cartoon အဖြစ် မခွဲထားပါ။ Anime/Donghua track ကို စစ်ဆေးပါ။",
            "bcdb": bcdb,
        }
    elif bcdb.get("found"):
        cartoon = {
            "found": True, "provider": "The Big Cartoon DataBase (BCDB)",
            "title": bcdb.get("title"), "source": bcdb.get("provider_url"),
            "catalogue_url": bcdb.get("catalogue_url"),
            "countries": countries, "year": wikidata.get("year") if wikidata.get("found") else None,
            "origin_verified": bool(countries),
            "notice": "BCDB facts/compilation CC BY 4.0; credit BCDB. BCDB page-view ranking is not platform trend data. Country must be verified before production.",
        }
    elif wikidata.get("found") and _description_matches(wikidata.get("description"), "cartoon"):
        cartoon = {
            "found": True, "provider": "Wikidata CC0 structured open data",
            "title": wikidata.get("title"), "description": wikidata.get("description"),
            "countries": countries, "year": wikidata.get("year"),
            "source": wikidata.get("source"),
            "origin_verified": bool(countries),
            "notice": "Cartoon/animated-work discovery lead; Wikidata description is community-edited.",
        }
    else:
        cartoon = {
            "found": False,
            "status": "BCDB Popular စာရင်းနှင့် Wikidata တွင် Cartoon/Animated work ဟု အတည်ပြုနိုင်သော မှတ်တမ်း မတွေ့ပါ။",
            "bcdb": bcdb, "wikidata": wikidata,
        }

    if india_origin:
        three_d = {
            "found": False,
            "status": "Wikidata တွင် အိန္ဒိယမူရင်းနိုင်ငံကို တွေ့ရှိသဖြင့် ဒီ Project အတွက် ပယ်ချထားပါသည်။",
            "india_excluded": True,
        }
    elif blender.get("found"):
        three_d = {
            "found": True, "provider": blender.get("provider"),
            "title": blender.get("title"), "year": blender.get("year"),
            "source": blender.get("source"), "catalogue_url": blender.get("catalogue"),
            "wikidata": wikidata,
            "notice": "Blender Studio official open-movie curated 3D subset. This is not a full 3D catalogue; verify title-specific rights before using footage.",
        }
    elif wikidata.get("found") and _description_matches(wikidata.get("description"), "3d_animation"):
        three_d = {
            "found": True, "provider": "Wikidata CC0 structured open data",
            "title": wikidata.get("title"), "description": wikidata.get("description"),
            "countries": countries, "year": wikidata.get("year"),
            "source": wikidata.get("source"),
            "notice": "3D/computer-animation discovery lead only; verify the production technique from studio sources.",
        }
    else:
        three_d = {
            "found": False,
            "status": "Wikidata description တွင် 3D/Computer Animation ဟု တိတိကျကျ မဖော်ပြထားပါ။ 3D ဟု မခန့်မှန်းပါ။",
            "wikidata": wikidata,
        }

    return {
        "title": clean,
        "donghua": donghua,
        "cartoon": cartoon,
        "3d_animation": three_d,
        "bangumi": bangumi,
        "bcdb": bcdb,
        "blender_open_movie": blender,
        "wikidata": wikidata,
    }


def format_animation_catalogue_report(report):
    lines = [
        "🎞️ NEXORA — Free Animation Catalogue Research",
        "ခေါင်းစဉ်: " + str(report.get("title") or "မရရှိပါ"),
        "",
        "【DONGHUA — Bangumi + Wikidata】",
    ]
    donghua = report.get("donghua") or {}
    if donghua.get("found"):
        item = donghua.get("bangumi") or {}
        wd = donghua.get("wikidata") or {}
        lines.extend([
            "အမည်: " + str(item.get("title") or "မရရှိပါ"),
            "နိုင်ငံ: " + (", ".join(wd.get("countries") or []) or "မရရှိပါ"),
            "နှစ်: " + str(wd.get("year") or item.get("date") or "မရရှိပါ"),
            "Bangumi: " + str(item.get("provider_url") or ""),
            "Wikidata: " + str(wd.get("source") or ""),
        ])
    else:
        lines.append(str(donghua.get("status") or "အတည်မပြုနိုင်ပါ။"))

    lines.extend(["", "【CARTOON — BCDB + Wikidata open catalogue】"])
    cartoon = report.get("cartoon") or {}
    if cartoon.get("found"):
        lines.extend([
            "အမည်: " + str(cartoon.get("title") or "မရရှိပါ"),
            "ဖော်ပြချက်: " + str(cartoon.get("description") or "Cartoon catalogue record"),
            "Source: " + str(cartoon.get("source") or ""),
            "နိုင်ငံအတည်ပြုချက်: " + ("ရရှိ" if cartoon.get("origin_verified") else "မရရှိသေး — production မစတင်ရ"),
        ])
        if cartoon.get("provider") == "The Big Cartoon DataBase (BCDB)":
            lines.extend([
                "BCDB Catalogue: " + str(cartoon.get("catalogue_url") or ""),
                "Attribution: The Big Cartoon DataBase (bcdb.com), CC BY 4.0",
                "သတိပြုရန်: BCDB Popular စာရင်း၏ page views သည် social-platform trend data မဟုတ်ပါ။",
            ])
    else:
        lines.append(str(cartoon.get("status") or "ရင်းမြစ် မရရှိပါ။"))

    lines.extend(["", "【3D ANIMATION — Blender Open Movies + Wikidata】"])
    three_d = report.get("3d_animation") or {}
    if three_d.get("found"):
        lines.extend([
            "အမည်: " + str(three_d.get("title") or "မရရှိပါ"),
            "ဖော်ပြချက်: " + str(three_d.get("description") or "3D Open Movie catalogue record"),
            "Source: " + str(three_d.get("source") or ""),
            "Catalogue: " + str(three_d.get("catalogue_url") or ""),
        ])
    else:
        lines.append(str(three_d.get("status") or "ရင်းမြစ် မရရှိပါ။"))

    lines.extend([
        "",
        "ရင်းမြစ်အမျိုးအစား: Bangumi သည် အရှေ့အာရှ Animation catalogue ဖြစ်ပြီး Donghua သီးသန့် catalogue မဟုတ်ပါ။",
        "BCDB သည် Cartoon catalogue ဖြစ်ပြီး /most-popular စာရင်းကိုသာ ဖတ်သည်။ /search ကို robots.txt က ပိတ်ထားသဖြင့် မသုံးပါ။",
        "Blender Studio သည် 3D Open Movies ၏ curated subset သာဖြစ်ပြီး 3D Animation ကမ္ဘာလုံးဆိုင်ရာ catalogue မဟုတ်ပါ။",
        "Wikidata သည် CC0 Open Data ဖြစ်သော်လည်း Cartoon/3D ဖော်ပြချက်များ မပြည့်စုံနိုင်ပါ။",
        "ဒီအချက်အလက်များသည် discovery lead သာဖြစ်ပြီး ဇာတ်ကွက်အတည်ပြုချက် သို့မဟုတ် footage/license ခွင့်ပြုချက် မဟုတ်ပါ။",
    ])
    return "\n".join(lines)
