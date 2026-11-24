"""Platform-aware output dimensions for standard and HD recap exports."""
from __future__ import annotations

QUALITY_DIMENSIONS = {
    "720p": {
        "youtube": (1280, 720),
        "facebook": (864, 1080),
        "tiktok": (720, 1280),
    },
    "1080p": {
        "youtube": (1920, 1080),
        "facebook": (1080, 1350),
        "tiktok": (1080, 1920),
    },
}

def resolve_output_dimensions(platform: str, quality: str = "720p") -> tuple[int, int]:
    key = str(quality or "720p").strip().lower()
    target = str(platform or "youtube").strip().lower()
    if key not in QUALITY_DIMENSIONS:
        raise ValueError("Quality သည် 720p သို့မဟုတ် 1080p ဖြစ်ရပါမယ်။")
    if target not in QUALITY_DIMENSIONS[key]:
        raise ValueError("Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမယ်။")
    return QUALITY_DIMENSIONS[key][target]
