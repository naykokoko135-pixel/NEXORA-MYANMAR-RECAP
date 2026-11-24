"""Optional VoxCPM2 Burmese voice design backend.

This backend creates fictional synthetic voices from text descriptions. It does not
clone real people. It is opt-in and intentionally excluded from Render's default
lightweight requirements.
"""
import asyncio
import os
import threading
import wave
from io import BytesIO

MAX_TEXT_CHARS = 3000
MAX_AUDIO_BYTES = 20 * 1024 * 1024
MODEL_ID = "openbmb/VoxCPM2"
_ENABLED_VALUES = {"1", "true", "yes", "on"}

VOICE_DESIGNS = {
    "story_male": {
        "label": "ဇာတ်ကြောင်းပြော အမျိုးသား",
        "description": "A mature Burmese-speaking male narrator, warm resonant mid-low voice, clear diction, calm measured pacing.",
        "seed": 1101,
    },
    "story_female": {
        "label": "ဇာတ်ကြောင်းပြော အမျိုးသမီး",
        "description": "A mature Burmese-speaking female narrator, warm clear voice, natural conversational cadence, expressive but controlled pacing.",
        "seed": 1102,
    },
    "young_male": {
        "label": "လူငယ် အမျိုးသားဇာတ်ကောင်",
        "description": "A youthful Burmese-speaking male character voice, bright energetic tone, clear diction, lively conversational pacing.",
        "seed": 1103,
    },
    "young_female": {
        "label": "လူငယ် အမျိုးသမီးဇာတ်ကောင်",
        "description": "A youthful Burmese-speaking female character voice, bright friendly tone, clear diction, lively natural pacing.",
        "seed": 1104,
    },
    "elder_male": {
        "label": "အသက်ကြီး အမျိုးသားဇာတ်ကောင်",
        "description": "An elderly Burmese-speaking male character voice, gentle textured lower register, deliberate slower pacing, warm and wise delivery.",
        "seed": 1105,
    },
    "villain": {
        "label": "ဗီလိန်ဇာတ်ကောင်",
        "description": "A fictional Burmese-speaking male antagonist voice, deep dramatic resonant tone, controlled intensity, deliberate cinematic pacing.",
        "seed": 1106,
    },
    "comic": {
        "label": "ဟာသဇာတ်ကောင်",
        "description": "A fictional Burmese-speaking female comic character voice, playful bright tone, animated expressive delivery, brisk but clear pacing.",
        "seed": 1107,
    },
    "mystery": {
        "label": "လျှို့ဝှက်ဆန်းကြယ် ဇာတ်ကောင်",
        "description": "A fictional Burmese-speaking female mystery narrator, soft low-key tone, restrained suspenseful expression, measured pacing.",
        "seed": 1108,
    },
}

_model = None
_model_lock = threading.Lock()


def voice_design_host_unavailable_reason() -> str | None:
    """Return a clear reason when VoxCPM2 cannot run on this host."""
    if os.getenv("NEXORA_VOXCPM_ENABLED", "").strip().lower() not in _ENABLED_VALUES:
        return (
            "VoxCPM2 Voice Design ကို လက်ရှိ Free host မှာ ပိတ်ထားပါတယ်။ "
            "GPU host မရှိသေးလို့ WAV မထုတ်နိုင်ပါ။ အခမဲ့အစားထိုးနည်းအဖြစ် /scenetts ကို သုံးနိုင်ပါတယ်။"
        )
    try:
        import torch
    except ImportError:
        return (
            "ဒီ host မှာ PyTorch မရှိသေးပါ။ VoxCPM2 အတွက် GPU setup မပြည့်စုံပါ။ "
            "အခမဲ့အစားထိုးနည်းအဖြစ် /scenetts ကို သုံးနိုင်ပါတယ်။"
        )
    if not torch.cuda.is_available():
        return (
            "ဒီ host မှာ CUDA GPU မတွေ့ပါ။ Render Free မှာ VoxCPM2 WAV မထုတ်နိုင်ပါ။ "
            "အခမဲ့အစားထိုးနည်းအဖြစ် /scenetts ကို သုံးနိုင်ပါတယ်။"
        )
    return None


def validate_voice_design_request(text: str, voice: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("မြန်မာစာသား ထည့်ပါ။")
    if len(cleaned) > MAX_TEXT_CHARS:
        raise ValueError("စာသားသည် စာလုံး ၃,၀၀၀ ထက် မကျော်ရပါ။")
    selected = (voice or "").strip().lower()
    if selected not in VOICE_DESIGNS:
        raise ValueError("Voice Design အမည်မမှန်ပါ။ /voices ကိုကြည့်ပါ။")
    return selected


def _get_model():
    global _model
    with _model_lock:
        if _model is None:
            try:
                from voxcpm import VoxCPM
            except ImportError as exc:
                raise RuntimeError(
                    "VoxCPM2 optional package မတင်ရသေးပါ။ GPU host တွင် requirements-voxcpm.txt ကို install လုပ်ပါ။"
                ) from exc
            try:
                _model = VoxCPM.from_pretrained(MODEL_ID, load_denoiser=False)
            except Exception as exc:
                raise RuntimeError(
                    "VoxCPM2 model ကို load မလုပ်နိုင်ပါ။ GPU/VRAM နှင့် model download အခြေအနေကို စစ်ပါ။"
                ) from exc
        return _model


def _validate_wav_bytes(data: bytes) -> None:
    """Reject truncated, malformed, or empty WAV output before sending it."""
    try:
        with wave.open(BytesIO(data), "rb") as wav_file:
            if (
                wav_file.getnchannels() < 1
                or wav_file.getsampwidth() != 2
                or wav_file.getframerate() <= 0
                or wav_file.getnframes() <= 0
                or wav_file.getcomptype() != "NONE"
            ):
                raise ValueError("Unsupported or empty WAV stream")
    except (wave.Error, EOFError, OSError, ValueError) as exc:
        raise RuntimeError("ထုတ်ပေးသော WAV ဖိုင်သည် မမှန်ကန်ပါ သို့မဟုတ် အသံမပါဝင်ပါ။") from exc


def _synthesize_sync(text: str, voice: str) -> bytes:
    profile = VOICE_DESIGNS[voice]
    model = _get_model()
    try:
        audio = model.generate(
            text=f"({profile['description']}){text}",
            cfg_value=2.0,
            inference_timesteps=10,
            seed=profile["seed"],
        )
        import soundfile as sf
        output = BytesIO()
        sf.write(output, audio, model.tts_model.sample_rate, format="WAV", subtype="PCM_16")
        result = output.getvalue()
    except Exception as exc:
        raise RuntimeError(
            "VoxCPM2 အသံဖန်တီးမှု မအောင်မြင်ပါ။ GPU memory နှင့် စာသားကို စစ်ဆေးပါ။"
        ) from exc
    if not result or len(result) > MAX_AUDIO_BYTES:
        raise RuntimeError("WAV ဖိုင်ဗလာဖြစ်နေသည် သို့မဟုတ် ၂၀ MB ထက် ကျော်နေသည်။")
    _validate_wav_bytes(result)
    return result


async def synthesize_designed_burmese_voice(text: str, voice: str) -> bytes:
    """Create a Burmese WAV using a fictional text-described synthetic voice."""
    selected = validate_voice_design_request(text, voice)
    from voxcpm_gpu_client import gpu_worker_configured, synthesize_on_gpu
    if gpu_worker_configured():
        result = await synthesize_on_gpu({"mode": "design", "text": text.strip(), "voice": selected})
        _validate_wav_bytes(result)
        return result
    unavailable = voice_design_host_unavailable_reason()
    if unavailable:
        raise RuntimeError(
            unavailable + " Remote GPU Worker မချိတ်ရသေးပါ။ NEXORA_VOXCPM_GPU_URL နှင့် NEXORA_VOXCPM_WORKER_TOKEN ကို သတ်မှတ်ပါ။"
        )
    return await asyncio.to_thread(_synthesize_sync, text.strip(), selected)
