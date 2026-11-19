"""Free Wikidata metadata lookup for NEXORA research.

This is a metadata cross-check, not a verified plot summary. It uses the public
Wikidata Action API without credentials and reports missing fields explicitly.
"""
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0 (https://github.com/naykokoko135-pixel/NEXORA-MYANMAR-RECAP)"
PROPERTIES = {
    "P495": "countries",
    "P577": "dates",
    "P57": "directors",
    "P136": "genres",
    "P364": "languages",
    "P1113": "episode_count",
    "P2437": "season_count",
}


def _request_json(params):
    request = Request(
        API_URL + "?" + urlencode(params),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        import json
        return json.loads(response.read().decode("utf-8"))


def _normalize_title(value):
    """Normalize punctuation and Unicode consistently for exact label/alias checks."""
    import unicodedata

    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    value = re.sub(r"\s+\([^)]*\)$", "", value)
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def _candidate_matches_exact_title(item, normalized_title):
    """Accept an exact label or exact alias match; never accept substring similarity."""
    if _normalize_title(item.get("label", "")) == normalized_title:
        return True
    aliases = item.get("aliases", [])
    for alias in aliases if isinstance(aliases, list) else []:
        alias_text = alias.get("value", "") if isinstance(alias, dict) else alias
        if _normalize_title(alias_text) == normalized_title:
            return True
    match = item.get("match", {})
    return (
        isinstance(match, dict)
        and match.get("type") == "alias"
        and _normalize_title(match.get("text", "")) == normalized_title
    )



def _candidate_is_primary_screen_work(item):
    """Prefer a clearly described screen adaptation over manga/franchise records."""
    description = _normalize_title(item.get("description", ""))
    excluded = ("manga series", "media franchise", "literary series", "novel series")
    if any(term in description for term in excluded):
        return False
    preferred = (
        "anime television series", "animated television series",
        "television series", "anime film", "animated film",
        "television film", "feature film", "film",
    )
    return any(term in description for term in preferred)


def _claim_entity_ids(claims, property_id):
    values = []
    for claim in claims.get(property_id, []):
        datavalue = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        entity_id = datavalue.get("id") if isinstance(datavalue, dict) else None
        if entity_id and entity_id not in values:
            values.append(entity_id)
    return values


def _date_year(claims):
    for claim in claims.get("P577", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        timestamp = value.get("time", "") if isinstance(value, dict) else ""
        match = re.search(r"[+-](\d{4})-", timestamp)
        if match:
            return match.group(1)
    return None



def _quantity_value(claims, property_id):
    """Return one unambiguous, non-deprecated integer quantity or None."""
    statements = [
        item for item in claims.get(property_id, [])
        if item.get("rank") != "deprecated"
    ]
    preferred = [item for item in statements if item.get("rank") == "preferred"]
    candidates = preferred or statements
    values = set()
    for item in candidates:
        raw = item.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        amount = raw.get("amount") if isinstance(raw, dict) else None
        if amount is None:
            continue
        try:
            number = float(str(amount).lstrip("+"))
        except (TypeError, ValueError):
            continue
        if number >= 0 and number.is_integer():
            values.add(int(number))
    return next(iter(values)) if len(values) == 1 else None


def fetch_wikidata_metadata(title):
    """Return metadata for an exact title match, or a safe unavailable result."""
    clean_title = " ".join((title or "").split()).strip()
    if not clean_title or len(clean_title) > 120:
        return {"found": False, "status": "ခေါင်းစဉ်မမှန်ကန်ပါ။"}

    try:
        normalized_title = _normalize_title(clean_title)
        # Retry a title without a trailing release year. Wikidata often labels
        # a film "The General" while users enter "The General (1926)".
        # The final label/alias comparison remains exact after normalization.
        search_terms = [clean_title]
        year_free_title = re.sub(r"\s+\(\d{4}\)$", "", clean_title).strip()
        if year_free_title and year_free_title.casefold() != clean_title.casefold():
            search_terms.append(year_free_title)
        candidates_by_id = {}
        exact_by_id = {}
        # Search likely title languages. English remains first for backwards
        # compatibility; Burmese and Japanese are fallbacks for localized names.
        for language in ("en", "my", "ja"):
            for search_term in search_terms:
                search_payload = _request_json({
                    "action": "wbsearchentities",
                    "search": search_term,
                    "language": language,
                    "uselang": language,
                    "type": "item",
                    "limit": 50,
                    "format": "json",
                })
                for item in search_payload.get("search", []):
                    candidate_id = item.get("id", "")
                    if re.fullmatch(r"Q\d+", candidate_id):
                        candidates_by_id[candidate_id] = item
            exact_by_id = {
                candidate_id: item for candidate_id, item in candidates_by_id.items()
                if _candidate_matches_exact_title(item, normalized_title)
            }
            if exact_by_id:
                break
        if not exact_by_id:
            return {
                "found": False,
                "status": "Wikidata တွင် အမည်တိတိကျကျ သို့မဟုတ် Alternate title ကိုက်ညီသော မှတ်တမ်း မတွေ့ပါ။",
            }
        if len(exact_by_id) > 1:
            # If the user supplied a release year, use Wikidata's structured
            # publication-date claims to distinguish same-title works before
            # considering the descriptive screen-work preference.
            year_match = re.search(r"\((\d{4})\)$", clean_title)
            if year_match:
                requested_year = year_match.group(1)
                candidate_payload = _request_json({
                    "action": "wbgetentities",
                    "ids": "|".join(exact_by_id.keys()),
                    "props": "claims",
                    "format": "json",
                })
                year_matches = {}
                for candidate_id, item in exact_by_id.items():
                    candidate_entity = candidate_payload.get("entities", {}).get(candidate_id, {})
                    candidate_year = _date_year(candidate_entity.get("claims", {}))
                    if candidate_year == requested_year:
                        year_matches[candidate_id] = item
                if year_matches:
                    exact_by_id = year_matches
                else:
                    return {
                        "found": False,
                        "status": "ပေးထားသော ခုနှစ်နှင့် ကိုက်ညီသော Wikidata မှတ်တမ်း မတွေ့ပါ။ မှတ်တမ်းများကို မခန့်မှန်းဘဲ အတည်ပြုရန် လိုအပ်ပါသည်။",
                        "candidates": [
                            {
                                "entity_id": entity_id,
                                "title": item.get("label", ""),
                                "description": item.get("description", "မရရှိပါ"),
                                "source": "https://www.wikidata.org/wiki/" + entity_id,
                            }
                            for entity_id, item in exact_by_id.items()
                        ],
                    }

        if len(exact_by_id) > 1:
            # Prefer one clearly described screen work over manga/franchise
            # records, but never choose between multiple films or series.
            screen_work_matches = {
                entity_id: item for entity_id, item in exact_by_id.items()
                if _candidate_is_primary_screen_work(item)
            }
            if len(screen_work_matches) == 1:
                exact_by_id = screen_work_matches
            else:
                return {
                    "found": False,
                    "status": "ခေါင်းစဉ်နှင့် ကိုက်ညီသော Wikidata မှတ်တမ်းများ အများအပြားရှိနေသည်။ အမျိုးအစားကို မခွဲနိုင်သေးသဖြင့် အတည်ပြုမှုလိုအပ်ပါသည်။",
                    "candidates": [
                        {
                            "entity_id": entity_id,
                            "title": item.get("label", ""),
                            "description": item.get("description", "မရရှိပါ"),
                            "source": "https://www.wikidata.org/wiki/" + entity_id,
                        }
                        for entity_id, item in exact_by_id.items()
                    ],
                }

        selected = next(iter(exact_by_id.values()))
        entity_id = selected.get("id", "")
        entity_payload = _request_json({
            "action": "wbgetentities",
            "ids": entity_id,
            "props": "labels|descriptions|claims|sitelinks",
            "languages": "my|en",
            "languagefallback": 1,
            "format": "json",
        })
        entity = entity_payload.get("entities", {}).get(entity_id, {})
        if "missing" in entity:
            return {"found": False, "status": "Wikidata မှတ်တမ်းကို ဖတ်မရပါ။"}
        claims = entity.get("claims", {})

        linked_ids = []
        for property_id in ("P495", "P57", "P136", "P364"):
            for linked_id in _claim_entity_ids(claims, property_id):
                if linked_id not in linked_ids:
                    linked_ids.append(linked_id)

        labels = {}
        labels_payload = {"entities": {}}
        if linked_ids:
            labels_payload = _request_json({
                "action": "wbgetentities",
                "ids": "|".join(linked_ids[:20]),
                "props": "labels",
                "languages": "my|en",
                "languagefallback": 1,
                "format": "json",
            })
            for linked_id, linked_entity in labels_payload.get("entities", {}).items():
                label = linked_entity.get("labels", {}).get("en", {}).get("value")
                if label:
                    labels[linked_id] = label

        def values_for(property_id, language="en"):
            output = []
            for item_id in _claim_entity_ids(claims, property_id):
                label_data = labels_payload.get("entities", {}).get(item_id, {}).get("labels", {})
                label = label_data.get(language, {}).get("value")
                if not label and language == "en":
                    label = label_data.get("en", {}).get("value")
                if label and label not in output:
                    output.append(label)
            return output

        entity_labels = entity.get("labels", {})
        entity_descriptions = entity.get("descriptions", {})
        return {
            "found": True,
            "title": selected.get("label", clean_title),
            "title_my": entity_labels.get("my", {}).get("value", selected.get("label", clean_title)),
            "description": selected.get("description", ""),
            "description_my": entity_descriptions.get("my", {}).get("value", ""),
            "entity_id": entity_id,
            "mywiki_title": entity.get("sitelinks", {}).get("mywiki", {}).get("title", ""),
            "enwiki_title": entity.get("sitelinks", {}).get("enwiki", {}).get("title", ""),
            "enwiki_source": ("https://en.wikipedia.org/wiki/" + entity.get("sitelinks", {}).get("enwiki", {}).get("title", "").replace(" ", "_")) if entity.get("sitelinks", {}).get("enwiki", {}).get("title") else "",
            "mywiki_source": ("https://my.wikipedia.org/wiki/" + entity.get("sitelinks", {}).get("mywiki", {}).get("title", "").replace(" ", "_")) if entity.get("sitelinks", {}).get("mywiki", {}).get("title") else "",
            "countries": values_for("P495"),
            "countries_my": values_for("P495", "my"),
            "year": _date_year(claims),
            "directors": values_for("P57"),
            "directors_my": values_for("P57", "my"),
            "genres": values_for("P136"),
            "genres_my": values_for("P136", "my"),
            "languages": values_for("P364"),
            "languages_my": values_for("P364", "my"),
            "episode_count": _quantity_value(claims, "P1113"),
            "season_count": _quantity_value(claims, "P2437"),
            "source": "https://www.wikidata.org/wiki/" + entity_id,
            "status": "Wikidata မှတ်တမ်းကို ရရှိပါပြီ။ မူရင်းထုတ်လုပ်သူ/ဖြန့်ချိသူရင်းမြစ်ဖြင့် ထပ်မံစစ်ဆေးပါ။",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
        return {
            "found": False,
            "status": "Wikidata API ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။ အချက်အလက်ကို မခန့်မှန်းထားပါ။",
        }


def format_wikidata_metadata(metadata):
    """Format metadata while clearly distinguishing unavailable fields."""
    if not metadata or not metadata.get("found"):
        status = (metadata or {}).get("status", "Wikidata အချက်အလက် မရရှိပါ။")
        return "🗂️ Wikidata အချက်အလက်စစ်ဆေးမှု\n" + status

    def show(items):
        return ", ".join(items) if items else "မရရှိပါ"

    lines = [
        "🗂️ Wikidata အချက်အလက်စစ်ဆေးမှု",
        "ခေါင်းစဉ်: " + metadata.get("title", "မရရှိပါ"),
        "အကျဉ်းဖော်ပြချက်: " + (metadata.get("description") or "မရရှိပါ"),
        "မူရင်းနိုင်ငံ/ဒေသ (Wikidata): " + show(metadata.get("countries", [])),
        "ထွက်ရှိသည့်နှစ်: " + (metadata.get("year") or "မရရှိပါ"),
        "ဒါရိုက်တာ: " + show(metadata.get("directors", [])),
        "Genre: " + show(metadata.get("genres", [])),
        "မူရင်းဘာသာစကား: " + show(metadata.get("languages", [])),
        "Source: " + metadata.get("source", ""),
        "အခြေအနေ: " + metadata.get("status", "ထပ်မံစစ်ဆေးရန်"),
        "မှတ်ချက်: Wikidata သည် လူထုတည်းဖြတ်ဒေတာဖြစ်သည်။ မူရင်းစတူဒီယို/ဖြန့်ချိသူရင်းမြစ်နှင့် ထပ်မံတိုက်စစ်ပါ။",
    ]
    return "\n".join(lines)



def format_wikidata_episode_guide(metadata):
    """Format only Wikidata's explicit total counts; never infer season breakdowns."""
    if not metadata or not metadata.get("found"):
        status = (metadata or {}).get("status", "Wikidata Episode အချက်အလက် မရရှိပါ။")
        return "📺 Episode အရေအတွက် (Wikidata အစားထိုးရင်းမြစ်)\n" + status

    episode_count = metadata.get("episode_count")
    season_count = metadata.get("season_count")
    lines = [
        "📺 Episode အရေအတွက် (Wikidata အစားထိုးရင်းမြစ်)",
        "ခေါင်းစဉ်: " + metadata.get("title", "မရရှိပါ"),
        "Season အရေအတွက်: " + (str(season_count) if season_count is not None else "မရရှိပါ"),
        "စုစုပေါင်း Episode အရေအတွက်: " + (str(episode_count) if episode_count is not None else "မရရှိပါ"),
        "Source: " + metadata.get("source", ""),
        "အခြေအနေ: Wikidata တွင် အရေအတွက်တန်ဖိုးရှိပါကသာ ဖော်ပြထားသည်။",
        "သတိပြုရန်: Season တစ်ခုချင်းစီ၏ Episode စာရင်း/ခေါင်းစဉ်များ မဟုတ်ပါ။ လူထုတည်းဖြတ်ဒေတာဖြစ်ပြီး နောက်ဆုံးအခြေအနေ မပြည့်စုံနိုင်သဖြင့် Official Studio/Broadcaster Guide နှင့် ပြန်စစ်ပါ။",
    ]
    if episode_count is None and season_count is None:
        lines.append("မှတ်ချက်: Wikidata တွင် Season/Episode အရေအတွက် မရရှိပါ။ မခန့်မှန်းထားပါ။")
    return "\n".join(lines)
