"""OpenAI Responses API adapter for optional, parent-managed NEXORA script drafting.

No key is bundled. Requests are bounded, non-streaming, and never retried on quota
or billing errors. The model may organize creator-provided verified notes, but
must not invent plot events or claim access to copyrighted footage.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_TOPIC_CHARS = 180
MAX_NOTES_CHARS = 6000
MAX_OUTPUT_TOKENS = 10000
MAX_SCRIPT_CHARS = 30000
TIMEOUT_SECONDS = 240


class AIScriptError(RuntimeError):
    """Safe, user-displayable AI script generation failure."""


def openai_script_status() -> dict:
    key_present = bool(os.getenv("OPENAI_API_KEY", "").strip())
    return {
        "provider": "OpenAI",
        "configured": key_present,
        "model": os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


def generate_burmese_recap_script(topic: str, notes: str, platform: str = "youtube",
                                 duration: str = "8-10") -> str:
    """Draft a Burmese recap only from supplied notes; never fabricate missing plot."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise AIScriptError("OpenAI API မချိတ်ရသေးပါ။ အုပ်ထိန်းသူက Render Environment တွင် OPENAI_API_KEY ကို သတ်မှတ်ပေးရန် လိုအပ်ပါတယ်။")
    topic = " ".join(str(topic or "").split()).strip()
    notes = str(notes or "").strip()
    if not topic or len(topic) > MAX_TOPIC_CHARS:
        raise AIScriptError("ခေါင်းစဉ်သည် ဗလာမဖြစ်ရ၊ စာလုံး 180 ထက်မကျော်ရပါ။")
    if len(notes) < 80 or len(notes) > MAX_NOTES_CHARS:
        raise AIScriptError("Research Notes ကို စာလုံး 80 မှ 6,000 အတွင်း ထည့်ပါ။")
    if platform not in {"youtube", "facebook", "tiktok"}:
        raise AIScriptError("Platform မမှန်ကန်ပါ။")
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    duration_ranges = {"youtube": (15, 20), "facebook": (10, 15), "tiktok": (1, 3)}
    preset_ranges = {"1-3": (1, 3), "3-5": (3, 5), "5-7": (5, 7), "8-10": (8, 10), "10-15": (10, 15), "12-15": (12, 15), "15-20": (15, 20), "20-30": (20, 30), "30-45": (30, 45), "45-60": (45, 60)}
    min_minutes, max_minutes = preset_ranges.get(duration, duration_ranges[platform])
    prompt = (
        "သင်သည် NEXORA Myanmar Recap အတွက် မြန်မာဘာသာ Script Editor ဖြစ်သည်။ "
        "အောက်ပါ research notes များကိုသာ အခြေခံ၍ recap narration draft ရေးပါ။ ရင်းမြစ်သည် လူထုတည်းဖြတ်ရင်းမြစ်ဖြစ်ပါက studio-verified canon ဟု မဆိုပါနှင့်။ မသေချာသောအချက်များကို [အချက်အလက် ထပ်စစ်ရန်] ဟု မှတ်သားပါ။ "
        "Notes ထဲတွင် မပါသော ဇာတ်ကွက်၊ ဇာတ်ကောင်လုပ်ရပ်၊ ending၊ quote၊ episode detail မတီထွင်ပါနှင့်။ "
        "အချက်အလက်မလုံလောက်သည့်နေရာတွင် [အချက်အလက် ထပ်စစ်ရန်] ဟုမှတ်သားပါ။ "
        "မူရင်းဇာတ်ကား၏ dialogue ကို မကူးယူပါနှင့်။ မူရင်းဗီဒီယို footage ရှိသည်ဟု မဆိုပါနှင့်။ "
        "သုံးသပ်ချက်နှင့် ဖြစ်ရပ်မှန်ကို ခွဲရေးပါ။ Hook, context, chronological narration, "
        "transition, original commentary, closing တို့ကို သဘာဝကျသော မြန်မာစကားဖြင့် ဖွဲ့စည်းပါ။ "
        "မြန်မာ narration ပုံမှန်ပြောနှုန်း တစ်မိနစ်လျှင် စကားလုံး ၁၀၀ မှ ၁၂၀ ခန့်ဖြင့် ရည်မှန်းချိန်ပြည့်အောင် အသေးစိတ်ရေးပါ။ "
        "အချက်အလက်မရှိဘဲ ထပ်ခါထပ်ခါ မဖြည့်ပါနှင့်။ ထုတ်ဝေမီ source fact-check လုပ်ရန် သတိပေးပါ။\n\n"
        f"ခေါင်းစဉ်: {topic}\nPlatform: {platform}\nရည်မှန်းကြာချိန်: {duration} မိနစ် (အနည်းဆုံး {min_minutes}၊ အများဆုံး {max_minutes} မိနစ်)\n"
        f"Verified research notes:\n{notes}"
    )
    payload = json.dumps({
        "model": model,
        "input": prompt,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "store": False,
    }).encode("utf-8")
    request = Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            result = json.loads(response.read(1_000_000).decode("utf-8"))
    except HTTPError as exc:
        # Never echo provider response bodies; they may contain sensitive details.
        if exc.code == 429:
            raise AIScriptError("OpenAI API Limit/Quota ပြည့်နေသည်။ ထပ်မခေါ်ဘဲ ရပ်ထားပါတယ်။ Free Builder သို့ ပြောင်းသုံးပါ။") from None
        if exc.code in (401, 403):
            raise AIScriptError("OpenAI API authentication သို့မဟုတ် project permission မမှန်ပါ။ Render Secret ကို အုပ်ထိန်းသူက စစ်ဆေးပေးရန် လိုပါတယ်။") from None
        if exc.code >= 500:
            raise AIScriptError("OpenAI ဝန်ဆောင်မှု ယာယီမရနိုင်ပါ။ ထပ်ခါတလဲလဲ မခေါ်ဘဲ ရပ်ထားပါတယ်။") from None
        raise AIScriptError(f"OpenAI API တောင်းဆိုမှု မအောင်မြင်ပါ (HTTP {exc.code})။") from None
    except (URLError, TimeoutError, OSError):
        raise AIScriptError("OpenAI API သို့ ချိတ်ဆက်မရပါ။ အလိုအလျောက် ထပ်မခေါ်ထားပါ။") from None
    except (ValueError, TypeError, KeyError):
        raise AIScriptError("OpenAI API မှ ဖတ်ရှုနိုင်သော တုံ့ပြန်မှု မရရှိပါ။") from None

    output = []
    for item in result.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if isinstance(part, dict) and part.get("type") == "output_text":
                value = str(part.get("text") or "").strip()
                if value:
                    output.append(value)
    script = "\n".join(output).strip()
    if not script:
        raise AIScriptError("OpenAI မှ Script စာသား မရရှိပါ။")
    minimum_chars = {"youtube": 5000, "facebook": 3300, "tiktok": 250}[platform]
    if len(script) < minimum_chars:
        raise AIScriptError(
            "ရရှိသော ဇာတ်လမ်းအချက်အလက်ဖြင့် သတ်မှတ်ထားသော ကြာချိန်ပြည့် Script မရနိုင်သေးပါ။ "
            "ပိုမိုပြည့်စုံသော ဇာတ်လမ်းရင်းမြစ် လိုအပ်ပါတယ်။ အချက်အလက်မရှိဘဲ စာသားဖြည့်မထုတ်ထားပါ။"
        )
    if len(script) > MAX_SCRIPT_CHARS:
        raise AIScriptError("ထုတ်ပေးသော Script သည် စာလုံး 30,000 ထက် ကျော်နေပါတယ်။")
    return script
