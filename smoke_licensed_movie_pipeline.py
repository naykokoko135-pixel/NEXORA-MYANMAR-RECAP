"""End-to-end MP4 smoke test using an actual reusable movie source from Wikimedia Commons.

Big Buck Bunny is a Blender Foundation open movie released under CC BY 3.0.
This test discovers the source by title, checks its reuse license, downloads a
short preview, creates Burmese narration + word-timed SRT, and renders a real
video-footage MP4 with the production source-video renderer.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from clip_source_finder import search_licensed_video
from licensed_video_pipeline import choose_matching_source, render_licensed_preview
from source_video_renderer import render_user_source_video
from tts_builder import synthesize_burmese_speech_with_srt

OUTPUT = Path("licensed-movie-smoke-artifacts")
TITLE = "Big Buck Bunny"
NARRATION = (
    "ဒီနေ့ စမ်းသပ်မယ့် ဇာတ်ကားက Big Buck Bunny ဖြစ်ပါတယ်။ "
    "ဒီဇာတ်လမ်းတိုမှာ ယုန်လေးတစ်ကောင်ရဲ့ အေးချမ်းတဲ့နေ့ကို "
    "အနှောင့်အယှက်ပေးလာတဲ့ ဖြစ်ရပ်တွေကို ဟာသဆန်ဆန် မြင်တွေ့ရမှာပါ။ "
    "NEXORA ရဲ့ မြန်မာအသံ၊ စာတန်းထိုးနဲ့ ဗီဒီယိုတည်းဖြတ်မှုကို "
    "တကယ့် ရုပ်ရှင် footage နဲ့ စမ်းသပ်ထားတာ ဖြစ်ပါတယ်။"
)


def subtitle_end_seconds(srt: str) -> float:
    matches = re.findall(r"-->\\s*(\\d{2}):(\\d{2}):(\\d{2}),(\\d{3})", srt)
    if not matches:
        raise RuntimeError("TTS did not return a valid timed SRT")
    h, m, sec, ms = matches[-1]
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


async def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    candidates = await asyncio.to_thread(search_licensed_video, TITLE, 8)
    source = choose_matching_source(TITLE, candidates, ["Big Buck Bunny 2008"])
    if not source:
        raise RuntimeError(
            "No exact-title Commons video with CC0/CC BY/CC BY-SA/Public Domain "
            "metadata was found; refusing unrelated footage."
        )

    # Keep an auditable rights/source record with the test artifacts.
    (OUTPUT / "source-attribution.json").write_text(
        json.dumps(
            {
                "requested_title": TITLE,
                "matched_file": source.get("title"),
                "source_page": source.get("source_page"),
                "license": source.get("license"),
                "artist": source.get("artist"),
                "attribution": source.get("attribution"),
                "notice": "Verify the uploader's rights and comply with the exact license before publication.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    preview = OUTPUT / "licensed-source-preview.mp4"
    await asyncio.to_thread(render_licensed_preview, source, preview, "youtube")

    audio, srt = await synthesize_burmese_speech_with_srt(NARRATION, "narrator")
    duration = subtitle_end_seconds(srt)
    if duration > 40:
        raise RuntimeError(f"Smoke narration too long for preview: {duration:.2f}s")

    audio_path = OUTPUT / "nexora-burmese-narration.mp3"
    srt_path = OUTPUT / "nexora-burmese-subtitles.srt"
    audio_path.write_bytes(audio)
    srt_path.write_text(srt, encoding="utf-8-sig")

    final_path = OUTPUT / "nexora-big-buck-bunny-recap-smoke.mp4"
    await asyncio.to_thread(
        render_user_source_video,
        preview,
        (audio_path.name, audio_path.read_bytes()),
        (srt_path.name, srt_path.read_bytes()),
        final_path,
        "youtube",
        0.0,
        True,
        duration,
        "cinematic",
        "voice",
        "pushin",
        None,
        0.18,
        True,
        None,
        "bottom-right",
        "cinematic",
        False,
        0.6,
        "720p",
    )

    import imageio_ffmpeg
    import subprocess

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(final_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    info = probe.stderr or probe.stdout
    if "Video:" not in info or "Audio:" not in info or "Subtitle:" not in info:
        raise RuntimeError("Final MP4 is missing a required video/audio/subtitle stream")
    for artifact in (preview, audio_path, srt_path, final_path):
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            raise RuntimeError(f"Missing or empty artifact: {artifact.name}")
        print(f"PASS {artifact.name}: {artifact.stat().st_size} bytes")
    print(f"PASS licensed source match: {source.get('title')} ({source.get('license')})")
    print(f"PASS real-footage MP4 + Burmese narration + timed SRT: {duration:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
