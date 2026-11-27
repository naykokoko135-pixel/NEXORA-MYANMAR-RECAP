"""Quality checks for scripts, narration audio, subtitles and the rendered video. Every check reports concrete issues."""
import json
import re
import subprocess
from pathlib import Path

from .base import config, subs

_MY = re.compile(r"[\u1000-\u109F\uAA60-\uAA7F]")


def check_script(sections, platform) -> dict:
    issues, warn = [], []
    items = [it for s in sections for it in s.get("items", [])]
    if len(items) < 8:
        issues.append(f"only {len(items)} sentences (need at least 8)")
    empty = [i for i, it in enumerate(items) if not str(it.get("my", "")).strip()]
    if empty:
        issues.append(f"{len(empty)} sentence(s) have no Burmese text")
    my_chars = sum(len(it.get("my", "")) for it in items)
    burmese = sum(len(_MY.findall(it.get("my", ""))) for it in items)
    if my_chars and burmese / my_chars < 0.3:
        issues.append(f"only {burmese / my_chars:.0%} of the narration is Burmese script")
    no_en = sum(1 for it in items if not str(it.get("en", "")).strip())
    if no_en:
        warn.append(f"{no_en} sentence(s) have no English subtitle text")
    long_en = sum(1 for it in items if len(it.get("en", "")) > 120)
    if long_en:
        warn.append(f"{long_en} English subtitle line(s) exceed 120 characters")
    dup = len(items) - len({it.get("my", "") for it in items})
    if dup > max(2, len(items) // 20):
        issues.append(f"{dup} duplicated sentences")
    return {"ok": not issues, "issues": issues, "warnings": warn, "sentences": len(items), "burmese_chars": burmese}


def _run(cmd, timeout=900):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def check_audio(path, platform, duration) -> dict:
    issues, warn = [], []
    P = config.PLATFORMS[platform]
    p = Path(path)
    if not p.exists() or p.stat().st_size < 5000:
        return {"ok": False, "issues": ["narration file missing or empty"], "warnings": []}
    if not (P["min"] * 60 <= duration <= P["max"] * 60):
        issues.append(f"duration {duration / 60:.1f} min is outside {platform}'s {P['min']}-{P['max']} min range")
    r = _run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "volumedetect,silencedetect=n=-45dB:d=8", "-vn", "-f", "null", "-"])
    m = re.search(r"max_volume: (-?[\d.]+) dB", r.stderr)
    if m and float(m.group(1)) >= -0.1:
        warn.append("audio peaks at 0 dB (possible clipping)")
    if m and float(m.group(1)) < -35:
        issues.append(f"audio is extremely quiet (peak {m.group(1)} dB)")
    sil = r.stderr.count("silence_start")
    if sil > 3:
        issues.append(f"{sil} silent gaps longer than 8 seconds")
    return {"ok": not issues, "issues": issues, "warnings": warn, "duration_min": round(duration / 60, 2)}


def check_subtitles(paths: dict, audio_duration: float) -> dict:
    issues, info = [], {}
    for lang, p in paths.items():
        try:
            v = subs.validate_srt(p)
        except Exception as e:
            issues.append(f"{lang}: unreadable SRT ({e})")
            continue
        info[lang] = {"cues": v["cues"], "ok": v["ok"]}
        issues += [f"{lang}: {x}" for x in v["issues"][:5]]
        if v["cues"] == 0:
            issues.append(f"{lang}: no cues")
            continue
        data = Path(p).read_text("utf-8")
        ends = re.findall(r"--> (\d+:\d\d:\d\d,\d{3})", data)
        last = subs._sec(ends[-1]) if ends else 0
        if last > audio_duration + 1.0:
            issues.append(f"{lang}: subtitles run {last - audio_duration:.1f}s past the audio")
        if last < audio_duration * 0.9:
            issues.append(f"{lang}: subtitles cover only {last / audio_duration:.0%} of the audio")
    return {"ok": not issues, "issues": issues, "files": info}


def probe(path) -> dict:
    r = _run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], 60)
    return json.loads(r.stdout or "{}")


def check_video(path, platform, width, height, expect_duration=None) -> dict:
    """Resolution-aware version of qc.check_mp4 (H.264 + audio, duration, A/V sync, decodability)."""
    p = Path(path)
    P = config.PLATFORMS[platform]
    issues = []
    if not p.exists() or p.stat().st_size < 10000:
        return {"ok": False, "issues": ["MP4 missing or empty"]}
    info = probe(p)
    v = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), None)
    a = next((s for s in info.get("streams", []) if s["codec_type"] == "audio"), None)
    if not v or v["codec_name"] != "h264":
        issues.append("video stream is not H.264")
    if not a or a["codec_name"] != "aac":
        issues.append("audio stream is not AAC")
    dur = float(info["format"]["duration"])
    if not (P["min"] * 60 <= dur <= P["max"] * 60):
        issues.append(f"duration {dur / 60:.2f} min is outside {platform}'s {P['min']}-{P['max']} min range")
    if expect_duration and abs(dur - expect_duration) > 3:
        issues.append(f"video length {dur:.1f}s differs from narration {expect_duration:.1f}s")
    if v and (v["width"], v["height"]) != (width, height):
        issues.append(f"resolution {v['width']}x{v['height']} != expected {width}x{height}")
    if v and a:
        dv, da = float(v.get("duration", dur)), float(a.get("duration", dur))
        if abs(dv - da) > 0.5:
            issues.append(f"A/V length mismatch {abs(dv - da):.2f}s")
    full = dur <= 600
    cmd = ["ffmpeg", "-v", "error", "-xerror", "-i", str(p), "-f", "null", "-"] if full else ["ffmpeg", "-v", "error", "-sseof", "-20", "-i", str(p), "-f", "null", "-"]
    t = _run(cmd, 1800)
    if t.returncode != 0 or t.stderr.strip():
        issues.append(("decode error: " if full else "decode error near end: ") + t.stderr[:160])
    s = _run(["ffmpeg", "-i", str(p), "-af", "silencedetect=n=-45dB:d=8", "-vn", "-f", "null", "-"], 1800)
    if s.stderr.count("silence_start") > 3:
        issues.append(f"{s.stderr.count('silence_start')} long silences in the final audio")
    return {"ok": not issues, "issues": issues, "duration_min": round(dur / 60, 2), "size_mb": round(p.stat().st_size / 1e6, 2),
            "width": v["width"] if v else None, "height": v["height"] if v else None, "codec": v["codec_name"] if v else None,
            "fully_decoded": full, "bitrate_kbps": int(int(info["format"].get("bit_rate", 0)) / 1000)}
