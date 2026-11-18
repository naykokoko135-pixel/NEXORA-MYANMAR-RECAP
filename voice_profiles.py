"""Session-scoped storage for creator-owned prerecorded voice clips."""
from pathlib import Path

MAX_PROFILE_NAME_CHARS = 24
MAX_PROFILES = 12
MAX_AUDIO_BYTES = 20 * 1024 * 1024
ALLOWED_AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".ogg"}


def normalize_profile_name(name: str) -> str:
    cleaned = " ".join((name or "").strip().split())
    if not cleaned or len(cleaned) > MAX_PROFILE_NAME_CHARS or not all(c.isalnum() or c in " _-" for c in cleaned):
        raise ValueError("အမည်သည် ၁ မှ ၂၄ လုံးအတွင်းဖြစ်ပြီး စာလုံး၊ နံပါတ်၊ space၊ _၊ - သာ သုံးပါ။")
    return cleaned


def store_voice_profile(profiles: dict, name: str, filename: str, audio: bytes) -> None:
    key = normalize_profile_name(name)
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise ValueError("MP3/M4A/WAV/OGG ဖိုင်သာ လက်ခံပါတယ်။")
    if not isinstance(audio, bytes) or not audio or len(audio) > MAX_AUDIO_BYTES:
        raise ValueError("အသံဖိုင်သည် ဗလာမဖြစ်ရ၊ ၂၀ MB အောက် ဖြစ်ရပါမယ်။")
    if key not in profiles and len(profiles) >= MAX_PROFILES:
        raise ValueError("အသံ Profile အများဆုံး ၁၂ ခုသာ သိမ်းနိုင်ပါတယ်။")
    profiles[key] = {"filename": key + suffix, "audio": audio}


def delete_voice_profile(profiles: dict, name: str) -> None:
    key = normalize_profile_name(name)
    if key not in profiles:
        raise ValueError("သိမ်းထားသောအသံ Profile မတွေ့ပါ။")
    del profiles[key]
