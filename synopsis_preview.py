"""Create a clearly labelled short preview from a catalogue-level synopsis.

A series synopsis is not an episode plot. This fallback is deliberately limited
to a 1-3 minute overview and never claims to be a full season/episode recap.
"""
from openai_script_provider import generate_burmese_recap_script, AIScriptError
from gemini_script_provider import (
    generate_burmese_recap_script as generate_gemini_recap_script,
    gemini_script_status,
    GeminiScriptError,
)


def generate_burmese_synopsis_preview(topic: str, synopsis: str, source_url: str):
    topic = " ".join(str(topic or "").split()).strip()
    synopsis = " ".join(str(synopsis or "").split()).strip()
    source_url = str(source_url or "").strip()
    if not topic or len(topic) > 180:
        raise ValueError("ခေါင်းစဉ် မမှန်ကန်ပါ။")
    if len(synopsis) < 100 or len(synopsis) > 3500:
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
        if "Limit/Quota" not in str(openai_error):
            raise
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
    return script.strip(), source_url
