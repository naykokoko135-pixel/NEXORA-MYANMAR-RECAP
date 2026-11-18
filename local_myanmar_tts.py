"""Optional on-device Burmese TTS adapter.

This backend runs inference inside the NEXORA process. Model weights are fetched
by the upstream package on first use; narration text is not sent to a hosted TTS
inference API. Enable explicitly with NEXORA_LOCAL_TTS_ENABLED=1.
"""
import asyncio
import os
import struct
import threading
import wave
from io import BytesIO

MAX_LOCAL_TEXT_CHARS = 1200
SAMPLE_RATE = 44100
_model = None
_model_lock = threading.Lock()


def _enabled() -> bool:
    return os.getenv("NEXORA_LOCAL_TTS_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _flatten_samples(audio):
    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    if hasattr(audio, "squeeze"):
        audio = audio.squeeze()
    if hasattr(audio, "tolist"):
        audio = audio.tolist()

    def walk(value):
        if isinstance(value, (list, tuple)):
            for item in value:
                yield from walk(item)
        else:
            yield float(value)

    return list(walk(audio))


def _get_model():
    global _model
    if _model is None:
        try:
            from myanmar_tts import MyanmarTTS
        except ImportError as exc:
            raise RuntimeError(
                "Local MyanmarTTS မတင်ရသေးပါ။ optional local TTS requirements ကို install လုပ်ပါ။"
            ) from exc
        # CPU is the safe default; deployments without suitable memory/CPU may
        # need a separate worker or a more capable host.
        _model = MyanmarTTS(device=os.getenv("NEXORA_LOCAL_TTS_DEVICE", "cpu"))
    return _model


def _wav_bytes(samples) -> bytes:
    if not samples:
        raise RuntimeError("Local MyanmarTTS မှ အသံဒေတာ မရရှိပါ။")
    pcm = bytearray()
    for sample in samples:
        value = max(-1.0, min(1.0, sample))
        pcm.extend(struct.pack("<h", int(value * 32767)))
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(bytes(pcm))
    return output.getvalue()


def _synthesize_sync(text: str) -> bytes:
    with _model_lock:
        model = _get_model()
        try:
            audio = model.tts(text, solver="euler", step=8, cfg=3.0)
        except Exception as exc:
            raise RuntimeError(
                "Local MyanmarTTS အသံဖန်တီးမှု မအောင်မြင်ပါ။ စာသားတိုတိုဖြင့် ပြန်စမ်းပါ။"
            ) from exc
        return _wav_bytes(_flatten_samples(audio))


async def synthesize_local_burmese_speech(text: str) -> bytes:
    """Return a WAV generated locally; requires explicit enablement and optional deps."""
    cleaned = (text or "").strip()
    if not _enabled():
        raise RuntimeError(
            "Local MyanmarTTS ကို မဖွင့်ရသေးပါ။ Host မှာ NEXORA_LOCAL_TTS_ENABLED=1 "
            "သတ်မှတ်ပြီး optional local TTS dependencies တင်ပြီးမှ အသုံးပြုနိုင်ပါတယ်။"
        )
    if not cleaned:
        raise ValueError("မြန်မာ Voice-over စာသား ထည့်ပါ။")
    if len(cleaned) > MAX_LOCAL_TEXT_CHARS:
        raise ValueError("Local MyanmarTTS စမ်းသပ်မှုအတွက် စာသားကို စာလုံး ၁,၂၀၀ အောက်ထားပါ။")
    return await asyncio.to_thread(_synthesize_sync, cleaned)
