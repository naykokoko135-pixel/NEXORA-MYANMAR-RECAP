"""Automatic editorial profiles for genre-aware, safe FFmpeg recap finishing."""
from __future__ import annotations

# These profiles select deterministic FFmpeg looks only; they never invent footage.
CATEGORY_PROFILES = {
    "anime": {"effect_preset": "anime", "audio_preset": "cinematic", "transition": "dissolve", "motion_preset": "pushin", "subtitle_style": "bold", "fade_seconds": 0.7},
    "donghua": {"effect_preset": "anime", "audio_preset": "cinematic", "transition": "smoothleft", "motion_preset": "drift", "subtitle_style": "cinematic", "fade_seconds": 0.7},
    "3d animation": {"effect_preset": "vivid", "audio_preset": "cinematic", "transition": "fade", "motion_preset": "pushin", "subtitle_style": "bold", "fade_seconds": 0.7},
    "cartoon": {"effect_preset": "vivid", "audio_preset": "voice", "transition": "wipeleft", "motion_preset": "panright", "subtitle_style": "bold", "fade_seconds": 0.7},
    "action": {"effect_preset": "action", "audio_preset": "cinematic", "transition": "wipeleft", "motion_preset": "pushin", "subtitle_style": "yellow", "fade_seconds": 0.8},
    "horror": {"effect_preset": "horror", "audio_preset": "cinematic", "transition": "fade", "motion_preset": "pushin", "subtitle_style": "cinematic", "fade_seconds": 0.7},
    "romance": {"effect_preset": "romance", "audio_preset": "soft", "transition": "dissolve", "motion_preset": "drift", "subtitle_style": "classic", "fade_seconds": 0.6},
    "documentary": {"effect_preset": "documentary", "audio_preset": "podcast", "transition": "cut", "motion_preset": "none", "subtitle_style": "minimal", "fade_seconds": 0.5},
    "movie": {"effect_preset": "cinematic", "audio_preset": "voice", "transition": "fade", "motion_preset": "pushin", "subtitle_style": "cinematic", "fade_seconds": 0.7},
    "default": {"effect_preset": "cinematic", "audio_preset": "voice", "transition": "fade", "motion_preset": "none", "subtitle_style": "classic", "fade_seconds": 0.6},
}

ALIASES = {
    "3d": "3d animation", "3danimation": "3d animation", "3d-animation": "3d animation",
    "animation": "3d animation", "films": "movie", "film": "movie",
    "thriller": "horror", "scary": "horror", "love": "romance",
    "news": "documentary", "nonfiction": "documentary",
}

def build_auto_edit_profile(category: str = "default", platform: str = "youtube") -> dict[str, str | float]:
    """Return a validated style bundle; platform is validated to prevent bad output presets."""
    key = str(category or "default").strip().casefold()
    key = ALIASES.get(key, key)
    if key not in CATEGORY_PROFILES:
        key = "default"
    if str(platform or "youtube").strip().casefold() not in {"youtube", "facebook", "tiktok"}:
        raise ValueError("Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမယ်။")
    return {"category": key, **CATEGORY_PROFILES[key]}

def list_auto_edit_categories() -> tuple[str, ...]:
    return tuple(sorted(k for k in CATEGORY_PROFILES if k != "default"))
