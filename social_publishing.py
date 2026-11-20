"""Fail-closed readiness and approval checks for official social publishing adapters.

This module deliberately does not upload anything. Platform-specific OAuth/API
adapters are enabled only after their official app approvals and credentials exist.
"""
from __future__ import annotations

import os
from pathlib import Path

PLATFORM_ENV = {
    "youtube": (
        "YOUTUBE_UPLOAD_CLIENT_ID",
        "YOUTUBE_UPLOAD_CLIENT_SECRET",
        "YOUTUBE_UPLOAD_REFRESH_TOKEN",
    ),
    "facebook": (
        "FACEBOOK_PAGE_ACCESS_TOKEN",
        "FACEBOOK_PAGE_ID",
    ),
    "tiktok": (
        "TIKTOK_CLIENT_KEY",
        "TIKTOK_CLIENT_SECRET",
        "TIKTOK_ACCESS_TOKEN",
        "TIKTOK_OPEN_ID",
    ),
}


class PublishingPreflightError(ValueError):
    """Raised when a video is not eligible for a publishing attempt."""


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def platform_readiness(platform: str, environ: dict | None = None) -> dict:
    """Return non-secret readiness information; never return credential values."""
    platform = (platform or "").strip().lower()
    if platform not in PLATFORM_ENV:
        raise ValueError("Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမယ်။")
    env = os.environ if environ is None else environ
    required = PLATFORM_ENV[platform]
    missing = [key for key in required if not str(env.get(key, "")).strip()]
    master_enabled = _enabled(env.get("SOCIAL_PUBLISHING_ENABLED"))
    platform_enabled = _enabled(env.get(f"{platform.upper()}_PUBLISH_ENABLED"))
    return {
        "platform": platform,
        "configured": not missing,
        "missing": missing,
        "master_enabled": master_enabled,
        "platform_enabled": platform_enabled,
        "ready": not missing and master_enabled and platform_enabled,
        "mode": "ready" if not missing and master_enabled and platform_enabled else "disabled_or_incomplete",
    }


def validate_publish_request(
    platform: str,
    video_path: str | Path,
    title: str,
    *,
    rights_confirmed: bool,
    human_approved: bool,
    public_posting_confirmed: bool = False,
) -> Path:
    """Validate a local MP4 and explicit rights/review gates before any adapter runs."""
    platform = (platform or "").strip().lower()
    if platform not in PLATFORM_ENV:
        raise PublishingPreflightError("Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမယ်။")
    path = Path(video_path)
    if path.suffix.lower() != ".mp4" or not path.is_file() or path.stat().st_size <= 0:
        raise PublishingPreflightError("တရားဝင် MP4 ဖိုင်တစ်ခု လိုအပ်ပါတယ်။")
    if not (title or "").strip():
        raise PublishingPreflightError("Video ခေါင်းစဉ် ထည့်ပါ။")
    if not rights_confirmed:
        raise PublishingPreflightError("Footage၊ music၊ image နှင့် script အသုံးပြုခွင့်ကို အတည်ပြုရပါမယ်။")
    if not human_approved:
        raise PublishingPreflightError("လူကိုယ်တိုင် နောက်ဆုံးစစ်ဆေးအတည်ပြုမှု လိုအပ်ပါတယ်။")
    if not public_posting_confirmed:
        raise PublishingPreflightError("Platform ပေါ်သို့ တင်မည့်လုပ်ဆောင်ချက်ကို သီးခြားအတည်ပြုရပါမယ်။")
    return path


def publishing_status(environ: dict | None = None) -> dict:
    """Summarize all platform gates without exposing tokens or secrets."""
    return {
        platform: platform_readiness(platform, environ)
        for platform in PLATFORM_ENV
    }
