"""Long-form creator-consented voice cloning for recap narration.

VoxCPM2 does not expose word-boundary timings. This module concatenates cloned
WAV chunks into MP3 and builds duration-scaled *estimated* SRT captions. The
captions are explicitly not described as word-aligned.
"""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
import tempfile
from pathlib import Path

from voxcpm_voice_clone import MAX_TEXT_CHARS, synthesize_cloned_burmese_voice

MAX_RECAP_CHARS = 80_000
MAX_OUTPUT_MP3_BYTES = 45 * 1024 * 1024
DURATION_RE = re.compile(r"Duration:\\s*(\\d{2,}):(\\d{2}):(\\d{2}(?:\\.\\d+)?)")


def split_clone_text(text: str, max_chars: int = MAX_TEXT_CHARS) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("မြန်မာ Narration စာသား ထည့်ပါ။")
    if len(cleaned) > MAX_RECAP_CHARS:
        raise ValueError("Narration သည် စာလုံး ၈၀,၀၀၀ ထက် ကျော်နေပါတယ်။")
    if not 100 <= int(max_chars) <= MAX_TEXT_CHARS:
        raise ValueError("Voice Clone အပိုင်းအရွယ်အစား မမှန်ပါ။")
    sentences = [s.strip() for s in re.split(r"(?<=[။!?])\\s*|\\n+", cleaned) if s.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > max_chars:
            split_at = sentence.rfind(" ", 0, max_chars + 1)
            if split_at < 1:
                split_at = max_chars
            piece, sentence = sentence[:split_at].strip(), sentence[split_at:].strip()
            if current:
                chunks.append(current)
                current = ""
            if piece:
                chunks.append(piece)
        candidate = (current + " " + sentence).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def _stamp(seconds: float) -> str:
    total = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def _caption_chunks(script: str, limit: int = 42) -> list[str]:
    result = []
    for paragraph in re.split(r"\\n+", script):
        remaining = paragraph.strip()
        while remaining:
            if len(remaining) <= limit:
                result.append(remaining)
                break
            split_at = remaining.rfind(" ", 0, limit + 1)
            if split_at < 1:
                split_at = limit
            result.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
    return [item for item in result if item]


def build_duration_scaled_srt(script: str, duration_seconds: float) -> str:
    """Build estimated caption timestamps spanning the measured audio duration."""
    duration = float(duration_seconds)
    if not script.strip() or not 0 < duration <= 3600:
        raise ValueError("Script သို့မဟုတ် Audio ကြာချိန် မမှန်ပါ။")
    captions = _caption_chunks(script)
    if not captions:
        raise ValueError("SRT ထုတ်ရန် စာသားမတွေ့ပါ။")
    weights = [max(1, len(item)) for item in captions]
    total_weight = sum(weights)
    cursor = 0.0
    blocks = []
    for index, (caption, weight) in enumerate(zip(captions, weights), start=1):
        start = cursor
        cursor = duration if index == len(captions) else cursor + duration * weight / total_weight
        end = max(start + 0.05, cursor)
        blocks.append(f"{index}\\n{_stamp(start)} --> {_stamp(end)}\\n{caption}")
    return "\\n\\n".join(blocks) + "\\n"


def _ffmpeg_duration(stderr: str) -> float:
    match = DURATION_RE.search(stderr or "")
    if not match:
        raise RuntimeError("Clone MP3 ကြာချိန်ကို FFmpeg ဖြင့် မဖတ်နိုင်ပါ။")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


async def synthesize_recap_in_creator_voice(
    text: str, filename: str, reference_audio: bytes
) -> tuple[bytes, str, float]:
    """Clone chunked narration, join to MP3, and return estimated SRT + duration."""
    chunks = split_clone_text(text)
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("FFmpeg မရရှိပါ။") from exc

    with tempfile.TemporaryDirectory(prefix="nexora-myvoice-recap-") as directory:
        work = Path(directory)
        wav_paths = []
        for index, chunk in enumerate(chunks, start=1):
            wav = await synthesize_cloned_burmese_voice(chunk, filename, reference_audio)
            if not wav or not wav.startswith(b"RIFF"):
                raise RuntimeError(f"ကိုယ်ပိုင်အသံ Part {index} WAV မမှန်ပါ။")
            path = work / f"part_{index:04d}.wav"
            path.write_bytes(wav)
            wav_paths.append(path)
        concat_list = work / "concat.txt"
        concat_list.write_text(
            "".join("file '" + path.as_posix().replace("'", "'\\''") + "'\\n" for path in wav_paths),
            encoding="utf-8",
        )
        output = work / "recap_voice.mp3"
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    ffmpeg, "-hide_banner", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list), "-vn", "-c:a", "libmp3lame", "-q:a", "3",
                    str(output),
                ],
                capture_output=True, text=True, timeout=900, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("ကိုယ်ပိုင်အသံ MP3 ပေါင်းစပ်မှု အချိန်ကျော်သွားပါတယ်။") from exc
        if result.returncode != 0 or not output.is_file() or output.stat().st_size <= 0:
            raise RuntimeError("ကိုယ်ပိုင်အသံ WAV များကို MP3 ပေါင်းစပ်မရပါ။")
        audio = output.read_bytes()
        if len(audio) > MAX_OUTPUT_MP3_BYTES:
            raise RuntimeError("ထုတ်ပေးသော MP3 သည် ၄၅ MB ထက် ကျော်နေပါတယ်။")
        duration = _ffmpeg_duration(result.stderr)
        return audio, build_duration_scaled_srt(text, duration), duration
