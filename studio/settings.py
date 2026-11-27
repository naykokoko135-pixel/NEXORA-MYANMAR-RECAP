"""Persistent, validated studio settings (platform configs, automation, AI providers, voice defaults)."""
import os
import copy
import re

from .base import config
from . import core, db

RULES = {p: {"min": v["min"], "max": v["max"]} for p, v in config.PLATFORMS.items()}
YOUTUBE_URL = config.YOUTUBE_URL
FACEBOOK_URL = config.FACEBOOK_URL

# preset id -> (edge voice, pitch, rate, gender, label)
_LABELS = {
    "story_female": ("female", "Burmese female – storyteller (Nilar)"), "story_male": ("male", "Burmese male – storyteller (Thiha)"),
    "young_female": ("female", "Burmese female – young"), "young_male": ("male", "Burmese male – young"),
    "elder_male": ("male", "Burmese male – elder"), "villain": ("male", "Burmese male – dark / villain"),
    "comic": ("female", "Burmese female – playful"), "mystery": ("male", "Burmese male – mystery"),
}
OFFLINE_PRESET = "offline_my"


def voice_presets() -> list[dict]:
    out = []
    for pid, (voice, pitch, rate) in config.VOICE_PRESETS.items():
        gender, label = _LABELS.get(pid, ("female" if "Nilar" in voice else "male", pid))
        out.append({"id": pid, "label": label, "gender": gender, "engine": "edge-tts", "voice": pid, "engine_voice": voice,
                    "note": f"Microsoft Edge neural voice {voice}, pitch {pitch}, rate {rate}. Needs internet access to the Edge TTS service."})
    return out


def resolve_voice(value: str) -> str:
    """Accept a preset id or a raw edge voice name; return a preset id."""
    v = (value or "").strip()
    if v in config.VOICE_PRESETS or v == OFFLINE_PRESET:
        return v
    for pid, (voice, _p, _r) in config.VOICE_PRESETS.items():
        if v == voice:
            return pid
    raise ValueError(f"Unknown voice '{value}'")


def default_cta(platform: str) -> str:
    if platform == "tiktok":
        return (f"ဇာတ်လမ်းအပြည့်အစုံကို YouTube နဲ့ Facebook မှာ ဆက်ကြည့်ပါ။\nYouTube: {YOUTUBE_URL}\nFacebook: {FACEBOOK_URL}")
    return (f"Subscribe and follow for daily recaps.\nYouTube: {YOUTUBE_URL}\nFacebook: {FACEBOOK_URL}")


def platform_defaults(platform: str) -> dict:
    tk = platform == "tiktok"
    return {
        "enabled": True, "target_min": config.PLATFORMS[platform]["target"],
        "format": "vertical_9_16" if tk else "landscape_16_9", "resolution": "720p",
        "voice": "story_female", "voice_profile": "", "srt_langs": ["en", "my"], "burn_subs": "en",
        "cta": default_cta(platform), "publish_mode": "draft", "export_wav": False, "use_assets": True,
    }


def validate_platform_config(platform: str, cfg: dict) -> dict:
    """Return a normalised copy or raise ValueError with a user-facing message."""
    if platform not in core.PLATFORMS:
        raise ValueError("Unknown platform")
    c = {**platform_defaults(platform), **{k: v for k, v in (cfg or {}).items() if k in platform_defaults(platform)}}
    r = RULES[platform]
    try:
        c["target_min"] = float(c["target_min"])
    except (TypeError, ValueError):
        raise ValueError("target_min must be a number of minutes")
    if not (r["min"] <= c["target_min"] <= r["max"]):
        raise ValueError(f"{platform.title()} target must be between {r['min']} and {r['max']} minutes")
    if c["format"] not in core.FORMATS:
        raise ValueError("Unknown video format")
    if platform == "tiktok" and c["format"] != "vertical_9_16":
        raise ValueError("TikTok videos must use the vertical 9:16 format")
    if c["resolution"] not in core.RESOLUTIONS:
        raise ValueError("Unknown resolution")
    c["voice"] = resolve_voice(c["voice"])
    c["voice_profile"] = re.sub(r"[^A-Za-z0-9_-]", "", str(c.get("voice_profile") or ""))[:40]
    langs = c["srt_langs"]
    if not isinstance(langs, list) or not langs or any(x not in ("en", "my") for x in langs):
        raise ValueError("srt_langs must be a non-empty list containing 'en' and/or 'my'")
    c["srt_langs"] = sorted(set(langs), key=["en", "my"].index)
    if c["burn_subs"] not in ("en", "none"):
        raise ValueError("burn_subs must be 'en' or 'none'")
    if c["burn_subs"] == "en" and "en" not in c["srt_langs"]:
        raise ValueError("English subtitles must be generated to burn them in")
    if c["publish_mode"] not in ("draft", "auto"):
        raise ValueError("publish_mode must be 'draft' or 'auto'")
    c["cta"] = str(c["cta"] or "").strip()[:1500]
    if platform == "tiktok":
        if "youtube.com/@ze.recab.channel" not in c["cta"] or "facebook.com/share/1CSZfXHwPd" not in c["cta"]:
            raise ValueError("TikTok CTA must contain both the YouTube and the Facebook channel links")
    for k in ("enabled", "export_wav", "use_assets"):
        c[k] = bool(c[k])
    return c


# ------------------------------------------------------------------ platform store
def platforms() -> dict:
    stored = db.kv_get("platforms", {}) or {}
    out = {}
    for p in core.PLATFORMS:
        try:
            out[p] = validate_platform_config(p, stored.get(p, {}))
        except ValueError:
            out[p] = platform_defaults(p)
    return out


def set_platform(platform: str, patch: dict) -> dict:
    if not isinstance(patch, dict):
        raise ValueError("Body must be an object")
    allowed = set(platform_defaults(platform))
    unknown = set(patch) - allowed
    if unknown:
        raise ValueError("Unknown field(s): " + ", ".join(sorted(unknown)))
    stored = db.kv_get("platforms", {}) or {}
    merged = validate_platform_config(platform, {**platforms()[platform], **patch})
    stored[platform] = merged
    db.kv_set("platforms", stored)
    return merged


# ------------------------------------------------------------------ automation
AUTOMATION_DEFAULTS = {
    "state": "stopped", "schedule": "06:00", "platforms": {p: True for p in core.PLATFORMS}, "publish_mode": "draft",
    "retry": {"max_attempts": 3, "backoff_s": 60}, "storage": {"min_free_gb": 3.0}, "last_run_date": None,
}


def automation() -> dict:
    s = copy.deepcopy(AUTOMATION_DEFAULTS)
    stored = db.kv_get("automation", {}) or {}
    for k, v in stored.items():
        if isinstance(v, dict) and isinstance(s.get(k), dict):
            s[k].update(v)
        else:
            s[k] = v
    return s


def save_automation(s: dict):
    db.kv_set("automation", s)


def update_automation(patch: dict) -> dict:
    if not isinstance(patch, dict):
        raise ValueError("Body must be an object")
    s = automation()
    if "schedule" in patch:
        core.parse_hhmm(patch["schedule"])
        h, m = core.parse_hhmm(patch["schedule"])
        s["schedule"] = f"{h:02d}:{m:02d}"
    if "platforms" in patch:
        p = patch["platforms"]
        if not isinstance(p, dict) or set(p) - set(core.PLATFORMS):
            raise ValueError("platforms must map youtube/facebook/tiktok to booleans")
        s["platforms"] = {**s["platforms"], **{k: bool(v) for k, v in p.items()}}
        if not any(s["platforms"].values()):
            raise ValueError("Enable at least one platform")
    if "publish_mode" in patch:
        if patch["publish_mode"] not in ("draft", "auto"):
            raise ValueError("publish_mode must be 'draft' or 'auto'")
        s["publish_mode"] = patch["publish_mode"]
    if "retry" in patch:
        r = patch["retry"] or {}
        a, b = int(r.get("max_attempts", s["retry"]["max_attempts"])), int(r.get("backoff_s", s["retry"]["backoff_s"]))
        if not (1 <= a <= 10) or not (0 <= b <= 86400):
            raise ValueError("max_attempts must be 1-10 and backoff_s 0-86400")
        s["retry"] = {"max_attempts": a, "backoff_s": b}
    if "storage" in patch:
        mf = float((patch["storage"] or {}).get("min_free_gb", s["storage"]["min_free_gb"]))
        if not (0 <= mf <= 1000):
            raise ValueError("min_free_gb must be between 0 and 1000")
        s["storage"] = {"min_free_gb": mf}
    save_automation(s)
    return s


def effective_publish_mode(platform_mode: str) -> str:
    """Auto-publish only when BOTH the platform and the global automation setting say so (safety default: draft)."""
    return "auto" if platform_mode == "auto" and automation()["publish_mode"] == "auto" else "draft"


# ------------------------------------------------------------------ AI providers
OPENAI_MODELS = list(dict.fromkeys(([os.environ["OPENAI_MODEL"]] if os.environ.get("OPENAI_MODEL") else []) + ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"]))
GEMINI_MODELS = list(dict.fromkeys(config.GEMINI_MODELS + ["gemini-2.0-flash", "gemini-1.5-flash"]))


def ai_settings() -> dict:
    s = {"primary": "openai", "fallback": True, "models": {"openai": OPENAI_MODELS[0], "gemini": config.GEMINI_MODELS[0] if config.GEMINI_MODELS else GEMINI_MODELS[0]}}
    stored = db.kv_get("ai", {}) or {}
    s["primary"] = stored.get("primary", s["primary"])
    s["fallback"] = stored.get("fallback", s["fallback"])
    s["models"].update(stored.get("models", {}))
    return s


def update_ai(patch: dict) -> dict:
    s = ai_settings()
    if "primary" in patch:
        if patch["primary"] not in ("openai", "gemini"):
            raise ValueError("primary must be 'openai' or 'gemini'")
        s["primary"] = patch["primary"]
    if "fallback" in patch:
        s["fallback"] = bool(patch["fallback"])
    for k, v in (patch.get("models") or {}).items():
        if k not in ("openai", "gemini"):
            raise ValueError("Unknown provider in models")
        v = str(v or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{2,80}", v):
            raise ValueError("Model name has invalid characters")
        s["models"][k] = v
    db.kv_set("ai", s)
    return s


# ------------------------------------------------------------------ voice defaults
def voice_settings() -> dict:
    s = {"default_voice": "story_female", "default_profile": "", "rate": "+0%", "pitch": "+0Hz"}
    s.update(db.kv_get("voice_settings", {}) or {})
    return s


def update_voice_settings(patch: dict) -> dict:
    s = voice_settings()
    if "default_voice" in patch:
        s["default_voice"] = resolve_voice(patch["default_voice"])
    if "default_profile" in patch:
        s["default_profile"] = re.sub(r"[^A-Za-z0-9_-]", "", str(patch["default_profile"] or ""))[:40]
    if "rate" in patch:
        v = str(patch["rate"]).strip()
        if re.fullmatch(r"[+-]?\d{1,3}", v):
            v = f"{int(v):+d}%"
        if not re.fullmatch(r"[+-]\d{1,3}%", v) or abs(int(v[:-1])) > 100:
            raise ValueError("rate must look like +10% or -15% (range ±100%)")
        s["rate"] = v
    if "pitch" in patch:
        v = str(patch["pitch"]).strip()
        if re.fullmatch(r"[+-]?\d{1,3}", v):
            v = f"{int(v):+d}Hz"
        if not re.fullmatch(r"[+-]\d{1,3}Hz", v) or abs(int(v[:-2])) > 100:
            raise ValueError("pitch must look like +5Hz or -8Hz (range ±100Hz)")
        s["pitch"] = v
    db.kv_set("voice_settings", s)
    return s
