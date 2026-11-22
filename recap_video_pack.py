"""Input and metadata guards for longer licensed recap preview generation."""
MAX_RECAP_SCRIPT_CHARS = 80000
INDIAN_COUNTRY_NAMES = {"india", "republic of india"}

def parse_recap_video_request(message_text: str, available_presets) -> tuple[str, str, str]:
    if not isinstance(message_text, str):
        raise ValueError("Command စာသားကို မဖတ်နိုင်ပါ။")
    first_line, separator, body = message_text.partition("\n")
    parts = first_line.strip().split(maxsplit=1)
    title = parts[1].strip() if len(parts) > 1 else ""
    if not title or len(title) > 120:
        raise ValueError("အသုံးပြုပုံ: /recapvideo <ခေါင်းစဉ်>")
    lines = body.strip().splitlines() if separator else []
    preset = "narrator"
    if lines and lines[0].strip().lower() in available_presets:
        preset = lines.pop(0).strip().lower()
    narration = "\n".join(lines).strip()
    # Empty narration signals automatic retrieval of a verified plot section.
    if len(narration) > MAX_RECAP_SCRIPT_CHARS:
        raise ValueError("Narration သည် စာလုံး ၈၀,၀၀၀ ထက် မကျော်ရပါ။")
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
    if not isinstance(audio_mp3, bytes) or not audio_mp3 or len(audio_mp3) > 45 * 1024 * 1024:
        raise ValueError("Narration MP3 သည် ဗလာဖြစ်နေခြင်း သို့မဟုတ် 45 MB ထက်ကြီးနေပါတယ်။")
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


def format_original_visual_fallback_notice(title: str, search_failed: bool = False) -> str:
    """Explain that the renderer will continue with NEXORA-authored abstract cards."""
    clean_title = " ".join(str(title or "").split())[:120] or "ဤခေါင်းစဉ်"
    if search_failed:
        reason = (
            f"{clean_title} အတွက် Commons ရင်းမြစ်ကို ယခုချိန်တွင် စစ်ဆေးမရပါ။ "
            "မသက်ဆိုင်သော သို့မဟုတ် မအတည်ပြုထားသော footage ကို မသုံးထားပါ။"
        )
    else:
        reason = format_no_licensed_footage_message(clean_title).replace(
            "MP4 မထုတ်ထားပါ။", "မူရင်း footage မသုံးထားပါ။"
        )
    return (
        reason + "\n\nNEXORA ကိုယ်တိုင်ဖန်တီးသော Original Abstract Visuals ဖြင့် "
        "MP4 ဆက်ထုတ်နေပါတယ်။ ဒီပုံများသည် မူရင်း Anime/Film ဇာတ်ဝင်ခန်း မဟုတ်ပါ။"
    )


PLATFORM_RECAP_DURATION_SECONDS = {
    "youtube": (46 * 60, 60 * 60),
    "facebook": (46 * 60, 60 * 60),
    "tiktok": (4 * 60, 7 * 60),
}


def validate_platform_recap_duration(platform: str, duration_seconds: float) -> dict:
    """Require measured narration duration to match the selected platform's brief."""
    import math

    key = str(platform or "").strip().casefold()
    if key not in PLATFORM_RECAP_DURATION_SECONDS:
        return {"ok": False, "platform": key, "status": "NOT READY", "issues": ["youtube/facebook/tiktok ကို ရွေးပါ။"]}
    if isinstance(duration_seconds, bool):
        return {"ok": False, "platform": key, "status": "NOT READY", "issues": ["Audio ကြာချိန် မမှန်ပါ။"]}
    try:
        duration = float(duration_seconds)
    except (TypeError, ValueError):
        duration = float("nan")
    if not math.isfinite(duration) or duration <= 0:
        return {"ok": False, "platform": key, "status": "NOT READY", "issues": ["Audio ကြာချိန် မမှန်ပါ။"]}
    minimum, maximum = PLATFORM_RECAP_DURATION_SECONDS[key]
    if duration < minimum:
        status = "TOO SHORT"
        issue = f"Audio သည် သတ်မှတ်အနည်းဆုံး {minimum // 60} မိနစ်ထက် တိုနေသည်။"
    elif duration > maximum:
        status = "TOO LONG"
        issue = f"Audio သည် သတ်မှတ်အများဆုံး {maximum // 60} မိနစ်ထက် ရှည်နေသည်။"
    else:
        status = "DURATION PASS"
        issue = None
    return {
        "ok": issue is None,
        "platform": key,
        "status": status,
        "duration_seconds": round(duration, 3),
        "minimum_seconds": minimum,
        "maximum_seconds": maximum,
        "issues": [issue] if issue else [],
    }
