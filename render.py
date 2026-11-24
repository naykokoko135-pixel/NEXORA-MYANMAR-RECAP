"""ffmpeg renderer. Visuals are 100% self-generated (animated gradients + text + progress bar): no third-party footage."""
import colorsys
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config

FONT = next((p for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                         "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"] if Path(p).exists()), "")


def _hex(h, s=0.55, v=0.35):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return f"0x{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _esc(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019").replace("%", "\\%")


def make_scenes(timeline, max_len=20.0):
    """Group sentences into scenes <= max_len seconds, never crossing a section boundary."""
    scenes, cur = [], None
    for e in timeline:
        if cur and e["sec"] == cur["sec"] and e["end"] - cur["start"] <= max_len:
            cur["end"] = e["end"] + 0.2
        else:
            if cur:
                scenes.append(cur)
            cur = dict(sec=e["sec"], start=e["start"], end=e["end"] + 0.2)
    if cur:
        scenes.append(cur)
    for i in range(len(scenes) - 1):  # make scenes contiguous so A/V stays in sync
        scenes[i]["end"] = scenes[i + 1]["start"]
    return scenes


def _clip(args):
    i, sc, total, title, sec_title, W, H, wd, fps = args
    d = max(sc["end"] - sc["start"], 0.5)
    h = (sc["sec"] * 0.137 + 0.55) % 1.0
    out = Path(wd) / f"c{i:05d}.mp4"
    base = f"gradients=s={W}x{H}:r={fps}:c0={_hex(h)}:c1={_hex(h + 0.12, 0.6, 0.2)}:d={d:.3f}:speed=0.015"
    vf = []
    if FONT:
        fs = int(H * (0.045 if W > H else 0.035))
        vf += [f"drawtext=fontfile={FONT}:text='{_esc(title)}':fontsize={fs}:fontcolor=white@0.9:x=w*0.05:y=h*0.06",
               f"drawtext=fontfile={FONT}:text='{_esc(sec_title)}':fontsize={int(fs * 0.6)}:fontcolor=white@0.6:x=w*0.05:y=h*0.06+{int(fs * 1.5)}",
               f"drawtext=fontfile={FONT}:text='{_esc(config.CHANNEL_NAME)}':fontsize={int(fs * 0.55)}:fontcolor=white@0.45:x=w-tw-w*0.04:y=h*0.05"]
    prog_x = sc["start"] / total
    prog_w = (sc["end"] - sc["start"]) / total
    vf.append(f"drawbox=x=0:y=ih-8:w=iw:h=8:color=white@0.15:t=fill")
    vf.append(f"drawbox=x=0:y=ih-8:w=iw*({prog_x:.5f}+{prog_w:.5f}*t/{d:.3f}):h=8:color=white@0.85:t=fill")
    vf.append(f"fade=t=in:d=0.4,fade=t=out:st={max(d - 0.4, 0):.3f}:d=0.4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", base, "-vf", ",".join(vf), "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:  # drawbox 't' var unsupported on old builds -> simple fallback
        vf2 = [x for x in vf if "drawbox" not in x or "*t/" not in x]
        cmd[cmd.index("-vf") + 1] = ",".join(vf2)
        subprocess.run(cmd, check=True)
    return out


def ensure_bgm(path):
    if Path(path).exists():
        return path
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=110:r=44100", "-f", "lavfi", "-i", "sine=f=165:r=44100",
                    "-f", "lavfi", "-i", "sine=f=220:r=44100", "-filter_complex",
                    "[0][1][2]amix=inputs=3,volume=0.6,tremolo=f=0.15:d=0.5,lowpass=f=600", "-t", "60", str(path)], check=True)
    return path


def render(timeline, audio, srt, platform, title, wd, out_mp4, log=print, bgm=True):
    P = config.PLATFORMS[platform]
    W, H, fps = P["w"], P["h"], 24
    wd = Path(wd)
    wd.mkdir(parents=True, exist_ok=True)
    scenes = make_scenes(timeline)
    total = scenes[-1]["end"]
    sec_titles = {}
    log(f"[render] {len(scenes)} scenes, {total / 60:.1f} min, {W}x{H}")
    jobs = [(i, s, total, title, f"Part {s['sec'] + 1}", W, H, wd, fps) for i, s in enumerate(scenes)]
    with ThreadPoolExecutor(max_workers=max(1, (__import__("os").cpu_count() or 2))) as ex:
        clips = list(ex.map(_clip, jobs))
    lst = wd / "clips.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    raw = wd / "video_raw.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(raw)], check=True)
    for c in clips:
        c.unlink(missing_ok=True)
    fs = 20 if W > H else 14
    style = f"FontName=DejaVu Sans,FontSize={fs},Bold=1,Outline=2,Shadow=1,MarginV={int(H * 0.08)},Alignment=2"
    sub = f"subtitles={Path(srt).name}:force_style='{style}'"
    inputs = ["-i", str(raw), "-i", str(audio)]
    if bgm:
        b = ensure_bgm(wd / "bgm.mp3")
        inputs += ["-stream_loop", "-1", "-i", str(b)]
        fc = (f"[0:v]{sub}[v];[2:a]volume=0.5[bg];[1:a]asplit[vo][sc];"
              "[bg][sc]sidechaincompress=threshold=0.04:ratio=10:attack=20:release=400[duck];"
              "[vo][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    else:
        fc = f"[0:v]{sub}[v];[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", "-r", str(fps),
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", "-movflags", "+faststart", str(out_mp4)]
    r = subprocess.run(cmd, cwd=str(Path(srt).parent), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg final render failed: " + r.stderr[-800:])
    raw.unlink(missing_ok=True)
    return out_mp4
