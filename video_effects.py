"""Reusable CapCut-inspired FFmpeg effect presets for NEXORA renders.

Presets are deterministic, offline, and safe to select by short preset ID.
They do not fetch copyrighted overlays, music, or templates.
"""
from __future__ import annotations

# Filter fragments use fixed constants only; never interpolate user-provided text.
EFFECT_PRESETS = {
    "clean": "eq=contrast=1.03:saturation=1.04:brightness=0.005,setsar=1",
    "cinematic": "eq=contrast=1.12:saturation=1.12:brightness=-0.012,"
                 "unsharp=5:5:0.55:3:3:0.0,vignette=PI/5,setsar=1",
    "action": "eq=contrast=1.18:saturation=1.28:brightness=0.005,"
              "unsharp=5:5:0.8:3:3:0.0,setsar=1",
    "anime": "eq=contrast=1.14:saturation=1.32:brightness=0.012,"
             "unsharp=5:5:0.7:3:3:0.0,setsar=1",
    "vintage": "eq=contrast=1.08:saturation=0.78:brightness=0.015,"
               "colorbalance=rs=0.04:gs=0.01:bs=-0.03,vignette=PI/4,setsar=1",
    "noir": "hue=s=0,eq=contrast=1.22:brightness=-0.015,"
            "unsharp=5:5:0.45:3:3:0.0,setsar=1",
    "dream": "eq=contrast=0.96:saturation=1.18:brightness=0.025,"
             "gblur=sigma=0.25,setsar=1",
}

def build_effect_filter(preset: str, width: int, height: int) -> str:
    """Return a validated platform crop + selected visual-effect filter graph."""
    key = str(preset or "cinematic").strip().casefold()
    if key not in EFFECT_PRESETS:
        raise ValueError(
            "Effect preset မသိပါ။ ရနိုင်သော preset များ: "
            + ", ".join(sorted(EFFECT_PRESETS))
        )
    if (width, height) not in {(1280, 720), (864, 1080), (720, 1280)}:
        raise ValueError("Platform video dimensions မမှန်ပါ။")
    crop = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    return crop + "," + EFFECT_PRESETS[key] + ",format=yuv420p"
