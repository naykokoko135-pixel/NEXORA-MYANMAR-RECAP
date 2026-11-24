"""Validated styled subtitle presets for optional FFmpeg hard-burn captions."""
from __future__ import annotations

SUBTITLE_STYLES = {
    "classic": "FontName=Noto Sans Myanmar,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&HCC000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=42,Bold=0",
    "bold": "FontName=Noto Sans Myanmar,FontSize=28,PrimaryColour=&H0000FFFF,OutlineColour=&HFF000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=48,Bold=1",
    "cinematic": "FontName=Noto Sans Myanmar,FontSize=25,PrimaryColour=&H00FFFFFF,OutlineColour=&HCC000000,BorderStyle=1,Outline=2,Shadow=2,Alignment=2,MarginV=50,Bold=1",
    "minimal": "FontName=Noto Sans Myanmar,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H99000000,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV=34,Bold=0",
    "yellow": "FontName=Noto Sans Myanmar,FontSize=26,PrimaryColour=&H0000D7FF,OutlineColour=&HFF000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=48,Bold=1",
}

def build_subtitle_filter(srt_path: str, style: str = "classic") -> str:
    key = str(style or "classic").strip().casefold()
    if key not in SUBTITLE_STYLES:
        raise ValueError("Subtitle style မသိပါ။ " + ", ".join(sorted(SUBTITLE_STYLES)))
    path = str(srt_path)
    if not path or any(char in path for char in "\n\r'"):
        raise ValueError("Subtitle file path မမှန်ပါ။")
    return f"subtitles=filename='{path}':force_style='{SUBTITLE_STYLES[key]}'"
