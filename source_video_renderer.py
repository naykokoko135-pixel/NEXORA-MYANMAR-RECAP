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
    source_video: tuple[str, bytes] | str | Path,
    narration_audio: tuple[str, bytes],
    subtitles_srt: tuple[str, bytes],
    output_path: str | Path,
    platform: str = "youtube",
    source_start_seconds: float = 0.0,
    require_source_coverage: bool = False,
    expected_duration_seconds: float | None = None,
) -> Path:
    """Use only the exact uploaded video; loop visuals if needed and replace source audio."""
    import imageio_ffmpeg

    if isinstance(source_video, (str, Path)):
        video_path = Path(source_video)
        video_name = video_path.name
        if not video_path.is_file() or video_path.stat().st_size <= 0:
            raise SourceVideoRenderError("Server တွင် မူရင်း Video ဖိုင် မတွေ့ပါ။ /licensedownload ကို ပြန်လုပ်ပါ။")
        video_data = None
    else:
        video_name, video_data = source_video
        video_path = None
    audio_name, audio_data = narration_audio
    srt_name, srt_data = subtitles_srt
    video_suffix = Path(video_name).suffix.lower()
    audio_suffix = Path(audio_name).suffix.lower()
    if video_suffix not in ALLOWED_VIDEO_SUFFIXES or (video_path is None and not video_data):
        raise SourceVideoRenderError("MP4/MOV/M4V/WEBM မူရင်း Video ဖိုင် လိုအပ်ပါတယ်။")
    if video_path is None and len(video_data) > MAX_SOURCE_VIDEO_BYTES:
        raise SourceVideoRenderError("Telegram မှ တိုက်ရိုက်ပို့သော Video သည် ၂၀ MB အောက် ဖြစ်ရပါမယ်။ Commons မှ Server-side Download ကို /licensedownload သုံးပါ။")
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
    srt_duration = _srt_duration(srt_text)
    duration = float(expected_duration_seconds) if expected_duration_seconds is not None else srt_duration
    if not 1 <= duration <= 3600 or srt_duration > duration + 0.5:
        raise SourceVideoRenderError("Narration/SRT ကြာချိန်သည် သတ်မှတ်ထားသော အပိုင်းကြာချိန်နှင့် မကိုက်ညီပါ။")
    if platform not in PLATFORM_DIMENSIONS:
        raise SourceVideoRenderError("Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမယ်။")
    width, height = PLATFORM_DIMENSIONS[platform]

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix="nexora_user_source_") as temp:
        work = Path(temp)
        render_video_path = video_path if video_path is not None else work / ("source" + video_suffix)
        audio_path = work / ("narration" + audio_suffix)
        srt_path = work / "captions.srt"
        if video_path is None:
            render_video_path.write_bytes(video_data)
        audio_path.write_bytes(audio_data)
        srt_path.write_bytes(srt_data)
        if require_source_coverage:
            probe = subprocess.run(
                [ffmpeg, "-hide_banner", "-i", str(render_video_path)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            probe_text = probe.stderr or probe.stdout
            match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\\.\d+)?)", probe_text)
            if not match:
                raise SourceVideoRenderError("မူရင်း Video ကြာချိန်ကို အတည်မပြုနိုင်ပါ။")
            source_duration = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
            required_end = float(source_start_seconds) + float(expected_duration_seconds or duration)
            if source_start_seconds < 0 or source_duration + 0.5 < required_end:
                raise SourceVideoRenderError("မူရင်း Video သည် အပိုင်းသုံးပိုင်းလုံးအတွက် လုံလောက်သော ကြာချိန်မရှိပါ။ ထပ်ခါတလဲလဲ footage မသုံးဘဲ ရပ်ထားပါတယ်။")
            video_input = ["-ss", f"{source_start_seconds:.3f}", "-i", str(render_video_path)]
        else:
            video_input = ["-stream_loop", "-1", "-i", str(render_video_path)]
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            *video_input,
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
