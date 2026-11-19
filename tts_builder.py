"""Optional Burmese neural speech synthesis using the online Edge TTS service.

Text is sent to Microsoft's online speech service when a user explicitly invokes /tts.
This is a no-key convenience integration, not a guaranteed or official Azure API.
"""
import asyncio
import re
import tempfile
from pathlib import Path

VOICE_MAP = {
    "female": "my-MM-NilarNeural",
    "male": "my-MM-ThihaNeural",
}

# Delivery styles reuse the two currently available Burmese neural speakers.
VOICE_PRESETS = {
    "female": {"voice": "female", "rate": "+0%", "pitch": "+0Hz", "label": "အမျိုးသမီး ပုံမှန်"},
    "male": {"voice": "male", "rate": "+0%", "pitch": "+0Hz", "label": "အမျိုးသား ပုံမှန်"},
    "narrator": {"voice": "female", "rate": "-5%", "pitch": "-1Hz", "label": "ဇာတ်ကြောင်းပြော"},
    "hero": {"voice": "male", "rate": "+5%", "pitch": "+2Hz", "label": "သူရဲကောင်း"},
    "villain": {"voice": "male", "rate": "-12%", "pitch": "-5Hz", "label": "ဗီလိန်"},
    "elder": {"voice": "male", "rate": "-18%", "pitch": "-3Hz", "label": "အသက်ကြီးဇာတ်ကောင်ပုံစံ"},
    "youth": {"voice": "female", "rate": "+8%", "pitch": "+3Hz", "label": "တက်ကြွလူငယ်"},
    "emotional": {"voice": "female", "rate": "-8%", "pitch": "-1Hz", "label": "ခံစားချက်ပြင်းပြ"},
    "energetic": {"voice": "male", "rate": "+12%", "pitch": "+2Hz", "label": "Action / တက်ကြွ"},
    "mystery": {"voice": "female", "rate": "-12%", "pitch": "-4Hz", "label": "လျှို့ဝှက်ဆန်းကြယ်"},
    "comedy": {"voice": "female", "rate": "+10%", "pitch": "+3Hz", "label": "ဟာသ / ပေါ့ပါး"},
    "calm": {"voice": "male", "rate": "-10%", "pitch": "-2Hz", "label": "အေးဆေးတည်ငြိမ်"},
}

def get_tts_preset(preset: str) -> dict:
    selected = (preset or "").strip().lower()
    if selected not in VOICE_PRESETS:
        raise ValueError("အသံ Preset မမှန်ပါ။ /voices ကိုကြည့်ပြီး ရွေးပါ။")
    return dict(VOICE_PRESETS[selected])
MAX_TEXT_CHARS = 30000
MAX_AUDIO_BYTES = 45 * 1024 * 1024
SYNTHESIS_TIMEOUT_SECONDS = 120
TTS_CHUNK_CHARS = 3000


def split_tts_text(text: str, max_chars: int = TTS_CHUNK_CHARS) -> list[str]:
    """Split long narration at sentence/word boundaries for bounded TTS requests."""
    cleaned = (text or "").strip()
    if not cleaned or max_chars < 100:
        raise ValueError("TTS စာသား သို့မဟုတ် အပိုင်းအရွယ်အစား မမှန်ကန်ပါ။")
    sentences = [part.strip() for part in re.split(r"(?<=[။!?])\s+|\n+", cleaned) if part.strip()]
    chunks = []
    current = ""
    for sentence in sentences:
        while len(sentence) > max_chars:
            split_at = sentence.rfind(" ", 0, max_chars + 1)
            if split_at < 1:
                split_at = max_chars
            piece, sentence = sentence[:split_at].strip(), sentence[split_at:].strip()
            if piece:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(piece)
        candidate = (current + " " + sentence).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def validate_tts_request(text: str, voice: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("မြန်မာ Voice-over စာသား ထည့်ပါ။")
    if len(cleaned) > MAX_TEXT_CHARS:
        raise ValueError("Voice-over စာသားသည် စာလုံး ၃၀,၀၀၀ ထက် မကျော်ရပါ။")
    selected = (voice or "").strip().lower()
    if selected not in VOICE_PRESETS:
        raise ValueError("အသံ Preset မမှန်ပါ။ /voices ကိုကြည့်ပြီး ရွေးပါ။")
    return VOICE_MAP[VOICE_PRESETS[selected]["voice"]]


async def synthesize_burmese_speech(text: str, voice: str = "female") -> bytes:
    """Return MP3 bytes; requires network access to the online speech service."""
    voice_id = validate_tts_request(text, voice)
    preset = get_tts_preset(voice)
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("TTS package မတင်ရသေးပါ။ Service ကို redeploy လုပ်ပါ။") from exc

    with tempfile.TemporaryDirectory(prefix="nexora_tts_") as temp_dir:
        output = Path(temp_dir) / "nexora_voiceover.mp3"
        try:
            communicate = edge_tts.Communicate(text.strip(), voice_id, rate=preset["rate"], pitch=preset["pitch"])
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
            raise RuntimeError("MP3 ဖိုင်အရွယ်အစား ၄၅ MB ထက် ကျော်နေသည် သို့မဟုတ် ဖိုင်ဗလာဖြစ်နေသည်။")
        return audio



def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def build_word_aligned_srt(boundaries: list[dict], max_chars: int = 42, max_duration: float = 4.5) -> str:
    """Build SRT captions from Edge TTS word-boundary metadata (100ns ticks)."""
    if not boundaries:
        raise ValueError("အသံမှ စာတန်းအချိန်မှတ်တမ်း မရရှိပါ။")
    captions = []
    current_text = ""
    current_start = None
    current_end = None

    def flush():
        nonlocal current_text, current_start, current_end
        caption = current_text.strip()
        if caption and current_start is not None and current_end is not None:
            start = max(0.0, current_start)
            captions.append((start, max(start + 0.2, current_end), caption))
        current_text = ""
        current_start = None
        current_end = None

    for item in boundaries:
        word = str(item.get("text", ""))
        if not word:
            continue
        try:
            start = max(0.0, float(item["offset"]) / 10_000_000)
            end = max(start + 0.05, (float(item["offset"]) + float(item["duration"])) / 10_000_000)
        except (KeyError, TypeError, ValueError):
            continue
        too_long = bool(current_text) and len((current_text + word).strip()) > max_chars
        too_slow = current_start is not None and end - current_start > max_duration
        if too_long or too_slow:
            flush()
        if current_start is None:
            current_start = start
        current_text += word
        current_end = end
        if word.rstrip().endswith(("။", "!", "?", "…", ".", "၊")):
            flush()

    flush()
    if not captions:
        raise ValueError("စာတန်းထိုးအတွက် အသံအချိန်မှတ်တမ်း မလုံလောက်ပါ။")
    blocks = []
    for index, (start, end, caption) in enumerate(captions, start=1):
        blocks.append(f"{index}\n{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n{caption}")
    return "\n\n".join(blocks) + "\n"


async def synthesize_burmese_speech_with_srt(text: str, voice: str = "female") -> tuple[bytes, str]:
    """Return MP3 bytes and SRT aligned to Edge TTS word-boundary timings."""
    voice_id = validate_tts_request(text, voice)
    preset = get_tts_preset(voice)
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("TTS package မတင်ရသေးပါ။ Service ကို redeploy လုပ်ပါ။") from exc
    audio_chunks = []
    boundaries = []

    async def collect(chunk: str, offset_ticks: int):
        local_boundaries = []
        communicate = edge_tts.Communicate(chunk, voice_id, rate=preset["rate"], pitch=preset["pitch"], boundary="WordBoundary")
        async for message in communicate.stream():
            if message.get("type") == "audio":
                audio_chunks.append(message.get("data", b""))
            elif message.get("type") == "WordBoundary":
                adjusted = dict(message)
                adjusted["offset"] = int(message.get("offset", 0)) + offset_ticks
                local_boundaries.append(adjusted)
        if not local_boundaries:
            raise RuntimeError("TTS အပိုင်းတစ်ခု၏ စာတန်းအချိန်မှတ်တမ်း မရရှိပါ။")
        boundaries.extend(local_boundaries)
        last = local_boundaries[-1]
        return int(last["offset"]) + int(last["duration"])

    try:
        offset_ticks = 0
        for chunk in split_tts_text(text):
            offset_ticks = await asyncio.wait_for(
                collect(chunk, offset_ticks), timeout=SYNTHESIS_TIMEOUT_SECONDS
            )
            if sum(len(part) for part in audio_chunks) > MAX_AUDIO_BYTES:
                raise RuntimeError("MP3 ဖိုင်အရွယ်အစား ၄၅ MB ထက် ကျော်နေပါတယ်။")
    except asyncio.TimeoutError as exc:
        raise RuntimeError("အသံအပိုင်းတစ်ခု ဖန်တီးချိန် ၂ မိနစ်ကျော်သွားပါတယ်။ နောက်မှ ပြန်စမ်းပါ။") from exc
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("Online Burmese TTS service ကို ချိတ်ဆက်မရပါ။ ခဏနေမှ ပြန်စမ်းပါ။") from exc
    audio = b"".join(audio_chunks)
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise RuntimeError("MP3 ဖိုင်အရွယ်အစား ၂၀ MB ထက် ကျော်နေသည် သို့မဟုတ် ဖိုင်ဗလာဖြစ်နေသည်။")
    try:
        srt = build_word_aligned_srt(boundaries)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    return audio, srt
