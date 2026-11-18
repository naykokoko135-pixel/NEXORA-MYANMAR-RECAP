"""Optional Burmese neural speech synthesis using the online Edge TTS service.

Text is sent to Microsoft's online speech service when a user explicitly invokes /tts.
This is a no-key convenience integration, not a guaranteed or official Azure API.
"""
import asyncio
import tempfile
from pathlib import Path

VOICE_MAP = {
    "female": "my-MM-NilarNeural",
    "male": "my-MM-ThihaNeural",
}
MAX_TEXT_CHARS = 6000
MAX_AUDIO_BYTES = 20 * 1024 * 1024
SYNTHESIS_TIMEOUT_SECONDS = 120


def validate_tts_request(text: str, voice: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("မြန်မာ Voice-over စာသား ထည့်ပါ။")
    if len(cleaned) > MAX_TEXT_CHARS:
        raise ValueError("Voice-over စာသားသည် စာလုံး ၆,၀၀၀ ထက် မကျော်ရပါ။")
    selected = (voice or "").strip().lower()
    if selected not in VOICE_MAP:
        raise ValueError("အသံရွေးချယ်မှု female သို့မဟုတ် male ဖြစ်ရပါမည်။")
    return VOICE_MAP[selected]


async def synthesize_burmese_speech(text: str, voice: str = "female") -> bytes:
    """Return MP3 bytes; requires network access to the online speech service."""
    voice_id = validate_tts_request(text, voice)
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("TTS package မတင်ရသေးပါ။ Service ကို redeploy လုပ်ပါ။") from exc

    with tempfile.TemporaryDirectory(prefix="nexora_tts_") as temp_dir:
        output = Path(temp_dir) / "nexora_voiceover.mp3"
        try:
            communicate = edge_tts.Communicate(text.strip(), voice_id)
            await asyncio.wait_for(
                communicate.save(str(output)),
                timeout=SYNTHESIS_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError("အသံဖန်တီးချိန် ၂ မိနစ်ကျော်သွားပါတယ်။ စာသားကို အပိုင်းခွဲပါ။") from exc
        except Exception as exc:
            # Do not expose remote request details or user script in bot replies/logs.
            raise RuntimeError("Online Burmese TTS service ကို ချိတ်ဆက်မရပါ။ ခဏနေမှ ပြန်စမ်းပါ။") from exc

        if not output.exists():
            raise RuntimeError("အသံဖိုင် မရရှိပါ။ ပြန်စမ်းပါ။")
        audio = output.read_bytes()
        if not audio or len(audio) > MAX_AUDIO_BYTES:
            raise RuntimeError("MP3 ဖိုင်အရွယ်အစား ၂၀ MB ထက် ကျော်နေသည် သို့မဟုတ် ဖိုင်ဗလာဖြစ်နေသည်။")
        return audio
