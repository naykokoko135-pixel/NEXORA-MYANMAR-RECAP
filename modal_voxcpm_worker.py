"""Modal serverless GPU worker for NEXORA VoxCPM2.

Deploy with: modal deploy modal_voxcpm_worker.py
Create Modal secret "nexora-voxcpm-secret" containing NEXORA_VOXCPM_WORKER_TOKEN.
GPU resources are billed by Modal; the worker scales to zero when idle.
"""
import base64
import hmac
import os
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

import modal

app = modal.App("nexora-voxcpm")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install("voxcpm", "soundfile", "fastapi")
)
secret = modal.Secret.from_name("nexora-voxcpm-secret")
MODEL_ID = "openbmb/VoxCPM2"
MAX_TEXT_CHARS = 3000
MAX_REFERENCE_BYTES = 20 * 1024 * 1024
_model = None

DESIGNS = {
    "story_male": ("A mature Burmese-speaking male narrator, warm resonant mid-low voice, clear diction, calm measured pacing.", 1101),
    "story_female": ("A mature Burmese-speaking female narrator, warm clear voice, natural conversational cadence, expressive but controlled pacing.", 1102),
    "young_male": ("A youthful Burmese-speaking male character voice, bright energetic tone, clear diction, lively conversational pacing.", 1103),
    "young_female": ("A youthful Burmese-speaking female character voice, bright friendly tone, clear diction, lively natural pacing.", 1104),
    "elder_male": ("An elderly Burmese-speaking male character voice, gentle textured lower register, deliberate slower pacing, warm and wise delivery.", 1105),
    "villain": ("A fictional Burmese-speaking male antagonist voice, deep dramatic resonant tone, controlled intensity, deliberate cinematic pacing.", 1106),
    "comic": ("A fictional Burmese-speaking female comic character voice, playful bright tone, animated expressive delivery, brisk but clear pacing.", 1107),
    "mystery": ("A fictional Burmese-speaking female mystery narrator, soft low-key tone, restrained suspenseful expression, measured pacing.", 1108),
}

def _get_model():
    global _model
    if _model is None:
        from voxcpm import VoxCPM
        _model = VoxCPM.from_pretrained(MODEL_ID, load_denoiser=False)
    return _model

def _wav_bytes(audio):
    import soundfile as sf
    output = BytesIO()
    sf.write(output, audio, _get_model().tts_model.sample_rate, format="WAV", subtype="PCM_16")
    data = output.getvalue()
    if not data or len(data) > MAX_REFERENCE_BYTES:
        raise ValueError("Generated WAV is empty or exceeds 20 MB")
    return data

@app.function(image=image, gpu="L4", timeout=900, scaledown_window=60, secrets=[secret])
@modal.web_endpoint(method="POST")
def synthesize(payload: dict):
    token = os.environ.get("NEXORA_VOXCPM_WORKER_TOKEN", "")
    supplied = payload.get("token", "")
    if not token or not isinstance(supplied, str) or not hmac.compare_digest(token, supplied):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")
    text = payload.get("text", "")
    mode = payload.get("mode")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_CHARS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid text")
    model = _get_model()
    if mode == "design":
        voice = payload.get("voice")
        if voice not in DESIGNS:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Unknown voice preset")
        description, seed = DESIGNS[voice]
        audio = model.generate(text=f"({description}){text.strip()}", cfg_value=2.0, inference_timesteps=10, seed=seed)
    elif mode == "clone":
        encoded = payload.get("reference_audio", "")
        filename = payload.get("filename", "reference.wav")
        if not isinstance(encoded, str) or len(encoded) > 28_000_000:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid reference audio")
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > MAX_REFERENCE_BYTES:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Reference audio exceeds limit")
        suffix = Path(filename).suffix.lower()
        if suffix not in {".wav", ".mp3", ".m4a", ".ogg"}:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Unsupported audio type")
        source = wav = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(raw)
                source = f.name
            wav = source + ".wav"
            result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", source, "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", wav], capture_output=True, timeout=90)
            if result.returncode or not os.path.isfile(wav) or os.path.getsize(wav) <= 44:
                raise ValueError("Could not normalize reference audio")
            audio = model.generate(text=text.strip(), reference_wav_path=wav, cfg_value=2.0, inference_timesteps=10, retry_badcase=True)
        finally:
            for path in (source, wav):
                if path:
                    try: os.unlink(path)
                    except OSError: pass
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Unknown mode")
    return {"wav_base64": base64.b64encode(_wav_bytes(audio)).decode("ascii")}
