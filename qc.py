import json
import subprocess
from pathlib import Path

from . import config


def _probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)],
                       capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def check_mp4(path, platform):
    p = Path(path)
    P = config.PLATFORMS[platform]
    issues = []
    if not p.exists() or p.stat().st_size < 10000:
        return dict(ok=False, issues=["MP4 မရှိပါ"])
    info = _probe(p)
    v = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), None)
    a = next((s for s in info.get("streams", []) if s["codec_type"] == "audio"), None)
    if not v or v["codec_name"] != "h264":
        issues.append("video is not H.264")
    if not a:
        issues.append("no audio stream")
    dur = float(info["format"]["duration"])
    if not (P["min"] * 60 <= dur <= P["max"] * 60):
        issues.append(f"duration {dur / 60:.1f} min outside {P['min']}-{P['max']}")
    if v and (v["width"], v["height"]) != (P["w"], P["h"]):
        issues.append(f"resolution {v['width']}x{v['height']} wrong")
    if v and a:
        dv, da = float(v.get("duration", dur)), float(a.get("duration", dur))
        if abs(dv - da) > 0.5:
            issues.append(f"A/V drift {abs(dv - da):.2f}s")
    t = subprocess.run(["ffmpeg", "-v", "error", "-sseof", "-15", "-i", str(p), "-f", "null", "-"], capture_output=True, text=True)
    if t.returncode != 0 or t.stderr.strip():
        issues.append("decode error near end: " + t.stderr[:120])
    s = subprocess.run(["ffmpeg", "-i", str(p), "-af", "silencedetect=n=-45dB:d=6", "-vn", "-f", "null", "-"], capture_output=True, text=True)
    long_sil = s.stderr.count("silence_start")
    if long_sil > 3:
        issues.append(f"{long_sil} long silences")
    return dict(ok=not issues, issues=issues, duration_min=round(dur / 60, 2), size_mb=round(p.stat().st_size / 1e6, 1),
                bitrate_kbps=int(int(info["format"].get("bit_rate", 0)) / 1000))
