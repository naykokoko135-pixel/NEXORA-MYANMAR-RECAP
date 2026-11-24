"""Attach VoxCPM2 narration to the recap renderer with duration-scaled estimated captions.

The caption timing is proportional/estimated, not phoneme or word aligned. Creators
must review it against the generated speech before publishing.
"""
from __future__ import annotations

import io
import re
import wave

from subtitle_builder import build_burmese_srt


def _to_ms(match: re.Match) -> int:
    hours, minutes, seconds, millis = (int(value) for value in match.groups())
    return ((hours * 3600 + minutes * 60 + seconds) * 1000) + millis


def _stamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def build_estimated_srt_for_audio(script: str, wav_bytes: bytes) -> str:
    """Build estimated Burmese captions scaled to the actual WAV duration."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            duration_ms = round(wav.getnframes() * 1000 / wav.getframerate())
    except (wave.Error, EOFError, OSError, ZeroDivisionError) as exc:
        raise ValueError("Voice Clone WAV ဖိုင်ကို ဖတ်မရပါ။") from exc
    if duration_ms < 1000 or duration_ms > 60 * 60 * 1000:
        raise ValueError("Voice Clone WAV ကြာချိန်သည် ၁ စက္ကန့်မှ ၆၀ မိနစ်အတွင်း ဖြစ်ရပါမယ်။")
    estimated = build_burmese_srt(script)
    pattern = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")
    matches = list(pattern.finditer(estimated))
    if not matches:
        raise ValueError("SRT timestamp မထုတ်နိုင်ပါ။")
    original_end = _to_ms(matches[-1])
    if original_end <= 0:
        raise ValueError("SRT ခန့်မှန်းကြာချိန် မမှန်ပါ။")
    scale = duration_ms / original_end
    return pattern.sub(
        lambda match: _stamp(min(duration_ms, round(_to_ms(match) * scale))),
        estimated,
    )
