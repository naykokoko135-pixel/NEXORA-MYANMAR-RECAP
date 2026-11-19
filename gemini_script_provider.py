"""Optional Gemini fallback for Burmese recap drafting.

Uses only supplied, title-linked research notes. No keys are bundled, requests are
not retried on quota errors, and no plot details may be invented.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_MODEL = "gemini-2.5-flash"
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT_SECONDS = 240
MAX_OUTPUT_TOKENS = 10000
MIN_SCRIPT_CHARS = {"youtube": 5000, "facebook": 3300, "tiktok": 250}


class GeminiScriptError(RuntimeError):
    """Safe, user-displayable Gemini generation failure."""


def gemini_script_status() -> dict:
    return {
        "provider": "Gemini",
        "configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "model": os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
    }


def generate_burmese_recap_script(topic: str, notes: str, platform: str = "youtube",
                                 duration: str = "15-20") -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiScriptError("Gemini API မချိတ်ရသေးပါ။ Render Environment တွင် GEMINI_API_KEY ထည့်ရန် လိုအပ်ပါတယ်။")
    topic = " ".join(str(topic or "").split()).strip()
    notes = str(notes or "").strip()
    if not topic or len(topic) > 180:
        raise GeminiScriptError("ခေါင်းစဉ်သည် ဗလာမဖြစ်ရ၊ စာလုံး 180 ထက်မကျော်ရပါ။")
    if len(notes) < 80 or len(notes) > 6000:
        raise GeminiScriptError("Research Notes ကို စာလုံး 80 မှ 6,000 အတွင်း ထည့်ပါ။")
    if platform not in MIN_SCRIPT_CHARS:
        raise GeminiScriptError("Platform မမှန်ကန်ပါ။")
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    prompt = (
        "သင်သည် NEXORA Myanmar Recap အတွက် မြန်မာဘာသာ Script Editor ဖြစ်သည်။ "
        "အောက်ပါ research notes များကိုသာ အခြေခံ၍ recap narration ရေးပါ။ "
        "Notes ထဲတွင် မပါသော ဇာတ်ကွက်၊ ဇာတ်ကောင်လုပ်ရပ်၊ ending၊ quote၊ episode detail မတီထွင်ပါနှင့်။ "
        "မသေချာသောအချက်များကို [အချက်အလက် ထပ်စစ်ရန်] ဟု မှတ်သားပါ။ "
        "လူထုတည်းဖြတ်ရင်းမြစ်ကို studio-verified canon ဟု မဆိုပါနှင့်။ "
        "မူရင်း dialogue မကူးပါနှင့်။ သဘာဝကျသော မြန်မာစကားဖြင့် Hook, context, "
        "ဖြစ်ရပ်အစဉ်လိုက် narration, transition, ကိုယ်ပိုင်သုံးသပ်ချက်နှင့် closing ရေးပါ။ "
        "ဇာတ်လမ်းအချက်အလက် မလုံလောက်လျှင် စာသားထပ်ဖြည့်မည့်အစား အချက်အလက်လိုအပ်ကြောင်း ဖော်ပြပါ။ "
        "ရည်မှန်းကြာချိန်နှင့် ကိုက်ညီအောင် ပြည့်စုံစွာရေးပါ။\n\n"
        f"ခေါင်းစဉ်: {topic}\nPlatform: {platform}\nရည်မှန်းကြာချိန်: {duration} မိနစ်\n"
        f"Verified research notes:\n{notes}"
    )
    payload = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.35, "maxOutputTokens": MAX_OUTPUT_TOKENS},
    }).encode("utf-8")
    request = Request(
        f"{API_ROOT}/{model}:generateContent",
        data=payload,
        headers={
            "x-goog-api-key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            result = json.loads(response.read(1_000_000).decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise GeminiScriptError("Gemini API Limit/Quota ပြည့်နေပါတယ်။ ထပ်မခေါ်ဘဲ ရပ်ထားပါတယ်။") from None
        if exc.code in (401, 403):
            raise GeminiScriptError("Gemini API Key သို့မဟုတ် permission မမှန်ပါ။ Render Secret ကို စစ်ဆေးရန် လိုပါတယ်။") from None
        if exc.code >= 500:
            raise GeminiScriptError("Gemini ဝန်ဆောင်မှု ယာယီမရနိုင်ပါ။ ထပ်မခေါ်ထားပါ။") from None
        raise GeminiScriptError(f"Gemini API တောင်းဆိုမှု မအောင်မြင်ပါ (HTTP {exc.code})။") from None
    except (URLError, TimeoutError, OSError):
        raise GeminiScriptError("Gemini API သို့ ချိတ်ဆက်မရပါ။ အလိုအလျောက် ထပ်မခေါ်ထားပါ။") from None
    except (ValueError, TypeError, KeyError):
        raise GeminiScriptError("Gemini API မှ ဖတ်ရှုနိုင်သော တုံ့ပြန်မှု မရရှိပါ။") from None

    try:
        candidates = result.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", [])
        script = "\n".join(str(part.get("text", "")).strip() for part in parts
                            if isinstance(part, dict) and part.get("text")).strip()
    except (IndexError, AttributeError, TypeError):
        script = ""
    if not script:
        raise GeminiScriptError("Gemini မှ Script စာသား မရရှိပါ။")
    if len(script) < MIN_SCRIPT_CHARS[platform]:
        raise GeminiScriptError(
            "Gemini မှ ရရှိသော Script သည် သတ်မှတ်ကြာချိန်အတွက် မလုံလောက်ပါ။ "
            "ဇာတ်လမ်းအချက်အလက်မရှိဘဲ စာသားမဖြည့်ထုတ်ထားပါ။"
        )
    if len(script) > 30000:
        raise GeminiScriptError("Gemini မှ ထုတ်ပေးသော Script သည် စာလုံး 30,000 ထက် ကျော်နေပါတယ်။")
    return script
