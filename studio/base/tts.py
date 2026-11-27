"""Burmese TTS: edge-tts (free) -> gTTS fallback; optional GPU voice-clone worker. Timeline is measured, not estimated."""
import asyncio
import base64
import subprocess
from pathlib import Path

import requests

from . import config


def ffprobe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def _to_wav(src, dst, pad=0.25):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ar", "24000", "-ac", "1",
                    "-af", f"apad=pad_dur={pad}", str(dst)], check=True)


async def _edge(text, voice, rate, pitch, out):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))


def _gtts(text, out):
    from gtts import gTTS
    gTTS(text, lang="my").save(str(out))


def _clone(text, profile, out):
    url = config.os.getenv("VOICE_GPU_URL", "")
    tok = config.os.getenv("VOICE_GPU_TOKEN", "")
    if not url.startswith("https://"):
        raise RuntimeError("GPU worker URL (https) not set")
    sample = Path(profile["sample_path"]).read_bytes()
    r = requests.post(url.rstrip("/") + "/clone", timeout=300, headers={"Authorization": f"Bearer {tok}"},
                      json={"text": text, "sample_b64": base64.b64encode(sample).decode(), "lang": "my"})
    r.raise_for_status()
    Path(out).write_bytes(r.content)


async def _one(i, text, voice_key, profile, wd, sem, log):
    async with sem:
        raw = Path(wd) / f"s{i:05d}.mp3"
        wav = Path(wd) / f"s{i:05d}.wav"
        v, pitch, rate = config.VOICE_PRESETS.get(voice_key, config.VOICE_PRESETS["story_female"])
        done = False
        if profile:
            try:
                await asyncio.to_thread(_clone, text, profile, raw)
                done = raw.exists() and raw.stat().st_size > 1000
            except Exception as e:
                log(f"[tts] clone fallback: {e}")
        for _ in range(3):
            if done:
                break
            try:
                await _edge(text, v, rate, pitch, raw)
                done = raw.exists() and raw.stat().st_size > 1000
            except Exception:
                await asyncio.sleep(1.5)
        if not done:
            try:
                await asyncio.to_thread(_gtts, text, raw)
                done = raw.exists() and raw.stat().st_size > 1000
            except Exception:
                pass
        if not done:
            raise RuntimeError(f"TTS failed for sentence {i}")
        await asyncio.to_thread(_to_wav, raw, wav)
        raw.unlink(missing_ok=True)
        return wav


async def _all(flat, voice_key, profile, wd, log):
    sem = asyncio.Semaphore(4)
    return await asyncio.gather(*[_one(i, s["my"], voice_key, profile, wd, sem, log) for i, s in enumerate(flat)])


def build_audio(sections, voice_key, profile, wd, out_mp3, log=print):
    """Returns timeline [{start,end,my,en,sec}] with exact timings from the real audio."""
    wd = Path(wd)
    wd.mkdir(parents=True, exist_ok=True)
    flat = [dict(**it, sec=si) for si, s in enumerate(sections) for it in s["items"]]
    wavs = asyncio.run(_all(flat, voice_key, profile, wd, log))
    t, timeline = 0.0, []
    lst = wd / "list.txt"
    with lst.open("w") as f:
        for it, w in zip(flat, wavs):
            d = ffprobe_dur(w)
            timeline.append(dict(start=t, end=t + d - 0.2, my=it["my"], en=it["en"], sec=it["sec"]))
            t += d
            f.write(f"file '{Path(w).resolve()}'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:a", "libmp3lame", "-b:a", "128k", str(out_mp3)], check=True)
    for w in wavs:
        Path(w).unlink(missing_ok=True)
    if not Path(out_mp3).exists() or Path(out_mp3).stat().st_size < 5000:
        raise RuntimeError("MP3 မထွက်ပါ — အောင်မြင်ကြောင်း မပြပါ")
    return timeline, ffprobe_dur(out_mp3)
