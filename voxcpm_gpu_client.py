"""Authenticated client for the optional remote VoxCPM2 GPU worker."""
from __future__ import annotations
import asyncio
import base64
import json
import os
import urllib.error
import urllib.request

MAX_RESPONSE_BYTES = 20 * 1024 * 1024

def gpu_worker_configured() -> bool:
    return bool(os.getenv("NEXORA_VOXCPM_GPU_URL", "").strip() and os.getenv("NEXORA_VOXCPM_WORKER_TOKEN", "").strip())

def _post(payload: dict) -> bytes:
    url = os.getenv("NEXORA_VOXCPM_GPU_URL", "").strip()
    token = os.getenv("NEXORA_VOXCPM_WORKER_TOKEN", "").strip()
    if not url or not token:
        raise RuntimeError("GPU Worker URL/Token မပြင်ဆင်ရသေးပါ။")
    body = json.dumps({**payload, "token": token}).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            raw = response.read(28 * 1024 * 1024)
    except urllib.error.HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", "replace")
        raise RuntimeError(f"GPU Worker HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError("GPU Worker ချိတ်ဆက်မရပါ။ URL/Worker အခြေအနေကို စစ်ပါ။") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
        wav = base64.b64decode(data["wav_base64"], validate=True)
    except Exception as exc:
        raise RuntimeError("GPU Worker မှ WAV response မမှန်ကန်ပါ။") from exc
    if not wav or len(wav) > MAX_RESPONSE_BYTES:
        raise RuntimeError("GPU Worker WAV ဗလာဖြစ်နေသည် သို့မဟုတ် ၂၀ MB ကျော်နေသည်။")
    return wav

async def synthesize_on_gpu(payload: dict) -> bytes:
    return await asyncio.to_thread(_post, payload)
