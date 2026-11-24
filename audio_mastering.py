"""Safe FFmpeg audio-mastering presets for narration-led NEXORA edits."""
from __future__ import annotations

AUDIO_PRESETS = {
    "voice": "highpass=f=75,lowpass=f=15500,acompressor=threshold=0.12:ratio=2.5:attack=20:release=250,loudnorm=I=-16:TP=-1.5:LRA=11",
    "cinematic": "highpass=f=55,lowpass=f=18000,acompressor=threshold=0.16:ratio=2:attack=25:release=300,loudnorm=I=-18:TP=-1.5:LRA=14",
    "podcast": "highpass=f=85,lowpass=f=14000,acompressor=threshold=0.10:ratio=3:attack=10:release=180,loudnorm=I=-16:TP=-1.0:LRA=8",
    "soft": "highpass=f=65,lowpass=f=15000,acompressor=threshold=0.18:ratio=1.8:attack=35:release=350,loudnorm=I=-19:TP=-2:LRA=12",
    "raw": "aresample=async=1",
}


def build_audio_filter(preset: str) -> str:
    key = str(preset or "voice").strip().casefold()
    if key not in AUDIO_PRESETS:
        raise ValueError("Audio preset မသိပါ။ ရနိုင်သော preset များ: " + ", ".join(sorted(AUDIO_PRESETS)))
    return AUDIO_PRESETS[key]
