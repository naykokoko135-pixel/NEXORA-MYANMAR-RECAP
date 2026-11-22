"""Automatic long-form render from an exact-match, reusable Wikimedia Commons source.

Only Commons media already filtered by the title matcher and reusable-license
allowlist is downloaded. The complete source must cover the full 46–60 minute
narration; short clips are rejected by the existing source-coverage renderer.
"""
from __future__ import annotations

from pathlib import Path
import secrets

from licensed_video_pipeline import download_licensed_source
from recap_partitioner import render_three_part_longform


def render_licensed_longform_parts(
    source: dict,
    narration_audio: tuple[str, bytes],
    subtitles_srt: tuple[str, bytes],
    output_dir: str | Path,
    platform: str,
) -> list[Path]:
    """Download one reusable Commons source, render three parts, then delete source."""
    if platform not in {"youtube", "facebook"}:
        raise ValueError("Automatic three-part long-form rendering supports YouTube/Facebook only.")
    if not isinstance(source, dict) or not source.get("source_page"):
        raise ValueError("A Commons source page and license record are required.")
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".webm" if str(source.get("mime", "")).lower() == "video/webm" else ".mp4"
    source_path = target_dir / (".nexora_source_" + secrets.token_hex(8) + suffix)
    try:
        download_licensed_source(source, source_path)
        return render_three_part_longform(
            source_path, narration_audio, subtitles_srt, target_dir / ("parts_" + secrets.token_hex(6)), platform
        )
    finally:
        source_path.unlink(missing_ok=True)
