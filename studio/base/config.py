import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
WORK_DIR = Path(os.getenv("WORK_DIR", "work"))
OUT_DIR = Path(os.getenv("OUT_DIR", "out"))
STATE_DIR = Path(os.getenv("STATE_DIR", "state"))
for _d in (DATA_DIR, WORK_DIR, OUT_DIR, STATE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
# Avoid model IDs retired by the API. Keep a current default even when an old
# GEMINI_MODELS value is still present in the deployment environment.
_RETIRED_GEMINI_MODELS = {"gemini-2.0-flash", "gemini-1.5-flash"}
GEMINI_MODELS = [
    m.strip() for m in os.getenv("GEMINI_MODELS", "gemini-3.8-flash").split(",")
    if m.strip() and m.strip() not in _RETIRED_GEMINI_MODELS
]
if not GEMINI_MODELS:
    GEMINI_MODELS = ["gemini-3.8-flash"]
LLM_DELAY = float(os.getenv("LLM_DELAY", "4.2"))  # free-tier rate limit
TMDB_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_TOKEN = os.getenv("TMDB_API_READ_ACCESS_TOKEN", "")  # production name (v4 bearer token); either credential enables TMDB
TMDB_ENABLED = bool(TMDB_KEY or TMDB_TOKEN)
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
CHARS_PER_SEC = float(os.getenv("CHARS_PER_SEC", "10"))  # initial estimate only; real length is measured

CATEGORIES = ["Anime", "Donghua", "Cartoon", "3D Animation", "International Movies"]

PLATFORMS = {
    "youtube": dict(min=46, max=60, target=49, w=1280, h=720, min_source=5000),
    "facebook": dict(min=46, max=60, target=49, w=1280, h=720, min_source=5000),
    "tiktok": dict(min=4, max=7, target=5, w=720, h=1280, min_source=1500),
}
PLATFORM_ORDER = ["youtube", "facebook", "tiktok"]

YOUTUBE_URL = "https://youtube.com/@ze.recab.channel?si=vSwZyJfr-zF-C67n"
FACEBOOK_URL = "https://www.facebook.com/share/1CSZfXHwPd/"
CHANNEL_NAME = "Ze Recap"

VOICE_PRESETS = {
    "story_female": ("my-MM-NilarNeural", "+0Hz", "+0%"),
    "story_male": ("my-MM-ThihaNeural", "+0Hz", "+0%"),
    "young_female": ("my-MM-NilarNeural", "+6Hz", "+6%"),
    "young_male": ("my-MM-ThihaNeural", "+6Hz", "+6%"),
    "elder_male": ("my-MM-ThihaNeural", "-8Hz", "-10%"),
    "villain": ("my-MM-ThihaNeural", "-12Hz", "-6%"),
    "comic": ("my-MM-NilarNeural", "+10Hz", "+14%"),
    "mystery": ("my-MM-ThihaNeural", "-4Hz", "-14%"),
}

EFFECTS = ["fade in/out per scene", "animated gradient visuals (self-generated)", "progress bar",
           "channel watermark", "BGM auto-ducking", "loudnorm -16 LUFS", "burned English subtitles"]
