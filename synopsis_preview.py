"""Create a clearly labelled short preview from a catalogue-level synopsis.

A series synopsis is not an episode plot. This fallback is deliberately limited
to a short overview and never claims to be a full season/episode recap.
"""
import json
import os
import re
import uuid
from html import unescape
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from openai_script_provider import generate_burmese_recap_script, AIScriptError
from gemini_script_provider import (
    generate_burmese_recap_script as generate_gemini_recap_script,
    gemini_script_status,
    GeminiScriptError,
)

GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
TRANSLATION_TIMEOUT_SECONDS = 20
MAX_TRANSLATION_CHARS = 3500
MYMEMORY_MAX_BYTES = 450


def _read_json(request: Request):
    with urlopen(request, timeout=TRANSLATION_TIMEOUT_SECONDS) as response:
        return json.loads(response.read(1_000_000).decode("utf-8"))


def _translate_google_chunk(chunk: str) -> str:
    """Unofficial, keyless Google endpoint; it can throttle or change."""
    params = urlencode({
        "client": "gtx",
        "sl": "auto",
        "tl": "my",
        "dt": "t",
        "q": chunk,
    })
    request = Request(
        GOOGLE_TRANSLATE_URL + "?" + params,
        headers={"User-Agent": "NEXORA-Myanmar-Recap/1.0"},
    )
    payload = _read_json(request)
    segments = payload[0] if isinstance(payload, list) and payload else []
    return "".join(
        str(segment[0]) for segment in segments
        if isinstance(segment, list) and segment and segment[0]
    ).strip()


def _split_utf8_chunks(text: str, max_bytes: int = MYMEMORY_MAX_BYTES):
    """Split on word boundaries without exceeding a provider's byte limit."""
    words = str(text or "").split()
    chunks = []
    current = ""

    for word in words:
        if len(word.encode("utf-8")) > max_bytes:
            if current:
                chunks.append(current)
                current = ""
            piece = ""
            for char in word:
                if piece and len((piece + char).encode("utf-8")) > max_bytes:
                    chunks.append(piece)
                    piece = ""
                piece += char
            if piece:
                chunks.append(piece)
            continue

        candidate = f"{current} {word}".strip()
        if current and len(candidate.encode("utf-8")) > max_bytes:
            chunks.append(current)
            current = word
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def _translate_mymemory_chunk(chunk: str) -> str:
    """Keyless secondary provider; its anonymous daily quota is limited."""
    email = os.getenv("MYMEMORY_EMAIL", "").strip()
    translated_parts = []
    for part in _split_utf8_chunks(chunk):
        query = {"q": part, "langpair": "en|my", "mt": "1"}
        if email:
            # MyMemory documents a higher daily quota when a contact email is supplied.
            query["de"] = email
        request = Request(
            "https://api.mymemory.translated.net/get?" + urlencode(query),
            headers={"User-Agent": "NEXORA-Myanmar-Recap/1.0"},
        )
        payload = _read_json(request)
        status = str(payload.get("responseStatus", "")) if isinstance(payload, dict) else ""
        if status != "200":
            raise ValueError("MyMemory unavailable")
        translated = unescape(
            str((payload.get("responseData") or {}).get("translatedText") or "")
        ).strip()
        if not translated or translated.casefold() == part.casefold():
            raise ValueError("MyMemory returned no translation")
        translated_parts.append(translated)
    return " ".join(translated_parts).strip()


def _translate_libretranslate_chunk(chunk: str) -> str:
    """Optional self-hosted or owner-configured LibreTranslate endpoint."""
    base_url = os.getenv("NEXORA_LIBRETRANSLATE_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("LibreTranslate is not configured")
    payload = {"q": chunk, "source": "en", "target": "my", "format": "text"}
    api_key = os.getenv("NEXORA_LIBRETRANSLATE_API_KEY", "").strip()
    if api_key:
        payload["api_key"] = api_key
    request = Request(
        base_url + "/translate",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "NEXORA-Myanmar-Recap/1.0",
        },
        method="POST",
    )
    result = _read_json(request)
    translated = str((result or {}).get("translatedText") or "").strip()
    if not translated:
        raise ValueError("LibreTranslate returned no text")
    return unescape(translated)


def _translate_azure_chunk(chunk: str) -> str:
    """Optional Microsoft Translator F0/free-tier integration; key stays server-side."""
    key = os.getenv("AZURE_TRANSLATOR_KEY", "").strip()
    if not key:
        raise RuntimeError("Azure Translator is not configured")
    region = os.getenv("AZURE_TRANSLATOR_REGION", "").strip()
    url = "https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&from=en&to=my"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json; charset=UTF-8",
        "X-ClientTraceId": str(uuid.uuid4()),
        "User-Agent": "NEXORA-Myanmar-Recap/1.0",
    }
    if region:
        headers["Ocp-Apim-Subscription-Region"] = region
    request = Request(
        url,
        data=json.dumps([{"text": chunk}]).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    result = _read_json(request)
    try:
        translated = str(result[0]["translations"][0]["text"]).strip()
    except (TypeError, KeyError, IndexError):
        translated = ""
    if not translated:
        raise ValueError("Azure Translator returned no text")
    return unescape(translated)


def _translate_google_cloud_chunk(chunk: str) -> str:
    """Optional Google Cloud Translation integration; billing/key are user-managed."""
    key = os.getenv("GOOGLE_CLOUD_TRANSLATE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Google Cloud Translation is not configured")
    url = "https://translation.googleapis.com/language/translate/v2?" + urlencode({"key": key})
    request = Request(
        url,
        data=json.dumps({
            "q": [chunk],
            "source": "en",
            "target": "my",
            "format": "text",
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "NEXORA-Myanmar-Recap/1.0",
        },
        method="POST",
    )
    result = _read_json(request)
    try:
        translated = str(result["data"]["translations"][0]["translatedText"]).strip()
    except (TypeError, KeyError, IndexError):
        translated = ""
    if not translated:
        raise ValueError("Google Cloud Translation returned no text")
    return unescape(translated)


def _has_myanmar_text(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    myanmar_chars = sum(1 for char in text if "\u1000" <= char <= "\u109f")
    return myanmar_chars >= max(1, int(len(text) * 0.12))


def _split_translation_chunks(text: str, max_chars: int = 3000):
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        split_at = max(
            remaining.rfind(". ", 0, max_chars),
            remaining.rfind("! ", 0, max_chars),
            remaining.rfind("? ", 0, max_chars),
            remaining.rfind(" ", 0, max_chars),
        )
        if split_at < 300:
            split_at = max_chars
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return chunks


def _provider_error_label(error: Exception) -> str:
    """Return a safe diagnostic label without URLs, request bodies, or secrets."""
    if isinstance(error, HTTPError):
        return f"HTTP {error.code}"
    return type(error).__name__


def _configured_translation_providers():
    providers = []
    # Prefer Gemini when configured and paid AI has been explicitly enabled.
    if gemini_script_status()["configured"]:
        providers.append(("Gemini API (configured key)", generate_gemini_translation))
    providers.extend([
        ("Google Translate (keyless)", _translate_google_chunk),
        ("MyMemory (keyless)", _translate_mymemory_chunk),
    ])
    if os.getenv("NEXORA_LIBRETRANSLATE_URL", "").strip():
        providers.append(("LibreTranslate (configured endpoint)", _translate_libretranslate_chunk))
    if os.getenv("AZURE_TRANSLATOR_KEY", "").strip():
        providers.append(("Microsoft Translator (configured key)", _translate_azure_chunk))
    if os.getenv("GOOGLE_CLOUD_TRANSLATE_API_KEY", "").strip():
        providers.append(("Google Cloud Translation (configured key)", _translate_google_cloud_chunk))
    return providers


def _translate_synopsis_to_burmese(synopsis: str) -> str:
    """Try independent keyless and optional configured providers; fail closed."""
    text = " ".join(str(synopsis or "").split()).strip()
    if not text or len(text) > MAX_TRANSLATION_CHARS:
        raise AIScriptError("Synopsis ဘာသာပြန်ရန် စာသားအရွယ်အစား မမှန်ကန်ပါ။")

    translated_chunks = []
    provider_failures = {}
    providers = _configured_translation_providers()
    for chunk in _split_translation_chunks(text):
        translated = ""
        for name, provider in providers:
            try:
                candidate = provider(chunk)
                if _has_myanmar_text(candidate):
                    translated = candidate
                    break
                provider_failures[name] = "non-Burmese/empty response"
            except Exception as error:
                provider_failures[name] = _provider_error_label(error)
                continue
        if not translated:
            attempted = ", ".join(
                f"{name}: {provider_failures.get(name, 'not successful')}"
                for name, _ in providers
            )
            raise AIScriptError(
                "ဘာသာပြန်ရင်းမြစ်အားလုံးမှ အသုံးပြုနိုင်သော မြန်မာစာ မရရှိပါ။ "
                "ဇာတ်ကွက်ကို မခန့်မှန်းဘဲ ရပ်ထားပါတယ်။ "
                f"စစ်ဆေးမှု: {attempted}"
            )
        translated_chunks.append(translated)

    result = "\n".join(translated_chunks).strip()
    myanmar_chars = sum(1 for char in result if "\u1000" <= char <= "\u109f")
    if myanmar_chars < max(25, int(len(result) * 0.12)):
        raise AIScriptError(
            "ဘာသာပြန်ရလဒ်သည် မြန်မာစာအဖြစ် မလုံလောက်ပါ။ "
            "မှားယွင်းသော Narration မထုတ်ဘဲ ရပ်ထားပါတယ်။"
        )
    return result


def _build_free_synopsis_preview(topic: str, synopsis: str) -> str:
    translated = _translate_synopsis_to_burmese(synopsis)
    return (
        f"ဒီနေ့ NEXORA မှာ {topic} အကြောင်း မိတ်ဆက်ပေးပါမယ်။\n"
        f"{translated}\n\n"
        "သတိပြုရန် — ဤ Narration သည် Catalogue Synopsis ကို မြန်မာဘာသာပြန်ထားသော "
        "အတိုချုံး မိတ်ဆက် Preview သာဖြစ်ပါတယ်။ Episode တစ်ခုချင်း၏ ဇာတ်ကွက်၊ "
        "Season အဆုံးသတ် သို့မဟုတ် Full Recap မဟုတ်ပါ။ မူရင်း Synopsis တွင် "
        "မပါဝင်သော ဇာတ်ဝင်ခန်းနှင့် ဖြစ်ရပ်များကို မထည့်ထားပါ။"
    )


def generate_burmese_synopsis_preview(topic: str, synopsis: str, source_url: str):
    topic = " ".join(str(topic or "").split()).strip()
    synopsis = " ".join(str(synopsis or "").split()).strip()
    source_url = str(source_url or "").strip()
    if not topic or len(topic) > 180:
        raise ValueError("ခေါင်းစဉ် မမှန်ကန်ပါ။")
    if len(synopsis) < 100 or len(synopsis) > MAX_TRANSLATION_CHARS:
        raise ValueError("Series synopsis သည် အတိုချုံး Preview ပြုလုပ်ရန် မလုံလောက်ပါ။")
    if not source_url.startswith("https://"):
        raise ValueError("Synopsis ရင်းမြစ်လင့်ခ် မရရှိပါ။")

    notes = (
        "အရေးကြီးသော အရင်းအမြစ်အမျိုးအစား: SERIES-LEVEL SYNOPSIS ONLY။ "
        "ဤစာသည် Series တစ်ခုလုံး၏ မိတ်ဆက်အကျဉ်းသာဖြစ်ပြီး Episode တစ်ခုချင်း၏ plot၊ "
        "season ending သို့မဟုတ် ဇာတ်ကွက်အစဉ် မဟုတ်ပါ။ ထို့ကြောင့် 1-3 မိနစ်စာ "
        "မိတ်ဆက် Preview သာရေးပါ။ Episode recap သို့မဟုတ် full recap ဟု မခေါ်ပါနှင့်။ "
        "Synopsis ထဲတွင် မပါသော ဖြစ်ရပ်၊ ဇာတ်ကောင်၊ ပြိုင်ပွဲရလဒ်၊ ending၊ scene မတီထွင်ပါနှင့်။ "
        "အတိအကျမသိသောအရာကို ချန်ထားပါ။\n"
        f"Catalogue synopsis: {synopsis}\nSource: {source_url}"
    )
    try:
        script = generate_burmese_recap_script(
            topic, notes, platform="tiktok", duration="1-3"
        )
    except AIScriptError as openai_error:
        error_text = str(openai_error)
        if "Free-only mode" in error_text:
            script = _build_free_synopsis_preview(topic, synopsis)
        elif "Limit/Quota" in error_text:
            if not gemini_script_status()["configured"]:
                raise AIScriptError(
                    "OpenAI Quota ပြည့်နေပြီး Gemini Key မချိတ်ထားပါ။"
                ) from None
            try:
                script = generate_gemini_recap_script(
                    topic, notes, platform="tiktok", duration="1-3"
                )
            except GeminiScriptError as gemini_error:
                raise AIScriptError(
                    "OpenAI Quota ပြည့်နေပြီး Gemini Preview လည်း မအောင်မြင်ပါ: "
                    + str(gemini_error)
                ) from None
        else:
            raise
    return script.strip(), source_url
