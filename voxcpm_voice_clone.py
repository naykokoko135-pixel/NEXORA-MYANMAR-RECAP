"""Creator-consented reference-audio voice cloning with VoxCPM2.

This optional backend is disabled on the default Render Free host. Reference audio
is written to a short-lived temporary file and removed after synthesis.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from io import BytesIO

MAX_TEXT_CHARS = 3000
MAX_REFERENCE_BYTES = 20 * 1024 * 1024
_ALLOWED_SUFFIXES = {".wav", ".mp3", ".m4a", ".ogg"}


def validate_voice_clone_request(text: str, filename: str, reference_audio: bytes) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("မြန်မာစာသား ထည့်ပါ။")
    if len(cleaned) > MAX_TEXT_CHARS:
        raise ValueError("စာသားသည် စာလုံး ၃,၀၀၀ ထက် မကျော်ရပါ။")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise ValueError("Reference အသံသည် WAV/MP3/M4A/OGG ဖြစ်ရပါမယ်။")
    if not isinstance(reference_audio, bytes) or not reference_audio:
        raise ValueError("သိမ်းထားသော Reference အသံဖိုင် မတွေ့ပါ။")
    if len(reference_audio) > MAX_REFERENCE_BYTES:
        raise ValueError("Reference အသံဖိုင်သည် ၂၀ MB ထက် ကျော်နေပါတယ်။")
    return cleaned


def _synthesize_sync(text: str, filename: str, reference_audio: bytes) -> bytes:
    from voxcpm_voice_design import _get_model, _validate_wav_bytes

    suffix = Path(filename).suffix.lower()
    source_path = None
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="nexora-voice-reference-", suffix=suffix, delete=False) as temp:
            temp.write(reference_audio)
            source_path = temp.name
        # VoxCPM's reference_wav_path expects WAV. Normalize Telegram voice notes,
        # MP3, M4A and OGG samples to mono 24 kHz PCM WAV before inference.
        import imageio_ffmpeg
        wav_path = source_path + ".wav"
        converted = subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
                "-y", "-i", source_path, "-vn", "-ac", "1", "-ar", "24000",
                "-c:a", "pcm_s16le", wav_path,
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if converted.returncode != 0 or not os.path.isfile(wav_path) or os.path.getsize(wav_path) <= 44:
            raise RuntimeError("Reference အသံကို WAV ပြောင်းမရပါ။ အသံဖိုင်ကို ပြန်စစ်ပါ။")
        model = _get_model()
        audio = model.generate(
            text=text,
            reference_wav_path=wav_path,
            cfg_value=2.0,
            inference_timesteps=10,
            retry_badcase=True,
        )
        import soundfile as sf
        output = BytesIO()
        sf.write(output, audio, model.tts_model.sample_rate, format="WAV", subtype="PCM_16")
        result = output.getvalue()
        if not result or len(result) > 20 * 1024 * 1024:
            raise RuntimeError("ထုတ်ပေးသော WAV ဖိုင်သည် ဗလာဖြစ်နေသည် သို့မဟုတ် ၂၀ MB ထက် ကျော်နေပါတယ်။")
        _validate_wav_bytes(result)
        return result
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError("ကိုယ်ပိုင်အသံ Clone မအောင်မြင်ပါ။ Reference ဖိုင်နှင့် GPU memory ကို စစ်ဆေးပါ။") from exc
    finally:
        for temp_path in (source_path, wav_path):
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass


async def synthesize_cloned_burmese_voice(text: str, filename: str, reference_audio: bytes) -> bytes:
    """Generate Burmese speech in the creator's saved reference voice."""
    cleaned = validate_voice_clone_request(text, filename, reference_audio)
    from voxcpm_voice_design import voice_design_host_unavailable_reason

    unavailable = voice_design_host_unavailable_reason()
    if unavailable:
        raise RuntimeError(unavailable)
    return await asyncio.to_thread(_synthesize_sync, cleaned, filename, reference_audio)
