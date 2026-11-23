"""Create a Burmese recap draft from an exact English Wikipedia plot source.

The source is community-edited and must not be presented as studio-verified canon.
"""
from urllib.parse import urlparse

from openai_script_provider import generate_burmese_recap_script, AIScriptError
from gemini_script_provider import generate_burmese_recap_script as generate_gemini_recap_script, gemini_script_status, GeminiScriptError
from synopsis_preview import _translate_synopsis_to_burmese

MAX_SOURCE_NOTES_CHARS = 5500
MIN_SOURCE_NOTES_CHARS = 80
PLATFORM_DURATIONS = {"youtube": "15-20", "facebook": "10-15", "tiktok": "1-3"}


def generate_burmese_recap_from_english_plot(
    topic: str, plot: dict, platform: str = "youtube"
) -> tuple[str, str]:
    """Translate/adapt a title-linked English plot section into Burmese narration."""
    if not isinstance(plot, dict) or not plot.get("found"):
        raise ValueError("English Wikipedia မှ အတည်ပြုထားသော Plot section မရှိပါ။")
    source_url = str(plot.get("source") or "").strip()
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.hostname != "en.wikipedia.org" or not parsed.path.startswith("/wiki/"):
        raise ValueError("English Plot ရင်းမြစ်လိပ်စာကို အတည်မပြုနိုင်ပါ။")
    source_text = " ".join(str(plot.get("plot_text") or "").split()).strip()
    if len(source_text) < MIN_SOURCE_NOTES_CHARS:
        raise ValueError("English Plot ရင်းမြစ်စာသား မလုံလောက်ပါ။")
    notes = (
        "English Wikipedia ၏ title-linked Plot section ဖြစ်သည်။ လူထုတည်းဖြတ်ရင်းမြစ်ဖြစ်၍ "
        "studio-verified canon ဟု မဆိုရ။ မသေချာသောအချက်များကို [အချက်အလက် ထပ်စစ်ရန်] ဟု မှတ်သားပါ။\n"
        + source_text[:MAX_SOURCE_NOTES_CHARS]
        + "\nSource: " + source_url
    )
    if platform not in PLATFORM_DURATIONS:
        raise ValueError("Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမယ်။")
    try:
        script = generate_burmese_recap_script(
            topic, notes, platform=platform, duration=PLATFORM_DURATIONS[platform]
        )
    except AIScriptError as openai_error:
        # Free-only mode must not block a short, source-derived Burmese preview.
        # Translate only a bounded excerpt; never stretch it to long-form duration.
        if "Free-only mode" in str(openai_error):
            excerpt = source_text[:MAX_SOURCE_NOTES_CHARS]
            boundary = max(excerpt.rfind(". "), excerpt.rfind("! "), excerpt.rfind("? "))
            if boundary >= 700:
                excerpt = excerpt[:boundary + 1]
            translated = _translate_synopsis_to_burmese(excerpt)
            script = (
                f"ဒီနေ့ NEXORA မှာ {topic} ရဲ့ ဇာတ်လမ်းအကျဉ်းကို မိတ်ဆက်ပေးပါမယ်။\\n"
                f"{translated}\\n\\n"
                "သတိပြုရန် — ဤသည် English Wikipedia Plot section မှ ရရှိသော "
                "အချက်အလက်ကို မြန်မာဘာသာပြန်ထားသည့် အတိုချုံး Preview သာဖြစ်သည်။ "
                "လူထုတည်းဖြတ်ရင်းမြစ်ဖြစ်ပြီး Full Recap မဟုတ်ပါ။ "
                "ရင်းမြစ်တွင် မပါသော ဖြစ်ရပ်များကို မထည့်ထားပါ။"
            )
            return script.strip(), source_url
        # Switch providers only for quota exhaustion; never retry OpenAI.
        if "Limit/Quota" not in str(openai_error):
            raise
        if not gemini_script_status()["configured"]:
            raise AIScriptError(
                "OpenAI API Quota ပြည့်နေပါတယ်။ OpenAI ကို ထပ်မခေါ်ထားပါ။ "
                "အခြား AI ဖြင့် ဆက်ရေးနိုင်ရန် Render Environment တွင် GEMINI_API_KEY လိုအပ်ပါတယ်။"
            ) from None
        try:
            script = generate_gemini_recap_script(
                topic, notes, platform=platform, duration=PLATFORM_DURATIONS[platform]
            )
        except GeminiScriptError as gemini_error:
            raise AIScriptError(
                "OpenAI Quota ပြည့်နေပြီး Gemini Fallback လည်း မအောင်မြင်ပါ: "
                + str(gemini_error)
            ) from None
    if not script.strip():
        raise ValueError("Burmese recap narration မရရှိပါ။")
    return script.strip(), source_url
