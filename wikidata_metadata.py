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
    value = str(value or "").casefold().strip()
    value = re.sub(r"\s+\([^)]*\)$", "", value)
    return " ".join(re.findall(r"[a-z0-9]+", value))


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


def fetch_wikidata_metadata(title):
    """Return metadata for an exact title match, or a safe unavailable result."""
    clean_title = " ".join((title or "").split()).strip()
    if not clean_title or len(clean_title) > 120:
        return {"found": False, "status": "ခေါင်းစဉ်မမှန်ကန်ပါ။"}

    try:
        search_payload = _request_json({
            "action": "wbsearchentities",
            "search": clean_title,
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": 8,
            "format": "json",
        })
        candidates = search_payload.get("search", [])
        exact = [
            item for item in candidates
            if _normalize_title(item.get("label", "")) == _normalize_title(clean_title)
        ]
        if not exact:
            return {
                "found": False,
                "status": "Wikidata တွင် အမည်တိတိကျကျ ကိုက်ညီသော မှတ်တမ်း မတွေ့ပါ။",
            }

        selected = exact[0]
        entity_id = selected.get("id", "")
        if not re.fullmatch(r"Q\d+", entity_id):
            return {"found": False, "status": "Wikidata entity ID မမှန်ကန်ပါ။"}

        entity_payload = _request_json({
            "action": "wbgetentities",
            "ids": entity_id,
            "props": "labels|claims",
            "languages": "en",
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
        if linked_ids:
            labels_payload = _request_json({
                "action": "wbgetentities",
                "ids": "|".join(linked_ids[:20]),
                "props": "labels",
                "languages": "en",
                "languagefallback": 1,
                "format": "json",
            })
            for linked_id, linked_entity in labels_payload.get("entities", {}).items():
                label = linked_entity.get("labels", {}).get("en", {}).get("value")
                if label:
                    labels[linked_id] = label

        def values_for(property_id):
            return [
                labels[item_id]
                for item_id in _claim_entity_ids(claims, property_id)
                if item_id in labels
            ]

        return {
            "found": True,
            "title": selected.get("label", clean_title),
            "description": selected.get("description", ""),
            "entity_id": entity_id,
            "countries": values_for("P495"),
            "year": _date_year(claims),
            "directors": values_for("P57"),
            "genres": values_for("P136"),
            "languages": values_for("P364"),
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
