"""Opt-in real-model smoke test for the optional local MyanmarTTS backend.

Run on a separate machine after installing requirements-local-tts.txt:
  NEXORA_LOCAL_TTS_ENABLED=1 python smoke_local_myanmar_tts.py
This downloads model assets on first use and writes a short WAV in the current
directory. It does not contact a hosted inference API or modify Render.
"""
import asyncio
import os
import wave
from pathlib import Path

from local_myanmar_tts import synthesize_local_burmese_speech

OUTPUT = Path("local_myanmar_tts_smoke.wav")
SAMPLE_TEXT = os.getenv("NEXORA_LOCAL_TTS_SMOKE_TEXT", "မင်္ဂလာပါ။ NEXORA အသံစမ်းသပ်မှု ဖြစ်ပါတယ်။")


async def main() -> None:
    if os.getenv("NEXORA_LOCAL_TTS_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        raise SystemExit(
            "Local TTS is disabled. Set NEXORA_LOCAL_TTS_ENABLED=1 in this shell "
            "before running the smoke test."
        )

    audio = await synthesize_local_burmese_speech(SAMPLE_TEXT)
    if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
        raise RuntimeError("Model output is not a valid WAV container.")

    OUTPUT.write_bytes(audio)
    with wave.open(str(OUTPUT), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        channels = wav.getnchannels()
        duration = frames / rate if rate else 0
        if frames <= 0 or rate <= 0:
            raise RuntimeError("WAV contains no playable audio frames.")

    print(f"PASS: generated {OUTPUT.resolve()}")
    print(f"Audio: {duration:.2f}s, {rate} Hz, {channels} channel(s)")
    print("Inference ran locally in this Python process.")


if __name__ == "__main__":
    asyncio.run(main())
