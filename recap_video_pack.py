"""Input and metadata guards for longer licensed recap preview generation."""
MAX_RECAP_SCRIPT_CHARS = 6000
INDIAN_COUNTRY_NAMES = {"india", "republic of india"}

def parse_recap_video_request(message_text: str, available_presets) -> tuple[str, str, str]:
    if not isinstance(message_text, str):
        raise ValueError("Command စာသားကို မဖတ်နိုင်ပါ။")
    first_line, separator, body = message_text.partition("\n")
    parts = first_line.strip().split(maxsplit=1)
    title = parts[1].strip() if len(parts) > 1 else ""
    if not title or len(title) > 120:
        raise ValueError("အသုံးပြုပုံ: /recapvideo <ခေါင်းစဉ်> ပြီးနောက် narration ထည့်ပါ။")
    lines = body.strip().splitlines() if separator else []
    preset = "narrator"
    if lines and lines[0].strip().lower() in available_presets:
        preset = lines.pop(0).strip().lower()
    narration = "\n".join(lines).strip()
    if not narration:
        raise ValueError("အသုံးပြုပုံ: /recapvideo <ခေါင်းစဉ်>\nnarrator\nကိုယ်တိုင်ရေးထားသော မြန်မာ narration...")
    if len(narration) > MAX_RECAP_SCRIPT_CHARS:
        raise ValueError("Narration သည် စာလုံး ၆,၀၀၀ ထက် မကျော်ရပါ။ အပိုင်းခွဲပါ။")
    return title, preset, narration

def validate_non_indian_wikidata_metadata(metadata: dict) -> list[str]:
    if not isinstance(metadata, dict) or not metadata.get("found"):
        raise ValueError((metadata or {}).get("status", "Wikidata အတည်ပြုချက် မရရှိပါ။"))
    countries = metadata.get("countries")
    if not isinstance(countries, list):
        raise ValueError("Wikidata မူရင်းနိုင်ငံ မရရှိပါ။ မခန့်မှန်းထားပါ။")
    normalized = [str(country).strip() for country in countries if str(country).strip()]
    if not normalized:
        raise ValueError("Wikidata မူရင်းနိုင်ငံ မရရှိပါ။ မခန့်မှန်းထားပါ။")
    if any(country.casefold() in INDIAN_COUNTRY_NAMES for country in normalized):
        raise ValueError("အိန္ဒိယ သို့မဟုတ် အိန္ဒိယပူးတွဲထုတ်လုပ်မှုကို ဒီ Project မှာ မထည့်ပါ။")
    return normalized


def build_recap_video_sidecars(audio_mp3: bytes, subtitles_srt: str) -> tuple[bytes, bytes]:
    """Validate and prepare downloadable MP3/SRT assets alongside the rendered MP4."""
    if not isinstance(audio_mp3, bytes) or not audio_mp3 or len(audio_mp3) > 20 * 1024 * 1024:
        raise ValueError("Narration MP3 သည် ဗလာဖြစ်နေခြင်း သို့မဟုတ် 20 MB ထက်ကြီးနေပါတယ်။")
    if not isinstance(subtitles_srt, str) or not subtitles_srt.strip() or "-->" not in subtitles_srt:
        raise ValueError("မြန်မာ SRT စာတန်းပုံစံ မမှန်ပါ။")
    subtitle_bytes = subtitles_srt.encode("utf-8-sig")
    if len(subtitle_bytes) > 1024 * 1024:
        raise ValueError("SRT ဖိုင်သည် 1 MB ထက်ကြီးနေပါတယ်။")
    return audio_mp3, subtitle_bytes




def format_no_licensed_footage_message(title: str) -> str:
    """Explain why recapvideo stops when no strongly matched reusable video exists."""
    clean_title = " ".join(str(title or "").split())[:120] or "ဤခေါင်းစဉ်"
    return (
        f"{clean_title} အတွက် Wikimedia Commons တွင် ခေါင်းစဉ်နှင့် metadata ကိုက်ညီမှုခိုင်မာသော "
        "CC/Public Domain ဗီဒီယို မတွေ့ပါ။ Commons သည် အခမဲ့ပြန်သုံးခွင့်ရှိသော မီဒီယာကိုသာ လက်ခံပြီး "
        "မူပိုင်ခွင့်ရှိသော TV/DVD ဇာတ်ဝင်ခန်းများကို ပုံမှန်အားဖြင့် လက်မခံပါ။ "
        "မသက်ဆိုင်သော footage ကို အစားမထိုးထားပါ။ MP4 မထုတ်ထားပါ။"
    )
