"""Subtle camera-motion presets for recap footage, implemented with FFmpeg only."""
from __future__ import annotations

MOTION_PRESETS = {
    "none": "",
    "pushin": "zoompan=z='min(zoom+0.0012,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=25",
    "pullout": "zoompan=z='if(eq(on,0),1.12,max(zoom-0.0012,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps=25",
    "panleft": "scale={scaled_width}:{scaled_height},crop={width}:{height}:x='(in_w-out_w)*(0.5-0.35*sin(t*0.30))':y='(in_h-out_h)/2'",
    "panright": "scale={scaled_width}:{scaled_height},crop={width}:{height}:x='(in_w-out_w)*(0.5+0.35*sin(t*0.30))':y='(in_h-out_h)/2'",
    "drift": "scale={scaled_width}:{scaled_height},crop={width}:{height}:x='(in_w-out_w)*(0.5+0.25*sin(t*0.22))':y='(in_h-out_h)*(0.5+0.18*cos(t*0.19))'",
}

def build_motion_filter(preset: str, width: int, height: int) -> str:
    key = str(preset or "none").strip().casefold()
    if key not in MOTION_PRESETS:
        raise ValueError("Motion preset မသိပါ။ ရနိုင်သော preset များ: " + ", ".join(sorted(MOTION_PRESETS)))
    if width <= 0 or height <= 0 or width > 3840 or height > 3840:
        raise ValueError("Motion output dimensions မမှန်ပါ။")
    template = MOTION_PRESETS[key]
    if not template:
        return ""
    return template.format(width=int(width), height=int(height),
                           scaled_width=int(width * 1.12), scaled_height=int(height * 1.12))
