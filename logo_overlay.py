"""Validated FFmpeg logo-overlay graph builder for creator-provided brand marks."""
from __future__ import annotations

LOGO_POSITIONS = {
    "top-left": "24:24",
    "top-right": "W-w-24:24",
    "bottom-left": "24:H-h-24",
    "bottom-right": "W-w-24:H-h-24",
}

def build_logo_overlay_graph(logo_input_index: int, position: str = "bottom-right",
                             opacity: float = 0.88, video_filter: str = "") -> tuple[str, str]:
    key = str(position or "bottom-right").strip().casefold()
    if key not in LOGO_POSITIONS:
        raise ValueError("Logo position မမှန်ပါ။ top-left/top-right/bottom-left/bottom-right ကိုသုံးပါ။")
    alpha = float(opacity)
    if not 0.1 <= alpha <= 1.0:
        raise ValueError("Logo opacity သည် 0.1 မှ 1.0 အတွင်း ဖြစ်ရပါမယ်။")
    if logo_input_index < 1:
        raise ValueError("Logo input index မမှန်ပါ။")
    base = f"[0:v]{video_filter}[nexora_base];" if video_filter else "[0:v]null[nexora_base];"
    graph = (base + f"[{logo_input_index}:v]scale=160:160:force_original_aspect_ratio=decrease,format=rgba,"
             f"colorchannelmixer=aa={alpha:.2f}[nexora_logo];"
             f"[nexora_base][nexora_logo]overlay=x={LOGO_POSITIONS[key]}:format=auto[vout]")
    return graph, "[vout]"
