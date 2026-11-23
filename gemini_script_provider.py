"""Optional Gemini fallback for Burmese recap drafting.

Uses only supplied, title-linked research notes. No keys are bundled, requests are
not retried on quota errors, and no plot details may be invented.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cost_controls import paid_ai_allowed

# Gemini 2.5 generation is restricted for some newly created projects. Use the
# current stable Flash model and its documented Interactions REST endpoint.
DEFAULT_MODEL = "gemini-3.8-flash"
API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
TIMEOUT_SECONDS = 240
MAX_OUTPUT_TOKENS = 30000
MIN_SCRIPT_CHARS = {"youtube": 5000, "facebook": 3300, "tiktok": 1800}


class GeminiScriptError(RuntimeError):
    """Safe, user-displayable Gemini generation failure."""


def gemini_script_status() -> dict:
    key_present = bool(os.getenv("GEMINI_API_KEY", "").strip())
    allowed = paid_ai_allowed()
    return {
        "provider": "Gemini",
        "key_present": key_present,
        "paid_ai_allowed": allowed,
        "configured": key_present and allowed,
        "model": os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
    }


def _extract_interaction_text(result: dict) -> str:
    """Extract only final model-output text from an Interactions response."""
    chunks = []
    for step in result.get("steps", []):
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        for part in step.get("content", []):
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                chunks.append(str(part["text"]).strip())
    return "\\n".join(chunk for chunk in chunks if chunk).strip()



def generate_burmese_translation(text: str) -> str:
    """Translate verified English synopsis text into Burmese without adding facts."""
    if not paid_ai_allowed():
        raise GeminiScriptError("Free-only mode ဖွင့်ထားသည်။ Gemini translation API ကို ပိတ်ထားသည်။")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiScriptError("Gemini API မချိတ်ရသေးပါ။ Render Environment တွင် GEMINI_API_KEY လိုအပ်ပါတယ်။")
    source = str(text or "").strip()
    if not source or len(source) > 3500:
        raise GeminiScriptError("ဘာသာပြန်မည့်စာသားသည် ဗလာမဖြစ်ရ၊ စာလုံး 3,500 ထက် မကျော်ရပါ။")
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    prompt = (
        "Translate the following English catalogue synopsis into natural, readable Burmese. "
        "Translation only: preserve every factual detail, names, sequence, and uncertainty. "
        "Do not summarize, expand, explain, add plot facts, invent scenes, or add headings. "
        "Return only the Burmese translation. If a proper name is unclear, keep its original spelling.\\n\\n"
        f"ENGLISH SOURCE:\\n{source}"
    )
    payload = json.dumps({
        "model": model, "input": prompt, "store": False,
        "generation_config": {"max_output_tokens": 5000},
    }).encode("utf-8")
    request = Request(API_URL, data=payload, headers={
        "x-goog-api-key": key, "Content-Type": "application/json", "Accept": "application/json",
    }, method="POST")
    try:
        with urlopen(request, timeout=90) as response:
            result = json.loads(response.read(1_000_000).decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise GeminiScriptError("Gemini API Limit/Quota ပြည့်နေပါတယ်။") from None
        if exc.code in (401, 403):
            raise GeminiScriptError("Gemini API Key သို့မဟုတ် permission မမှန်ပါ။") from None
        if exc.code == 404:
            raise GeminiScriptError("Gemini model သို့မဟုတ် Interactions API မရရှိပါ (HTTP 404)။") from None
        raise GeminiScriptError(f"Gemini API ဘာသာပြန်မှု မအောင်မြင်ပါ (HTTP {exc.code})။") from None
    except (URLError, TimeoutError, OSError):
        raise GeminiScriptError("Gemini API သို့ ချိတ်ဆက်မရပါ။") from None
    except (ValueError, TypeError, KeyError):
        raise GeminiScriptError("Gemini API မှ ဖတ်ရှုနိုင်သော ဘာသာပြန်ရလဒ် မရရှိပါ။") from None
    translated = _extract_interaction_text(result)
    if not translated:
        raise GeminiScriptError("Gemini မှ ဘာသာပြန်စာသား မရရှိပါ။")
    myanmar_chars = sum(1 for char in translated if "\\u1000" <= char <= "\\u109f")
    if myanmar_chars < max(8, int(len(translated) * 0.12)):
        raise GeminiScriptError("Gemini တုံ့ပြန်မှုတွင် မြန်မာစာ မလုံလောက်ပါ။")
    return translated.strip()


def generate_burmese_recap_script(topic: str, notes: str, platform: str = "youtube",
                                 duration: str = "46-60") -> str:
    if not paid_ai_allowed():
        raise GeminiScriptError("Free-only mode ဖွင့်ထားသည်။ အခကြေးငွေရှိနိုင်သော Gemini API ကို ပိတ်ထားသည်။")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiScriptError("Gemini API မချိတ်ရသေးပါ။ Render Environment တွင် GEMINI_API_KEY ထည့်ရန် လိုအပ်ပါတယ်။")
    topic = " ".join(str(topic or "").split()).strip()
    notes = str(notes or "").strip()
    if not topic or len(topic) > 180:
        raise GeminiScriptError("ခေါင်းစဉ်သည် ဗလာမဖြစ်ရ၊ စာလုံး 180 ထက်မကျော်ရပါ။")
    if len(notes) < 80 or len(notes) > 20000:
        raise GeminiScriptError("Research Notes ကို စာလုံး 80 မှ 20,000 အတွင်း ထည့်ပါ။")
    if platform not in MIN_SCRIPT_CHARS:
        raise GeminiScriptError("Platform မမှန်ကန်ပါ။")
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    longform_instruction = (
        "YouTube/Facebook 46-60 မိနစ်အတွက် PART 1, PART 2, PART 3 ဟု အတိအကျ သုံးပိုင်းသာ ခွဲပါ။ "
        "Part တစ်ခုစီကို ၁၅–၂၀ မိနစ်စာ အသေးစိတ် narration ရေးပြီး အစ၊ အကြောင်းအရာနှင့် ဆက်စပ်ချက် ပါစေ။ "
        if platform in {"youtube", "facebook"} and duration == "46-60" else ""
    )
    prompt = (
        "သင်သည် NEXORA Myanmar Recap အတွက် မြန်မာဘာသာ Script Editor ဖြစ်သည်။ "
        "အောက်ပါ research notes များကိုသာ အခြေခံ၍ recap narration ရေးပါ။ "
        "Notes ထဲတွင် မပါသော ဇာတ်ကွက်၊ ဇာတ်ကောင်လုပ်ရပ်၊ ending၊ quote၊ episode detail မတီထွင်ပါနှင့်။ "
        "မသေချာသောအချက်များကို [အချက်အလက် ထပ်စစ်ရန်] ဟု မှတ်သားပါ။ "
        "လူထုတည်းဖြတ်ရင်းမြစ်ကို studio-verified canon ဟု မဆိုပါနှင့်။ "
        "မူရင်း dialogue မကူးပါနှင့်။ သဘာဝကျသော မြန်မာစကားဖြင့် Hook, context, "
        "ဖြစ်ရပ်အစဉ်လိုက် narration, transition, ကိုယ်ပိုင်သုံးသပ်ချက်နှင့် closing ရေးပါ။ "
        "ဇာတ်လမ်းအချက်အလက် မလုံလောက်လျှင် စာသားထပ်ဖြည့်မည့်အစား အချက်အလက်လိုအပ်ကြောင်း ဖော်ပြပါ။ "
        + longform_instruction
        + "အချက်အလက်မရှိလျှင် အရှည်ပြည့်စေရန် မတီထွင်ပါနှင့်။ ရည်မှန်းကြာချိန်နှင့် ကိုက်ညီအောင် ပြည့်စုံစွာရေးပါ။\\n\\n"
        f"ခေါင်းစဉ်: {topic}\\nPlatform: {platform}\\nရည်မှန်းကြာချိန်: {duration} မိနစ်\\n"
        f"Verified research notes:\\n{notes}"
    )
    payload = json.dumps({
        "model": model,
        "input": prompt,
        "store": False,
        "generation_config": {"max_output_tokens": MAX_OUTPUT_TOKENS},
    }).encode("utf-8")
    request = Request(
        API_URL,
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
        if exc.code == 404:
            raise GeminiScriptError("Gemini model သို့မဟုတ် Interactions API မရရှိပါ (HTTP 404)။ GEMINI_MODEL ကို စစ်ဆေးရန် လိုပါတယ်။") from None
        if exc.code >= 500:
            raise GeminiScriptError("Gemini ဝန်ဆောင်မှု ယာယီမရနိုင်ပါ။ ထပ်မခေါ်ထားပါ။") from None
        raise GeminiScriptError(f"Gemini API တောင်းဆိုမှု မအောင်မြင်ပါ (HTTP {exc.code})။") from None
    except (URLError, TimeoutError, OSError):
        raise GeminiScriptError("Gemini API သို့ ချိတ်ဆက်မရပါ။ အလိုအလျောက် ထပ်မခေါ်ထားပါ။") from None
    except (ValueError, TypeError, KeyError):
        raise GeminiScriptError("Gemini API မှ ဖတ်ရှုနိုင်သော တုံ့ပြန်မှု မရရှိပါ။") from None

    script = _extract_interaction_text(result)
    if not script:
        raise GeminiScriptError("Gemini မှ Script စာသား မရရှိပါ။")
    minimum_chars = 28000 if platform == "youtube" and duration == "46-60" else 24000 if platform == "facebook" and duration == "46-60" else 18000 if platform == "youtube" and duration == "30-45" else MIN_SCRIPT_CHARS[platform]
    if len(script) < minimum_chars:
        raise GeminiScriptError(
            "Gemini မှ ရရှိသော Script သည် သတ်မှတ်ကြာချိန်အတွက် မလုံလောက်ပါ။ "
            "ဇာတ်လမ်းအချက်အလက်မရှိဘဲ စာသားမဖြည့်ထုတ်ထားပါ။"
        )
    if len(script) > 80000:
        raise GeminiScriptError("Gemini မှ ထုတ်ပေးသော Script သည် စာလုံး 80,000 ထက် ကျော်နေပါတယ်။")
    return script
