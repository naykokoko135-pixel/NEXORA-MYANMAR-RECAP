"""Render creator-owned or explicitly licensed source video with Burmese narration and SRT."""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path


class SourceVideoRenderError(ValueError):
    """Raised when an uploaded source video cannot be safely rendered."""


MAX_SOURCE_VIDEO_BYTES = 19 * 1024 * 1024
MAX_SOURCE_VIDEO_CLIPS = 30
MAX_SOURCE_VIDEO_TOTAL_BYTES = 180 * 1024 * 1024
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
    require_source_coverage: bool = True,
    expected_duration_seconds: float | None = None,
    effect_preset: str = "cinematic",
    audio_preset: str = "voice",
    motion_preset: str = "none",
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

    from video_effects import build_effect_filter

    try:
        video_filter = build_effect_filter(effect_preset, width, height)
    except ValueError as exc:
        raise SourceVideoRenderError(str(exc)) from exc

    from motion_presets import build_motion_filter
    try:
        motion_filter = build_motion_filter(motion_preset, width, height)
    except ValueError as exc:
        raise SourceVideoRenderError(str(exc)) from exc
    if motion_filter:
        video_filter = video_filter + "," + motion_filter

    from audio_mastering import build_audio_filter

    try:
        audio_filter = build_audio_filter(audio_preset)
    except ValueError as exc:
        raise SourceVideoRenderError(str(exc)) from exc

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
        # Use only genuine source-video frames; never loop or freeze a short clip to fill narration.
        probe = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(render_video_path)],
            capture_output=True, text=True, timeout=30, check=False,
        )
        probe_text = probe.stderr or probe.stdout
        match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", probe_text)
        if "Video:" not in probe_text or not match:
            raise SourceVideoRenderError("မူရင်းဖိုင်သည် ဖတ်ရှုနိုင်သော Video Footage မဟုတ်ပါ။ Still Image ကို MP4 အဖြစ် မပြောင်းပါ။")
        source_duration = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
        required_end = float(source_start_seconds) + float(expected_duration_seconds or duration)
        if source_start_seconds < 0 or source_duration + 0.5 < required_end:
            raise SourceVideoRenderError("မူရင်း Video သည် Narration/SRT အတွက် လုံလောက်သော ကြာချိန်မရှိပါ။ Footage ကို loop မလုပ်ဘဲ MP4 ထုတ်မှု ရပ်ထားပါတယ်။ ပိုရှည်သော Video လိုအပ်ပါတယ်။")
        video_input = ["-ss", f"{source_start_seconds:.3f}", "-i", str(render_video_path)] if source_start_seconds else ["-i", str(render_video_path)]
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            *video_input,
            "-i", str(audio_path), "-i", str(srt_path),
            "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0",
            "-vf",
            video_filter,
            "-r", "25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
            "-af", audio_filter,
            "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text",
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


def concatenate_source_video_clips(
    clips: list[tuple[str, bytes | str | Path]],
    output_path: str | Path,
    transition: str = "fade",
) -> Path:
    """Normalize and join real-video clips with a selectable transition."""
    import imageio_ffmpeg

    if not clips or len(clips) > MAX_SOURCE_VIDEO_CLIPS:
        raise SourceVideoRenderError(f"Video Clip ၁ ခုမှ {MAX_SOURCE_VIDEO_CLIPS} ခုအထိ လိုအပ်ပါတယ်။")
    total_bytes = 0
    for index, (_, payload) in enumerate(clips, 1):
        if isinstance(payload, (str, Path)):
            clip_path = Path(payload)
            if not clip_path.is_file():
                raise SourceVideoRenderError(f"Clip {index} ဖိုင် မတွေ့ပါ။")
            total_bytes += clip_path.stat().st_size
        else:
            total_bytes += len(payload)
    if total_bytes > MAX_SOURCE_VIDEO_TOTAL_BYTES:
        raise SourceVideoRenderError("Video Clip စုစုပေါင်း ၁၈၀ MiB ကျော်နေပါတယ်။")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexora_clip_join_") as temp:
        work = Path(temp)
        normalized: list[Path] = []
        durations: list[float] = []
        for index, (filename, data) in enumerate(clips, 1):
            suffix = Path(filename).suffix.lower()
            if suffix not in ALLOWED_VIDEO_SUFFIXES:
                raise SourceVideoRenderError(f"Clip {index}: MP4/MOV/M4V/WEBM ဖိုင်အမျိုးအစား လိုအပ်ပါတယ်။")
            if isinstance(data, (str, Path)):
                raw = Path(data)
                if not raw.is_file() or raw.stat().st_size <= 0 or raw.stat().st_size > MAX_SOURCE_VIDEO_BYTES:
                    raise SourceVideoRenderError(f"Clip {index}: ဖိုင်မရှိပါ သို့မဟုတ် ၁၉ MiB ကျော်နေပါတယ်။")
            else:
                if not data or len(data) > MAX_SOURCE_VIDEO_BYTES:
                    raise SourceVideoRenderError(f"Clip {index}: MP4/MOV/M4V/WEBM ၁၉ MiB အောက် လိုအပ်ပါတယ်။")
                raw = work / f"input_{index}{suffix}"
                raw.write_bytes(data)
            cooked = work / f"clip_{index:02d}.mp4"
            probe = subprocess.run(
                [ffmpeg, "-hide_banner", "-i", str(raw)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            probe_text = probe.stderr or probe.stdout
            if "Video:" not in probe_text:
                raise SourceVideoRenderError(f"Clip {index} တွင် ဖတ်ရှုနိုင်သော Video မတွေ့ပါ။")
            duration_match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", probe_text)
            if not duration_match:
                raise SourceVideoRenderError(f"Clip {index} ကြာချိန်ကို မဖတ်နိုင်ပါ။")
            durations.append(int(duration_match.group(1))*3600 + int(duration_match.group(2))*60 + float(duration_match.group(3)))
            command = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(raw), "-map", "0:v:0", "-an",
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
                "-movflags", "+faststart", str(cooked),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
            if result.returncode or not cooked.is_file() or cooked.stat().st_size == 0:
                raise SourceVideoRenderError(f"Clip {index} ကို Video အဖြစ် ပြင်ဆင်မရပါ။")
            normalized.append(cooked)
        if len(normalized) == 1 or transition == "cut":
            concat_list = work / "concat.txt"
            concat_list.write_text("".join(f"file '{path.as_posix()}'\n" for path in normalized), encoding="utf-8")
            command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", "-movflags", "+faststart", str(target)]
        else:
            from video_transitions import build_transition_graph
            try:
                graph, output_label = build_transition_graph(durations, transition, 0.6)
            except ValueError as exc:
                raise SourceVideoRenderError(str(exc)) from exc
            command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
            for path in normalized: command.extend(["-i", str(path)])
            command.extend(["-filter_complex", graph, "-map", output_label, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)])
        result = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
        if result.returncode or not target.is_file() or target.stat().st_size == 0:
            raise SourceVideoRenderError("Video Clip များကို ပေါင်းစပ်၍ MP4 မထုတ်နိုင်ပါ။")
    return target
