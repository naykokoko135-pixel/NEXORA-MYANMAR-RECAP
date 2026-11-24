"""Validated playback-speed controls for the video-only source renderer."""
from __future__ import annotations


MIN_VIDEO_SPEED = 0.5
MAX_VIDEO_SPEED = 2.0


def normalize_video_speed(value: float | str) -> float:
    """Accept a playback multiplier between 0.5x slow motion and 2x speed."""
    raw = str(value).strip().lower().removesuffix("x")
    try:
        speed = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Video Speed သည် 0.5x မှ 2.0x အတွင်း ဖြစ်ရပါမယ်။") from exc
    if not MIN_VIDEO_SPEED <= speed <= MAX_VIDEO_SPEED:
        raise ValueError("Video Speed သည် 0.5x မှ 2.0x အတွင်း ဖြစ်ရပါမယ်။")
    return speed


def build_video_speed_filter(speed: float | str) -> str:
    """Return an FFmpeg setpts filter; narration/audio remains unchanged."""
    value = normalize_video_speed(speed)
    return "" if abs(value - 1.0) < 1e-9 else f"setpts=PTS/{value:.4f}"


def required_source_duration(output_duration: float, speed: float | str) -> float:
    """Raw footage seconds required to fill a narration timeline at this speed."""
    value = normalize_video_speed(speed)
    duration = float(output_duration)
    if duration <= 0:
        raise ValueError("Output duration must be positive.")
    return duration * value
