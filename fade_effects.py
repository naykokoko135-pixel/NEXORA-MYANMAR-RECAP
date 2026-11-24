"""Automatic fade-in/fade-out finishing filters for video and audio."""
from __future__ import annotations

def build_edge_fade_filters(duration: float, seconds: float = 0.6) -> tuple[str, str]:
    total = float(duration)
    fade = float(seconds)
    if total <= 0:
        raise ValueError("Media duration မမှန်ပါ။")
    if fade < 0 or fade > 5 or fade * 2 > total:
        raise ValueError("Fade ကြာချိန်သည် ၀ မှ ၅ စက္ကန့်အတွင်း၊ Video ကြာချိန်တစ်ဝက်ထက် မပိုရပါ။")
    if fade == 0:
        return "", ""
    start_out = total - fade
    video = f"fade=t=in:st=0:d={fade:.3f},fade=t=out:st={start_out:.3f}:d={fade:.3f}"
    audio = f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={start_out:.3f}:d={fade:.3f}"
    return video, audio
