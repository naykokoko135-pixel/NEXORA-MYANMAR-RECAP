"""Split long-form narration/SRT at cue boundaries into three real, non-overlapping parts."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


class RecapPartitionError(ValueError):
    """Raised when a long-form recap cannot be divided into three valid parts."""


_TIME = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})$")


def _seconds(value: str) -> float:
    match = _TIME.match(value.strip())
    if not match:
        raise RecapPartitionError("SRT timestamp ပုံစံ မမှန်ပါ။")
    hours, minutes, seconds, millis = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def _stamp(value: float) -> str:
    total_ms = max(0, round(value * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def plan_three_part_srt(srt_text: str) -> list[dict]:
    """Return three cue-aligned, timestamp-reset SRT parts, each 15–20 minutes."""
    blocks = re.split(r"\r?\n\s*\r?\n", str(srt_text).strip())
    cues = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        match = re.match(
            r"^\s*(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
            lines[1],
        )
        if not match:
            continue
        start, end = _seconds(match.group(1)), _seconds(match.group(2))
        if end <= start:
            raise RecapPartitionError("SRT cue အချိန်အစ/အဆုံး မမှန်ပါ။")
        cues.append((start, end, lines[2:]))
    if not cues:
        raise RecapPartitionError("SRT cue မတွေ့ပါ။")
    cues.sort(key=lambda cue: cue[0])
    duration = max(cue[1] for cue in cues)
    if not 2760 <= duration <= 3600:
        raise RecapPartitionError("YouTube/Facebook အတွက် SRT ကြာချိန်သည် ၄၆–၆၀ မိနစ် ဖြစ်ရပါမယ်။")
    candidates = sorted({cue[0] for cue in cues if 900 <= cue[0] <= 2700})
    pairs = []
    for first in candidates:
        if not 900 <= first <= 1200:
            continue
        for second in candidates:
            if second <= first:
                continue
            if 900 <= second - first <= 1200 and 900 <= duration - second <= 1200:
                pairs.append((abs(first - duration / 3) + abs(second - 2 * duration / 3), first, second))
    if not pairs:
        raise RecapPartitionError("SRT cue များကို မဖြတ်တောက်ဘဲ ၁၅–၂၀ မိနစ်စီ သုံးပိုင်းခွဲမရပါ။")
    _, first_cut, second_cut = min(pairs)
    bounds = [0.0, first_cut, second_cut, duration]
    result = []
    for index in range(3):
        start, end = bounds[index], bounds[index + 1]
        part_cues = [
            (cue_start - start, min(cue_end, end) - start, text_lines)
            for cue_start, cue_end, text_lines in cues
            if start <= cue_start < end
        ]
        if not part_cues:
            raise RecapPartitionError(f"Part {index + 1} တွင် subtitle မရှိပါ။")
        output = []
        for number, (cue_start, cue_end, text_lines) in enumerate(part_cues, 1):
            output.extend([
                str(number),
                f"{_stamp(cue_start)} --> {_stamp(cue_end)}",
                *text_lines,
                "",
            ])
        result.append({
            "part": index + 1,
            "start_seconds": start,
            "duration_seconds": end - start,
            "srt_text": "\n".join(output).strip() + "\n",
        })
    if any(not 900 <= part["duration_seconds"] <= 1200 for part in result):
        raise RecapPartitionError("သုံးပိုင်းလုံး ၁၅–၂၀ မိနစ်စီ မပြည့်မီပါ။")
    return result


def split_audio_for_parts(
    audio: tuple[str, bytes],
    parts: list[dict],
    output_dir: str | Path,
) -> list[dict]:
    """Use FFmpeg to cut exact narration intervals; never duplicate the full track."""
    import imageio_ffmpeg

    filename, audio_bytes = audio
    if not audio_bytes:
        raise RecapPartitionError("Narration audio ဗလာဖြစ်နေပါတယ်။")
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / ("full_narration" + (Path(filename).suffix.lower() or ".mp3"))
    source.write_bytes(audio_bytes)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    completed = []
    try:
        for part in parts:
            target = folder / f"part_{part['part']}_narration.mp3"
            command = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(source), "-ss", f"{part['start_seconds']:.3f}",
                "-t", f"{part['duration_seconds']:.3f}", "-vn",
                "-c:a", "libmp3lame", "-q:a", "2", str(target),
            ]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
            except subprocess.TimeoutExpired as exc:
                raise RecapPartitionError("Narration ကို အပိုင်းခွဲရန် အချိန်ကျော်သွားပါတယ်။") from exc
            if result.returncode or not target.is_file() or target.stat().st_size == 0:
                raise RecapPartitionError(f"Part {part['part']} Narration ကို ခွဲမရပါ။")
            completed.append({
                **part,
                "audio": (target.name, target.read_bytes()),
                "subtitle": (f"part_{part['part']}_subtitles.srt", part["srt_text"].encode("utf-8-sig")),
            })
        return completed
    except Exception:
        for item in completed:
            (folder / item["audio"][0]).unlink(missing_ok=True)
        raise
    finally:
        source.unlink(missing_ok=True)



def render_three_part_longform(
    source_video: tuple[str, bytes] | str | Path,
    narration_audio: tuple[str, bytes],
    subtitles_srt: tuple[str, bytes],
    output_dir: str | Path,
    platform: str,
    effect_preset: str = "cinematic",
    audio_preset: str = "voice",
    motion_preset: str = "none",
) -> list[Path]:
    """Render three sequential source ranges with distinct audio/SRT files."""
    import tempfile
    from source_video_renderer import render_user_source_video

    if platform not in {"youtube", "facebook"}:
        raise RecapPartitionError("သုံးပိုင်း Render ကို YouTube/Facebook အတွက်သာ အသုံးပြုနိုင်ပါတယ်။")
    try:
        srt_text = subtitles_srt[1].decode("utf-8-sig")
    except (AttributeError, UnicodeDecodeError) as exc:
        raise RecapPartitionError("UTF-8 SRT ဖိုင် လိုအပ်ပါတယ်။") from exc
    parts = plan_three_part_srt(srt_text)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="nexora_recap_parts_") as temp:
        split_parts = split_audio_for_parts(narration_audio, parts, temp)
        try:
            for part in split_parts:
                output = target_dir / f"nexora_recap_part_{part['part']}.mp4"
                render_user_source_video(
                    source_video,
                    part["audio"],
                    part["subtitle"],
                    output,
                    platform,
                    source_start_seconds=part["start_seconds"],
                    require_source_coverage=True,
                    expected_duration_seconds=part["duration_seconds"],
                    effect_preset=effect_preset,
                    audio_preset=audio_preset,
                    motion_preset=motion_preset,
                )
                outputs.append(output)
        except Exception:
            for output in outputs:
                output.unlink(missing_ok=True)
            raise
    return outputs
