"""Studio video renderer: ffmpeg + libx264 (H.264) + AAC, any aspect ratio / resolution.

Visuals are (a) authorised still images (Commons/Openverse/user uploads) with a slow zoom and visible attribution when
required, or (b) self-generated animated graphics. Nothing is presented as footage from the movie.
"""
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import render as base


def ascii_safe(text: str, limit: int = 60) -> str:
    """drawtext uses DejaVu (no Burmese glyphs): keep Latin text only, single line, bounded length."""
    t = re.sub(r"[^\x20-\x7E -ɏ‐-―‘-”]", "", str(text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return (t[: limit - 1] + "…") if len(t) > limit else t


def _even(n) -> int:
    n = int(round(n))
    return n - n % 2


def _esc(t: str) -> str:
    return base._esc(ascii_safe(t, 200))


def default_run(cmd, cwd=None, line_cb=None):
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, err


def _clip(args):
    i, sc, total, title, sec_title, W, H, fps, wd, asset, channel, run, cancel = args
    cancel()
    d = max(sc["end"] - sc["start"], 0.5)
    out = Path(wd) / f"c{i:05d}.mp4"
    fs = max(18, int(min(W, H) * 0.06))
    max_title = 26 if H > W else 48
    vf = []
    if asset:
        bw, bh = _even(W * 1.5), _even(H * 1.5)
        frames = max(1, round(d * fps))
        src = ["-i", asset["path"]]
        vf.append(f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
                  f"zoompan=z='min(1.0+0.0006*on,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={fps}")
        vf.append(f"drawbox=x=0:y=0:w=iw:h=ih*0.2:color=black@0.5:t=fill")
    else:
        hue = (sc.get("section", 0) * 0.137 + 0.55) % 1.0
        src = ["-f", "lavfi", "-i", f"gradients=s={W}x{H}:r={fps}:c0={base._hex(hue)}:c1={base._hex(hue + 0.12, 0.6, 0.2)}:d={d:.3f}:speed=0.015"]
    if base.FONT:
        vf += [f"drawtext=fontfile={base.FONT}:text='{_esc(ascii_safe(title, max_title))}':fontsize={fs}:fontcolor=white@0.92:x=w*0.05:y=h*0.05",
               f"drawtext=fontfile={base.FONT}:text='{_esc(sec_title)}':fontsize={int(fs * 0.6)}:fontcolor=white@0.7:x=w*0.05:y=h*0.05+{int(fs * 1.45)}",
               f"drawtext=fontfile={base.FONT}:text='{_esc(channel)}':fontsize={int(fs * 0.5)}:fontcolor=white@0.5:x=w-tw-w*0.04:y=h*0.95"]
        if asset and asset.get("attribution_required"):
            credit = ascii_safe(f"Image: {asset.get('title', '')} - {asset.get('attribution', '')} ({asset.get('license', '')})", 110)
            vf += [f"drawbox=x=0:y=ih*0.90:w=iw:h=ih*0.045:color=black@0.55:t=fill",
                   f"drawtext=fontfile={base.FONT}:text='{_esc(credit)}':fontsize={max(12, int(fs * 0.38))}:fontcolor=white@0.9:x=w*0.02:y=h*0.905"]
    done_w = (sc["start"] + (sc["end"] - sc["start"])) / max(total, 1)
    vf.append("drawbox=x=0:y=ih-8:w=iw:h=8:color=white@0.15:t=fill")
    vf.append(f"drawbox=x=0:y=ih-8:w=iw*{done_w:.5f}:h=8:color=white@0.85:t=fill")
    vf.append(f"fade=t=in:d=0.4,fade=t=out:st={max(d - 0.4, 0):.3f}:d=0.4")
    cmd = ["ffmpeg", "-y", "-v", "error", *src, "-t", f"{d:.3f}", "-vf", ",".join(vf), "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "26", "-pix_fmt", "yuv420p", "-an", str(out)]
    rc, err = run(cmd)
    if rc != 0:
        raise RuntimeError(f"scene {i} render failed: {err[-300:]}")
    return out


def render(scenes, audio, srt_en, out_mp4, *, title, channel, W, H, workdir, burn_subs=True, assets=None, fps=24, bgm=True, crf=24,
           progress=lambda f, s="": None, run=default_run, cancel=lambda: None, workers=2, log=print):
    """Render scenes + narration (+ burned English subtitles) to H.264/AAC MP4. Returns metadata dict."""
    wd = Path(workdir)
    wd.mkdir(parents=True, exist_ok=True)
    assets = assets or {}
    total = scenes[-1]["end"]
    log(f"[render] {len(scenes)} scenes, {total / 60:.1f} min, {W}x{H}@{fps}, assets used: {sum(1 for s in scenes if s.get('asset_id') in assets)}")
    jobs = [(i, s, total, title, f"Part {s.get('section', 0) + 1}", W, H, fps, wd, assets.get(s.get("asset_id")), channel, run, cancel) for i, s in enumerate(scenes)]
    clips, t0 = [], time.time()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = [ex.submit(_clip, j) for j in jobs]
        for n, f in enumerate(futs, 1):
            clips.append(f.result())
            progress(0.6 * n / len(futs), f"scene {n}/{len(futs)}")
    cancel()
    lst = wd / "clips.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    raw = wd / "video_raw.mp4"
    rc, err = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(raw)])
    if rc != 0:
        raise RuntimeError("scene concat failed: " + err[-300:])
    for c in clips:
        c.unlink(missing_ok=True)
    chain = "null"
    if burn_subs and srt_en:
        fs = 20 if W > H else 14
        style = f"FontName=DejaVu Sans,FontSize={fs},Bold=1,Outline=2,Shadow=1,MarginV={int(H * 0.08)},MarginL=20,MarginR=20,Alignment=2"
        chain = f"subtitles={Path(srt_en).name}:force_style='{style}'"
    inputs = ["-i", str(raw), "-i", str(audio)]
    if bgm:
        b = base.ensure_bgm(wd / "bgm.mp3")
        inputs += ["-stream_loop", "-1", "-i", str(b)]
        fc = (f"[0:v]{chain}[v];[2:a]volume=0.3[bg];[1:a]asplit[vo][sc];[bg][sc]sidechaincompress=threshold=0.04:ratio=10:attack=20:release=400[duck];"
              "[vo][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    else:
        fc = f"[0:v]{chain}[v];[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    cmd = ["ffmpeg", "-y", "-v", "error", "-progress", "pipe:1", "-nostats", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p", "-profile:v", "high", "-r", str(fps),
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", "-movflags", "+faststart", str(out_mp4)]

    def on_line(line):
        m = re.match(r"out_time_(?:us|ms)=(\d+)", line.strip())
        if m:
            progress(0.6 + 0.4 * min(1.0, int(m.group(1)) / 1e6 / max(total, 1)), "encoding final video")

    rc, err = run(cmd, cwd=str(Path(srt_en).parent) if srt_en else None, line_cb=on_line)
    if rc != 0:
        raise RuntimeError("ffmpeg final render failed: " + err[-600:])
    raw.unlink(missing_ok=True)
    progress(1.0, "done")
    return {"path": str(out_mp4), "seconds": round(time.time() - t0, 1), "width": W, "height": H, "scenes": len(scenes)}
