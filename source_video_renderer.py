"""Render creator-owned or explicitly licensed source video with Burmese narration and SRT."""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path


class SourceVideoRenderError(ValueError):
    """Raised when an uploaded source video cannot be safely rendered."""


MAX_SOURCE_VIDEO_BYTES = 20 * 1024 * 1024
MAX_NARRATION_BYTES = 45 * 1024 * 1024
MAX_SRT_BYTES = 1024 * 1024
ALLOWED_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}
ALLOWED_AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".ogg"}
PLATFORM_DIMENSIONS = {
    "youtube": (1280, 720),
    "facebook": (864, 1080),
    "tiktok": (720, 1280),
}


def _srt_duration(text: str) -> float:
    times = re.findall(r"-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})", text)
    if not times:
        raise SourceVideoRenderError("SRT timestamp မမှန်ပါ။")
    h, m, s, ms = times[-1]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def render_user_source_video(
    source_video: tuple[str, bytes],
    narration_audio: tuple[str, bytes],
    subtitles_srt: tuple[str, bytes],
    output_path: str | Path,
    platform: str = "youtube",
) -> Path:
    """Use only the exact uploaded video; loop visuals if needed and replace source audio."""
    import imageio_ffmpeg

    video_name, video_data = source_video
    audio_name, audio_data = narration_audio
    srt_name, srt_data = subtitles_srt
    video_suffix = Path(video_name).suffix.lower()
    audio_suffix = Path(audio_name).suffix.lower()
    if video_suffix not in ALLOWED_VIDEO_SUFFIXES or not video_data:
        raise SourceVideoRenderError("MP4/MOV/M4V/WEBM မူရင်း Video ဖိုင် လိုအပ်ပါတယ်။")
    if len(video_data) > MAX_SOURCE_VIDEO_BYTES:
        raise SourceVideoRenderError("Telegram မှ လက်ခံနိုင်သော Video အရွယ်အစား ၂၀ MB အောက် ဖြစ်ရပါမယ်။")
    if audio_suffix not in ALLOWED_AUDIO_SUFFIXES or not audio_data or len(audio_data) > MAX_NARRATION_BYTES:
        raise SourceVideoRenderError("Narration MP3/M4A/WAV/OGG ဖိုင် မမှန်ပါ သို့မဟုတ် ၄၅ MB ကျော်နေပါတယ်။")
    if Path(srt_name).suffix.lower() != ".srt" or not srt_data or len(srt_data) > MAX_SRT_BYTES:
        raise SourceVideoRenderError("UTF-8 SRT ဖိုင် ၁ MB အောက် လိုအပ်ပါတယ်။")
    try:
        srt_text = srt_data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceVideoRenderError("SRT သည် UTF-8 မြန်မာစာ ဖြစ်ရပါမယ်။") from exc
    if "-->" not in srt_text:
        raise SourceVideoRenderError("SRT timestamp မတွေ့ပါ။")
    duration = _srt_duration(srt_text)
    if not 1 <= duration <= 3600:
        raise SourceVideoRenderError("Narration/SRT ကြာချိန်သည် ၁ စက္ကန့်မှ ၆၀ မိနစ်အတွင်း ဖြစ်ရပါမယ်။")
    if platform not in PLATFORM_DIMENSIONS:
        raise SourceVideoRenderError("Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမယ်။")
    width, height = PLATFORM_DIMENSIONS[platform]

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix="nexora_user_source_") as temp:
        work = Path(temp)
        video_path = work / ("source" + video_suffix)
        audio_path = work / ("narration" + audio_suffix)
        srt_path = work / "captions.srt"
        video_path.write_bytes(video_data)
        audio_path.write_bytes(audio_data)
        srt_path.write_bytes(srt_data)
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1", "-i", str(video_path),
            "-i", str(audio_path), "-i", str(srt_path),
            "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0",
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,format=yuv420p",
            "-r", "25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
            "-c:a", "aac", "-b:a", "128k", "-c:s", "mov_text",
            "-metadata:s:s:0", "language=bur", "-t", f"{duration:.3f}",
            "-shortest", "-movflags", "+faststart", str(target),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
        except subprocess.TimeoutExpired as exc:
            raise SourceVideoRenderError("MP4 ထုတ်လုပ်ချိန် ၁၅ မိနစ်ကျော်သွားပါတယ်။") from exc
        if result.returncode or not target.exists() or not target.stat().st_size:
            raise SourceVideoRenderError("မူရင်း Video မှ MP4 မထုတ်နိုင်ပါ။ Video codec/ဖိုင်ကို ပြန်စစ်ပါ။")
    return target
