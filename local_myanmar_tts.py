"""Optional on-device Burmese TTS adapter.

This backend runs inference inside the NEXORA process. Model weights and the
public reference sample are fetched from Hugging Face on first use; narration
text is not sent to a hosted TTS inference API. Enable explicitly with
NEXORA_LOCAL_TTS_ENABLED=1.
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
_reference_audio = None
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


def _get_model_and_reference():
    """Load the low-level API with the model's required reference WAV.

    myanmartts==1.0.2's high-level convenience wrapper can pass None as
    ref_audio, although the underlying StableTTS API requires a reference WAV.
    Use the documented low-level API and bundled public sample explicitly.
    """
    global _model, _reference_audio
    if _model is None or _reference_audio is None:
        try:
            from huggingface_hub import hf_hub_download
            from myanmar_tts.api import StableTTSAPI
        except ImportError as exc:
            raise RuntimeError(
                "Local MyanmarTTS dependencies မပြည့်စုံပါ။ "
                "requirements-local-tts.txt ကို install လုပ်ပါ။"
            ) from exc

        repo_id = "freococo/MyanmarTTS"
        try:
            model_path = hf_hub_download(repo_id=repo_id, filename="model_fp16.pt")
            vocoder_path = hf_hub_download(repo_id=repo_id, filename="vocos.pt")
            reference_path = hf_hub_download(
                repo_id=repo_id, filename="samples/sample_0.wav"
            )
            model = StableTTSAPI(model_path, vocoder_path, "vocos")
            model.to(os.getenv("NEXORA_LOCAL_TTS_DEVICE", "cpu"))
            model.eval()
        except Exception as exc:
            raise RuntimeError(
                "MyanmarTTS model/reference audio ကို ပြင်ဆင်မရပါ။ "
                "Hugging Face download နှင့် PyTorch/TorchCodec dependencies ကို စစ်ပါ။"
            ) from exc
        _model = model
        _reference_audio = reference_path
    return _model, _reference_audio


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
        model, reference_audio = _get_model_and_reference()
        try:
            audio, _mel = model.inference(
                text,
                reference_audio,
                "burmese",
                step=8,
                solver="euler",
                cfg=3.0,
            )
        except Exception as exc:
            raise RuntimeError(
                "Local MyanmarTTS အသံဖန်တီးမှု မအောင်မြင်ပါ။ "
                "အောက်ပါ error အကြောင်းရင်းကို စစ်ဆေးပါ။"
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
