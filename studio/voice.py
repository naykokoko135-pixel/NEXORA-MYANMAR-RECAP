"""Narration synthesis for the studio.

One narration uses ONE engine end-to-end (voices are never mixed mid-video). The engine ladder is
reference-conditioned GPU worker (only with a voice profile + VOICE_GPU_URL) -> Edge neural TTS -> gTTS -> offline espeak-ng.
Timings are measured from the generated audio, never estimated.
"""
import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import config, tts, voices
from . import core, settings

QUALITY = {"clone": "reference_conditioned", "edge": "standard", "gtts": "basic", "espeak": "low"}
ENGINE_LABEL = {"clone": "gpu-reference-conditioned", "edge": "edge-tts", "gtts": "gtts", "espeak": "offline-espeak"}
PAD = 0.25  # seconds of silence after every sentence (matches the existing pipeline)
_TEST_SENTENCE = "မင်္ဂလာပါ။"


class VoiceError(RuntimeError):
    pass


def espeak_available() -> bool:
    return bool(shutil.which("espeak-ng") or shutil.which("espeak"))


def clone_configured() -> bool:
    return os.getenv("VOICE_GPU_URL", "").startswith("https://")


def _pct(v: str) -> int:
    m = re.fullmatch(r"([+-]?\d+)(?:%|Hz)?", str(v or "0").strip())
    return int(m.group(1)) if m else 0


def _combine(preset_value: str, user_value: str, unit: str) -> str:
    return f"{_pct(preset_value) + _pct(user_value):+d}{unit}"


def voice_params(voice_key: str, user_rate="+0%", user_pitch="+0Hz") -> tuple[str, str, str]:
    """(edge voice name, edge rate, edge pitch) combining the preset with the user's rate/pitch offsets."""
    name, pitch, rate = config.VOICE_PRESETS.get(voice_key, config.VOICE_PRESETS["story_female"])
    return name, _combine(rate, user_rate, "%"), _combine(pitch, user_pitch, "Hz")


def ladder(voice_key: str, profile: dict | None) -> list[str]:
    if voice_key == settings.OFFLINE_PRESET:
        return ["espeak"]
    env = [e.strip() for e in os.getenv("NEXORA_TTS_ENGINES", "").split(",") if e.strip()]
    order = env or ["clone", "edge", "gtts", "espeak"]
    out = []
    for e in order:
        if e == "clone" and not (profile and clone_configured()):
            continue
        if e == "espeak" and not espeak_available():
            continue
        out.append(e)
    return out


# ------------------------------------------------------------------ engine primitives (text -> wav 24k mono + padding)
def _to_wav(src, dst):
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ar", "24000", "-ac", "1", "-af", f"apad=pad_dur={PAD}", "-c:a", "pcm_s16le", str(dst)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not Path(dst).exists():
        raise VoiceError("audio conversion failed: " + r.stderr[-200:])


def _edge_one(text, voice_key, user_rate, user_pitch, raw):
    name, rate, pitch = voice_params(voice_key, user_rate, user_pitch)
    asyncio.run(tts._edge(text, name, rate, pitch, raw))


def _espeak_one(text, voice_key, user_rate, out_wav):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    gender = next((p["gender"] for p in settings.voice_presets() if p["id"] == voice_key), "male")
    variant = "my+f3" if gender == "female" else "my"
    speed = max(80, min(260, int(150 * (1 + _pct(user_rate) / 100))))
    r = subprocess.run([exe, "-v", variant, "-s", str(speed), "-w", str(out_wav), text], capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not Path(out_wav).exists() or Path(out_wav).stat().st_size < 1000:
        raise VoiceError("espeak failed: " + r.stderr[-200:])


def synth_sentence(engine, text, voice_key, profile, user_rate, user_pitch, out_wav, tmpdir: Path):
    """Synthesize one sentence to a 24 kHz mono WAV (with trailing pad). Raises on failure."""
    base = Path(tmpdir) / f"{Path(out_wav).stem}_raw"
    src = base.with_suffix(".wav" if engine == "espeak" else ".mp3")
    try:
        if engine == "espeak":
            _espeak_one(text, voice_key, user_rate, src)
        elif engine == "edge":
            _edge_one(text, voice_key, user_rate, user_pitch, src)
        elif engine == "gtts":
            tts._gtts(text, src)
        elif engine == "clone":
            tts._clone(text, profile, src)
        else:
            raise VoiceError("unknown engine " + engine)
        if not src.exists() or src.stat().st_size < 800:
            raise VoiceError(f"{engine} returned no audio")
        _to_wav(src, out_wav)
    finally:
        src.unlink(missing_ok=True)


def wav_duration(path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def probe_engine(engine, voice_key, profile, user_rate, user_pitch, tmp: Path) -> str | None:
    """Return None when the engine works, else a short reason."""
    out = tmp / f"probe_{engine}.wav"
    try:
        synth_sentence(engine, _TEST_SENTENCE, voice_key, profile, user_rate, user_pitch, out, tmp)
        return None if out.exists() and wav_duration(out) > 0.2 else "empty audio"
    except Exception as e:
        return str(e)[:160]
    finally:
        out.unlink(missing_ok=True)


# ------------------------------------------------------------------ whole narration
def build_narration(sections, voice_key, profile, workdir: Path, out_mp3: Path, out_wav: Path | None = None, *,
                    user_rate="+0%", user_pitch="+0Hz", log=print, progress=lambda f: None, check_cancel=lambda: None, workers=4) -> dict:
    """Synthesize every sentence with one engine, measure real timings, write MP3 (and optional WAV)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    flat = [dict(my=it["my"], en=it.get("en", ""), sec=si) for si, s in enumerate(sections) for it in s["items"]]
    if not flat:
        raise VoiceError("Script has no sentences")
    candidates = ladder(voice_key, profile)
    if not candidates:
        raise VoiceError("No narration engine is available on this host (install espeak-ng or configure internet TTS).")
    notes, chosen, wavs = [], None, None
    for engine in candidates:
        check_cancel()
        why = probe_engine(engine, voice_key, profile, user_rate, user_pitch, workdir)
        if why:
            notes.append(f"{ENGINE_LABEL[engine]} unavailable: {why}")
            log(f"[voice] {ENGINE_LABEL[engine]} unavailable: {why}")
            continue
        log(f"[voice] using engine {ENGINE_LABEL[engine]} ({QUALITY[engine]} quality) for {len(flat)} sentences")
        try:
            wavs = _synth_all(engine, flat, voice_key, profile, user_rate, user_pitch, workdir, log, progress, check_cancel, workers)
            chosen = engine
            break
        except VoiceError as e:
            notes.append(f"{ENGINE_LABEL[engine]} failed mid-run: {e}")
            log(f"[voice] {ENGINE_LABEL[engine]} failed mid-run ({e}); restarting whole narration with the next engine")
    if not chosen:
        raise VoiceError("All narration engines failed: " + "; ".join(notes))
    t, timeline = 0.0, []
    lst = workdir / "concat.txt"
    with lst.open("w") as f:
        for it, w in zip(flat, wavs):
            d = wav_duration(w)
            timeline.append({"start": round(t, 3), "end": round(t + d - (PAD - 0.05), 3), "my": it["my"], "en": it["en"], "sec": it["sec"]})
            t += d
            f.write(f"file '{Path(w).resolve()}'\n")
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:a", "libmp3lame", "-b:a", "128k", str(out_mp3)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not out_mp3.exists() or out_mp3.stat().st_size < 5000:
        raise VoiceError("MP3 encode failed: " + r.stderr[-200:])
    if out_wav is not None:
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out_wav)], capture_output=True, text=True)
        if r.returncode != 0 or not out_wav.exists():
            raise VoiceError("WAV export failed: " + r.stderr[-200:])
    for w in wavs:
        Path(w).unlink(missing_ok=True)
    dur = core.ffprobe_duration(out_mp3) or t
    return {"timeline": timeline, "duration": dur, "engine": ENGINE_LABEL[chosen], "quality": QUALITY[chosen], "voice": voice_key,
            "sentences": len(flat), "notes": notes}


def _synth_all(engine, flat, voice_key, profile, user_rate, user_pitch, workdir, log, progress, check_cancel, workers):
    cache = workdir / f"tts_{engine}"
    cache.mkdir(exist_ok=True)
    done = [0]
    lock = threading.Lock()

    def one(i):
        check_cancel()
        text = flat[i]["my"]
        key = hashlib.sha1(f"{engine}|{voice_key}|{user_rate}|{user_pitch}|{text}".encode()).hexdigest()[:10]
        wav = cache / f"s{i:05d}_{key}.wav"
        if not (wav.exists() and wav.stat().st_size > 1000):  # cached from an interrupted earlier attempt
            last = None
            for attempt in range(3 if engine != "espeak" else 1):
                try:
                    synth_sentence(engine, text, voice_key, profile, user_rate, user_pitch, wav, cache)
                    last = None
                    break
                except Exception as e:  # noqa
                    last = e
                    time.sleep(1.2 * (attempt + 1))
            if last is not None:
                raise VoiceError(f"sentence {i + 1}: {str(last)[:120]}")
        with lock:
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(flat):
                progress(done[0] / len(flat))
        return wav

    with ThreadPoolExecutor(max_workers=workers if engine != "espeak" else 2) as ex:
        futs = [ex.submit(one, i) for i in range(len(flat))]
        try:
            return [f.result() for f in futs]
        except Exception:
            for f in futs:
                f.cancel()
            raise


# ------------------------------------------------------------------ preview
def preview(text: str, voice_key: str, user_rate="+0%", user_pitch="+0Hz", profile=None) -> dict:
    """Synthesize a short sample for the Voice Studio. Returns metadata and the file path."""
    text = " ".join(str(text or "").split())
    if not text or len(text) > 300:
        raise ValueError("Preview text must be 1-300 characters")
    core.PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for old in core.PREVIEW_DIR.glob("*.mp3"):  # keep the folder small
        if time.time() - old.stat().st_mtime > 3600:
            old.unlink(missing_ok=True)
    tmp = core.work_dir(0) / "preview"
    tmp.mkdir(parents=True, exist_ok=True)
    notes = []
    for engine in ladder(voice_key, profile):
        wav = tmp / f"{uuid.uuid4().hex}.wav"
        try:
            synth_sentence(engine, text, voice_key, profile, user_rate, user_pitch, wav, tmp)
            pid = uuid.uuid4().hex
            out = core.PREVIEW_DIR / f"{pid}.mp3"
            r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "96k", str(out)], capture_output=True, text=True)
            if r.returncode != 0:
                raise VoiceError(r.stderr[-120:])
            note = "; ".join(notes) or ("Reference sample is used only when the GPU worker is configured." if engine == "clone" else "")
            return {"ok": True, "engine": ENGINE_LABEL[engine], "quality": QUALITY[engine], "duration": round(wav_duration(wav), 2), "id": pid, "path": str(out), "note": note}
        except Exception as e:
            notes.append(f"{ENGINE_LABEL[engine]}: {str(e)[:100]}")
        finally:
            wav.unlink(missing_ok=True)
    raise VoiceError("No engine could synthesize the preview. " + "; ".join(notes))


# ------------------------------------------------------------------ voice profiles (reference samples)
def profile_view(p: dict) -> dict:
    sp = Path(p.get("sample_path", ""))
    exists = sp.exists()
    return {"name": p["name"], "size": sp.stat().st_size if exists else 0, "ext": sp.suffix.lstrip("."), "created": sp.stat().st_mtime if exists else None,
            "duration": core.ffprobe_duration(sp) if exists else None, "owner": p.get("owner", ""), "used_for_synthesis": clone_configured()}


def clone_status() -> dict:
    if clone_configured():
        return {"mode": "reference_conditioned_synthesis",
                "note": "Reference samples are sent to your configured GPU voice worker (VOICE_GPU_URL), which synthesizes Burmese speech conditioned on the sample. "
                        "This is reference-conditioned synthesis, not a recording of the speaker; quality depends on the worker model. Only upload voices you have the right to use."}
    return {"mode": "unavailable",
            "note": "No GPU voice worker is configured (VOICE_GPU_URL). Uploaded samples are stored but are NOT used for synthesis; narration uses the selected preset voice. "
                    "Reference-conditioned synthesis needs a separate GPU host and cannot run on Render Free."}
