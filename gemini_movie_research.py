"""Gemini Google Search-grounded movie metadata fallback.

Uses the existing GEMINI_API_KEY. Requires grounded source URLs from at least
two distinct domains and structured production-country/year metadata. Never
treats an ungrounded model answer as verified catalogue data.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cost_controls import paid_ai_allowed

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.8-flash"
RETIRED_MODEL_ALIASES = {"gemini-2.5-flash": DEFAULT_MODEL}
TIMEOUT_SECONDS = 45


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    value = re.sub(r"\s+\(\d{4}\)$", "", value)
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def _safe_status(message: str) -> dict:
    return {"found": False, "status": message}


def _http_error_status(exc: HTTPError) -> str:
    """Classify Google's HTTP errors without exposing request credentials."""
    try:
        body = exc.read(16_384).decode("utf-8", errors="replace")
        payload = json.loads(body) if body else {}
    except (OSError, ValueError, TypeError):
        payload = {}

    error = payload.get("error") if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        error = {}
    google_status = str(error.get("status") or "").strip()
    message = str(error.get("message") or "").casefold()
    reasons = []
    details = error.get("details") or []
    if isinstance(details, list):
        for detail in details:
            if isinstance(detail, dict):
                reason = detail.get("reason")
                if reason:
                    reasons.append(str(reason).casefold())
                metadata = detail.get("metadata")
                if isinstance(metadata, dict):
                    reasons.extend(str(value).casefold() for value in metadata.values())
    reason_text = " ".join(reasons)
    diagnostic = " ".join((google_status.casefold(), reason_text, message))

    if any(term in diagnostic for term in ("free tier", "free-tier", "not available for free", "billingnotenabled")):
        return _safe_status(
            "Google API က လက်ရှိ Free Tier တွင် Google Search Grounding ကို ခွင့်မပြုခြင်း သို့မဟုတ် Billing မဖွင့်ထားခြင်း ဖြစ်နိုင်ပါသည်။ "
            "AI Studio ရှိ Project Billing နှင့် Search Grounding ရရှိနိုင်မှုကို စစ်ဆေးပါ။"
        )["status"]
    if any(term in diagnostic for term in ("billing", "spend cap", "payment", "insufficient_quota")):
        return _safe_status(
            "Google API က Billing သို့မဟုတ် Project Spend Limit ဆိုင်ရာ ကန့်သတ်ချက်ကို ပြန်ပေးထားပါသည်။ "
            "အသုံးပြုမှုမရှိဟု မြင်ရသော်လည်း Project Billing နှင့် Spend Cap ကို စစ်ဆေးပါ။"
        )["status"]
    if any(term in diagnostic for term in ("ratelimit", "rate_limit", "quota", "resource_exhausted", "too many requests")):
        label = google_status or (reasons[0] if reasons else "RESOURCE_EXHAUSTED")
        return _safe_status(
            f"Google API က Rate/Quota ကန့်သတ်ချက်ကို ပြန်ပေးထားပါသည် ({label[:80]}၊ HTTP {exc.code})။ "
            "ဒါဟာ သင်ကိုယ်တိုင် အသုံးပြုခဲ့ကြောင်း သက်သေမဟုတ်ပါ။ Project၊ Model နှင့် Search Grounding limit ကို စစ်ဆေးပါ။"
        )["status"]

    label = google_status or "အကြောင်းရင်းမသတ်မှတ်ရသေး"
    reason = reasons[0][:80] if reasons else ""
    suffix = f"၊ reason: {reason}" if reason else ""
    return (
        f"Google Gemini API က HTTP {exc.code} ပြန်ပေးထားပါသည် ({label}{suffix})။ "
        "Quota ပြည့်သည်ဟု တိတိကျကျ မသတ်မှတ်နိုင်သေးပါ။ Google error အကြောင်းရင်းကို စစ်ဆေးရန်လိုပါသည်။"
    )


def fetch_gemini_movie_metadata(title: str) -> dict:
    """Search public web sources via Gemini grounding and return validated facts."""
    clean = " ".join(str(title or "").split()).strip()
    if not clean or len(clean) > 120:
        return _safe_status("ရုပ်ရှင်ခေါင်းစဉ် မမှန်ကန်ပါ။")
    if not paid_ai_allowed():
        return _safe_status("Free-only mode ဖွင့်ထားသည်။ အခကြေးငွေရှိနိုင်သော Gemini Search API ကို ပိတ်ထားသည်။")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return _safe_status("GEMINI_API_KEY မချိတ်ထားပါ။ Render Environment ကို စစ်ဆေးပါ။")

    configured_model = os.getenv("GEMINI_RESEARCH_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    # Render may retain an older dashboard override after Blueprint changes.
    # Route the retired 2.5 Flash setting to the current Search-grounding model.
    model = RETIRED_MODEL_ALIASES.get(configured_model, configured_model)
    model_fallback_used = model != configured_model
    prompt = (
        "Research the exact film title using Google Search. Do not guess. "
        "Return ONLY a JSON object with keys: title, media_type, release_year, "
        "production_countries, original_language, directors, genres, overview, "
        "identity_match, uncertainty. "
        "title must be the exact film title or its established official alternate title. "
        "media_type must be feature film. release_year must be a four-digit year or null. "
        "production_countries must list ALL known original and co-production countries, "
        "not filming locations or distribution territories. If uncertain, return an empty list. "
        "Use reliable sources such as official studio/distributor pages, national film institutes, "
        "BFI, film festival catalogues, or established encyclopedias. "
        "Do not infer country from language, cast nationality, setting, or director nationality. "
        "The project excludes any Indian-origin or Indian co-production film: explicitly check "
        "whether India is a production country or co-producer. "
        "overview must be a short factual synopsis, not invented plot details. "
        "If the exact film identity or production countries cannot be established, set "
        "identity_match false or leave uncertain fields empty. "
        f"Film title to research: {clean}"
    )
    payload = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"googleSearch": {}}],
        "generationConfig": {"temperature": 1.0},
    }).encode("utf-8")
    url = API_BASE + "/" + model + ":generateContent"
    request = Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            result = json.loads(response.read(1_500_000).decode("utf-8"))
    except HTTPError as exc:
        if exc.code in (401, 403):
            return _safe_status("Gemini API Key သို့မဟုတ် permission မမှန်ပါ။")
        if exc.code == 429:
            return _safe_status(_http_error_status(exc))
        return _safe_status(f"Gemini Search API ယာယီမရရှိပါ (HTTP {exc.code})။")
    except (URLError, TimeoutError, OSError):
        return _safe_status("Gemini Search API သို့ ချိတ်ဆက်မရပါ။")
    except (ValueError, TypeError, KeyError):
        return _safe_status("Gemini Search API တုံ့ပြန်မှုကို ဖတ်မရပါ။")

    candidates = result.get("candidates") or []
    if not candidates:
        return _safe_status("Gemini Search မှ အဖြေမရရှိပါ။")
    candidate = candidates[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "\n".join(str(part.get("text") or "") for part in parts if isinstance(part, dict)).strip()
    grounding = candidate.get("groundingMetadata") or {}
    chunks = grounding.get("groundingChunks") or []
    sources = []
    domains = set()
    for chunk in chunks:
        web = chunk.get("web") if isinstance(chunk, dict) else None
        uri = str((web or {}).get("uri") or "").strip()
        source_title = str((web or {}).get("title") or "").strip()
        match = re.match(r"^https://([^/]+)", uri, flags=re.I)
        if match and uri not in {item["url"] for item in sources}:
            domain = match.group(1).lower().split(":")[0]
            domains.add(domain.removeprefix("www."))
            sources.append({"title": source_title[:180], "url": uri[:1000]})
    if len(domains) < 2:
        return _safe_status("Gemini အဖြေတွင် လွတ်လပ်သော web source domain အနည်းဆုံး ၂ ခု မရရှိပါ။")

    try:
        cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text, flags=re.I)
        data = json.loads(cleaned)
    except (ValueError, TypeError):
        return _safe_status("Gemini grounded အဖြေသည် သတ်မှတ်ထားသော JSON ပုံစံမဟုတ်ပါ။")

    if data.get("identity_match") is not True or _normalize(data.get("title", "")) != _normalize(clean):
        return _safe_status("Gemini ရှာဖွေမှုတွင် ခေါင်းစဉ်အတိအကျကို အတည်မပြုနိုင်ပါ။")
    if str(data.get("media_type") or "").casefold() not in {"feature film", "film", "movie"}:
        return _safe_status("Gemini ရှာဖွေမှုတွင် Feature Film အမျိုးအစားကို အတည်မပြုနိုင်ပါ။")

    countries = data.get("production_countries")
    if not isinstance(countries, list):
        countries = []
    countries = list(dict.fromkeys(
        str(item).strip() for item in countries
        if isinstance(item, str) and item.strip()
    ))
    year = str(data.get("release_year") or "").strip()
    if not re.fullmatch(r"\d{4}", year):
        year = ""
    if not countries or not year:
        return _safe_status("Gemini source များမှ ထုတ်လုပ်သည့်နိုင်ငံနှင့် ထွက်ရှိသည့်နှစ် နှစ်ခုလုံးကို မအတည်ပြုနိုင်ပါ။")

    overview = re.sub(r"\s+", " ", str(data.get("overview") or "")).strip()[:2500]
    if len(overview) < 60:
        overview = ""
    return {
        "found": True,
        "provider": "Gemini Google Search",
        "title": str(data.get("title") or clean).strip(),
        "year": year,
        "countries": countries,
        "original_language": str(data.get("original_language") or "").strip(),
        "directors": [str(x).strip() for x in data.get("directors", []) if isinstance(x, str) and x.strip()][:8],
        "genres": [str(x).strip() for x in data.get("genres", []) if isinstance(x, str) and x.strip()][:12],
        "overview": overview,
        "sources": sources[:8],
        "source_domains": sorted(domains),
        "status": ("GEMINI_RESEARCH_MODEL ဟောင်းကို gemini-3.8-flash သို့ အလိုအလျောက်ပြောင်းပြီး Google Search ဖြင့် အချက်အလက်ရရှိပါပြီ။ " if model_fallback_used else "Gemini Google Search ဖြင့် source domain မတူသော web ရင်းမြစ်များကို အခြေခံ၍ အချက်အလက်ရရှိပါပြီ။ ") + "Official source ဖြင့် ထပ်မံစစ်ဆေးပါ။",
    }
