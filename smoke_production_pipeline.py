"""Real Edge TTS + SRT + FFmpeg MP4 smoke test for a disposable Burmese sample."""
from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image, ImageDraw

from tts_builder import synthesize_burmese_speech_with_srt
from video_renderer import render_slideshow

OUTPUT = Path("production-smoke-artifacts")
SAMPLE_TEXT = "မင်္ဂလာပါ။ ဒါက NEXORA အသံ၊ စာတန်းထိုးနဲ့ ဗီဒီယို ထုတ်လုပ်မှု စမ်းသပ်ချက် ဖြစ်ပါတယ်။"


async def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    audio, srt = await synthesize_burmese_speech_with_srt(SAMPLE_TEXT, "narrator")
    mp3_path = OUTPUT / "nexora-smoke.mp3"
    srt_path = OUTPUT / "nexora-smoke.srt"
    mp3_path.write_bytes(audio)
    srt_path.write_text(srt, encoding="utf-8-sig")

    image_path = OUTPUT / "nexora-smoke.png"
    image = Image.new("RGB", (1280, 720), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 1240, 680), outline="black", width=4)
    draw.text((90, 100), "NEXORA PRODUCTION SMOKE TEST", fill="black")
    draw.text((90, 180), "Synthetic test card — not movie footage", fill="black")
    image.save(image_path)

    mp4_path = OUTPUT / "nexora-smoke.mp4"
    render_slideshow(
        [(image_path.name, image_path.read_bytes())],
        (mp3_path.name, mp3_path.read_bytes()),
        mp4_path,
        platform="youtube",
        subtitle=(srt_path.name, srt_path.read_bytes()),
    )
    for artifact in (mp3_path, srt_path, mp4_path):
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            raise RuntimeError(f"Missing or empty artifact: {artifact.name}")
        print(f"PASS {artifact.name}: {artifact.stat().st_size} bytes")
    print("PASS real Edge TTS + word-aligned SRT + FFmpeg MP4 pipeline")


if __name__ == "__main__":
    asyncio.run(main())
