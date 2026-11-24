"""CapCut-inspired offline visual looks for NEXORA's FFmpeg renderer.

All filters are fixed and deterministic; no remote templates or copyrighted assets
are fetched. These are color/texture looks, not a replacement for a full NLE.
"""
from __future__ import annotations

EFFECT_PRESETS = {
    "clean": "eq=contrast=1.03:saturation=1.04:brightness=0.005",
    "cinematic": "eq=contrast=1.12:saturation=1.12:brightness=-0.012,unsharp=5:5:0.55:3:3:0.0,vignette=PI/5",
    "action": "eq=contrast=1.18:saturation=1.28:brightness=0.005,unsharp=5:5:0.8:3:3:0.0",
    "anime": "eq=contrast=1.14:saturation=1.32:brightness=0.012,unsharp=5:5:0.7:3:3:0.0",
    "vintage": "eq=contrast=1.08:saturation=0.78:brightness=0.015,colorbalance=rs=0.04:gs=0.01:bs=-0.03,vignette=PI/4",
    "noir": "hue=s=0,eq=contrast=1.22:brightness=-0.015,unsharp=5:5:0.45:3:3:0.0",
    "dream": "eq=contrast=0.96:saturation=1.18:brightness=0.025,gblur=sigma=0.25",
    "warm": "eq=contrast=1.06:saturation=1.16:brightness=0.015,colorbalance=rs=0.08:gs=0.025:bs=-0.06",
    "cool": "eq=contrast=1.08:saturation=1.05:brightness=-0.005,colorbalance=rs=-0.05:gs=0.0:bs=0.08",
    "vivid": "eq=contrast=1.16:saturation=1.48:brightness=0.01",
    "soft": "eq=contrast=0.94:saturation=0.96:brightness=0.025,gblur=sigma=0.18",
    "film": "eq=contrast=1.10:saturation=0.90:brightness=0.005,noise=alls=4:allf=t+u,vignette=PI/6",
    "retro": "eq=contrast=1.05:saturation=0.72:brightness=0.02,colorbalance=rs=0.07:gs=0.015:bs=-0.05,vignette=PI/3",
    "bright": "eq=contrast=1.02:saturation=1.08:brightness=0.07",
    "dark": "eq=contrast=1.18:saturation=0.88:brightness=-0.07,vignette=PI/5",
    "pastel": "eq=contrast=0.90:saturation=0.82:brightness=0.04",
    "sports": "eq=contrast=1.22:saturation=1.35:brightness=0.015,unsharp=5:5:0.9:3:3:0.0",
    "horror": "eq=contrast=1.25:saturation=0.62:brightness=-0.04,colorbalance=gs=0.06:bs=0.04,vignette=PI/3",
    "romance": "eq=contrast=0.98:saturation=1.12:brightness=0.035,colorbalance=rs=0.05:gs=0.01:bs=-0.025",
    "documentary": "eq=contrast=1.05:saturation=0.98:brightness=0.005,unsharp=5:5:0.35:3:3:0.0",
}

PLATFORM_DIMENSIONS = {
    "youtube": (1280, 720),
    "facebook": (864, 1080),
    "tiktok": (720, 1280),
}


def build_effect_filter(preset: str, width: int, height: int) -> str:
    """Return a validated platform crop and selected visual-look filter graph."""
    key = str(preset or "cinematic").strip().casefold()
    if key not in EFFECT_PRESETS:
        raise ValueError(
            "Effect preset မသိပါ။ ရနိုင်သော preset များ: "
            + ", ".join(sorted(EFFECT_PRESETS))
        )
    if (width, height) not in set(PLATFORM_DIMENSIONS.values()):
        raise ValueError("Platform video dimensions မမှန်ပါ။")
    crop = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    return crop + "," + EFFECT_PRESETS[key] + ",setsar=1,format=yuv420p"
