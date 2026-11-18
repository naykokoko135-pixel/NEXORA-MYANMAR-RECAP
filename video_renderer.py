"""Create a simple MP4 slideshow from creator-owned images and narration audio."""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

MAX_IMAGES = 12
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_AUDIO_SECONDS = 600
MAX_SUBTITLE_BYTES = 1024 * 1024
SUBTITLE_SUFFIXES = {".srt"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".ogg"}


class VideoRenderError(ValueError):
    """Raised when inputs cannot be rendered safely."""


def _duration_seconds(ffmpeg: str, audio_path: Path) -> float:
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(audio_path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    details = probe.stderr or probe.stdout
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", details)
    if not match:
        raise VideoRenderError("အသံဖိုင်ကြာချိန်ကို မဖတ်နိုင်ပါ။ MP3/M4A/WAV/OGG ဖိုင်သုံးပါ။")
    hours, minutes, seconds = match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if duration <= 0 or duration > MAX_AUDIO_SECONDS:
        raise VideoRenderError("အသံဖိုင်သည် ၁၀ မိနစ်ထက် မကျော်ရပါ။")
    return duration


def render_slideshow(
    images: list[tuple[str, bytes]],
    audio: tuple[str, bytes] | list[tuple[str, bytes]],
    output_path: str | Path,
    platform: str = "youtube",
) -> Path:
    """Render up to 12 still images and narration into a platform-sized MP4."""
    dimensions = {"youtube": (1280, 720), "facebook": (864, 1080), "tiktok": (720, 1280)}
    if platform not in dimensions:
        raise VideoRenderError("Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမယ်။")
    width, height = dimensions[platform]
    if subtitle is not None:
        subtitle_name, subtitle_data = subtitle
        if Path(subtitle_name).suffix.lower() not in SUBTITLE_SUFFIXES or not subtitle_data or len(subtitle_data) > MAX_SUBTITLE_BYTES:
            raise VideoRenderError("စာတန်းဖိုင်သည် SRT ဖြစ်ပြီး ၁ MB အောက် ဖြစ်ရပါမယ်။")
        try:
            subtitle_text = subtitle_data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise VideoRenderError("SRT ဖိုင်သည် UTF-8 မြန်မာစာဖြစ်ရပါမယ်။") from exc
        if "-->" not in subtitle_text:
            raise VideoRenderError("SRT timestamp ပုံစံ မမှန်ပါ။")
    if not 1 <= len(images) <= MAX_IMAGES:
        raise VideoRenderError(f"ပုံ {1} မှ {MAX_IMAGES} ပုံအထိ ထည့်နိုင်ပါတယ်။")
    audio_tracks = [audio] if isinstance(audio, tuple) else list(audio)
    if not audio_tracks or len(audio_tracks) > 12:
        raise VideoRenderError("အသံ Track ၁ မှ ၁၂ ခုအထိ ထည့်နိုင်ပါတယ်။")
    total_audio_bytes = 0
    for audio_name, audio_data in audio_tracks:
        if Path(audio_name).suffix.lower() not in AUDIO_SUFFIXES:
            raise VideoRenderError("အသံဖိုင်အမျိုးအစား မမှန်ပါ။ MP3/M4A/WAV/OGG သုံးပါ။")
        if not audio_data:
            raise VideoRenderError("အသံဖိုင် ဗလာဖြစ်နေပါတယ်။")
        total_audio_bytes += len(audio_data)
    if total_audio_bytes > MAX_AUDIO_BYTES:
        raise VideoRenderError("အသံဖိုင်အားလုံးပေါင်း ၂၀ MB အောက် ဖြစ်ရပါမယ်။")

    for name, data in images:
        if Path(name).suffix.lower() not in IMAGE_SUFFIXES:
            raise VideoRenderError("ပုံဖိုင်သည် JPG/PNG/WEBP ဖြစ်ရပါမယ်။")
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise VideoRenderError("ပုံတစ်ပုံသည် ၈ MB အောက် ဖြစ်ရပါမယ်။")

    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise VideoRenderError("Video renderer ကို မတင်ဆင်ရသေးပါ။") from exc

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexora_render_") as temp:
        work = Path(temp)
        audio_paths = []
        duration = 0.0
        for index, (audio_name, audio_data) in enumerate(audio_tracks):
            audio_path = work / (f"voice_{index:02d}" + Path(audio_name).suffix.lower())
            audio_path.write_bytes(audio_data)
            duration += _duration_seconds(ffmpeg, audio_path)
            audio_paths.append(audio_path)
        if duration > MAX_AUDIO_SECONDS:
            raise VideoRenderError("အသံ Track အားလုံးပေါင်း ၁၀ မိနစ်ထက် မကျော်ရပါ။")

        subtitle_path = None
        if subtitle is not None:
            subtitle_path = work / "captions.srt"
            subtitle_path.write_bytes(subtitle[1])

        lines = []
        segment = duration / len(images)
        for index, (name, data) in enumerate(images):
            image_path = work / f"image_{index:02d}{Path(name).suffix.lower()}"
            image_path.write_bytes(data)
            safe_path = str(image_path).replace("'", "'\\''")
            lines.append(f"file '{safe_path}'")
            lines.append(f"duration {segment:.4f}")
        last_path = str(work / f"image_{len(images)-1:02d}{Path(images[-1][0]).suffix.lower()}").replace("'", "'\\''")
        lines.append(f"file '{last_path}'")
        concat_path = work / "slides.txt"
        concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
            *[arg for audio_path in audio_paths for arg in ("-i", str(audio_path))],
            *(["-i", str(subtitle_path)] if subtitle_path else []),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p",
            "-r", "25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            *(
                ["-filter_complex",
                 "".join(
                     f"[{i + 1}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}];"
                     for i in range(len(audio_paths))
                 ) +
                 "".join(f"[a{i}]" for i in range(len(audio_paths))) +
                 f"concat=n={len(audio_paths)}:v=0:a=1[aout]",
                 "-map", "0:v", "-map", "[aout]"]
                if len(audio_paths) > 1 else ["-map", "0:v", "-map", "1:a"]
            ),
            *(["-map", f"{len(audio_paths) + 1}:s:0", "-c:s", "mov_text", "-metadata:s:s:0", "language=bur"] if subtitle_path else []),
            "-c:a", "aac", "-b:a", "128k", "-shortest", "-t", f"{duration:.3f}",
            "-movflags", "+faststart", str(target),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
        except subprocess.TimeoutExpired as exc:
            raise VideoRenderError("Video ထုတ်လုပ်ချိန် ၅ မိနစ်ကျော်သွားပါတယ်။ ပိုတိုတဲ့ အသံဖိုင်သုံးပါ။") from exc
        if result.returncode != 0 or not target.exists() or target.stat().st_size == 0:
            raise VideoRenderError("MP4 ထုတ်လုပ်မှု မအောင်မြင်ပါ။ ပုံနဲ့အသံဖိုင်ကို ပြန်စစ်ပါ။")
    return target
