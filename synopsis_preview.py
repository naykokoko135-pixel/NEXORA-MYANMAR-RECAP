"""Create a clearly labelled short preview from a catalogue-level synopsis.

A series synopsis is not an episode plot. This fallback is deliberately limited
to a short overview and never claims to be a full season/episode recap.
"""
import json
import re
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


def _translate_synopsis_to_burmese(synopsis: str) -> str:
    """Translate public catalogue synopsis text through Google's no-key web endpoint.

    This is a best-effort free fallback, not a guaranteed or official API. The
    caller fails closed if the response is unavailable or is not Burmese.
    """
    text = " ".join(str(synopsis or "").split()).strip()
    if not text or len(text) > MAX_TRANSLATION_CHARS:
        raise AIScriptError("Synopsis ဘာသာပြန်ရန် စာသားအရွယ်အစား မမှန်ကန်ပါ။")

    # Keep chunks bounded and split at sentence/space boundaries.
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= 3500:
            chunks.append(remaining)
            break
        split_at = max(remaining.rfind(". ", 0, 3500), remaining.rfind("! ", 0, 3500),
                       remaining.rfind("? ", 0, 3500), remaining.rfind(" ", 0, 3500))
        if split_at < 500:
            split_at = 3500
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    translated_chunks = []
    try:
        for chunk in chunks:
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
            with urlopen(request, timeout=TRANSLATION_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read(1_000_000).decode("utf-8"))
            segments = payload[0] if isinstance(payload, list) and payload else []
            translated = "".join(
                str(segment[0]) for segment in segments
                if isinstance(segment, list) and segment and segment[0]
            ).strip()
            if not translated:
                raise ValueError("empty translation")
            translated_chunks.append(translated)
    except Exception as exc:
        raise AIScriptError(
            "Free Burmese translation service ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။ "
            "ဇာတ်ကွက်ကို မခန့်မှန်းဘဲ ရပ်ထားပါတယ်။"
        ) from exc

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
            # No paid AI and no configured translation model: use a free,
            # bounded translation path. It remains explicitly synopsis-only.
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
