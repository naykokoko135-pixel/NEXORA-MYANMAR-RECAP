"""Create a short narrated preview from a reusable Wikimedia Commons video.

The narration is creator-supplied and generated with the project's Burmese TTS.
The source video's original audio is deliberately discarded.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from licensed_video_pipeline import ALLOWED_HOST, MAX_SOURCE_BYTES, LicensedClipError


def render_licensed_narrated_preview(
    source: dict,
    narration_mp3: bytes,
    subtitles_srt: str,
    output_path: str | Path,
    platform: str = "youtube",
) -> Path:
    """Render up to 90 seconds of licensed footage with Burmese narration and SRT."""
    from urllib.request import Request, HTTPRedirectHandler, build_opener
    import imageio_ffmpeg

    license_name = str(source.get("license", "")).strip()
    if not re.match(
        r"^(?:CC0(?:\\s|$)|CC BY(?:-SA)?(?:\\s|$)|Public domain$)",
        license_name,
        re.IGNORECASE,
    ):
        raise LicensedClipError("လိုင်စင်အမျိုးအစားကို အတည်မပြုနိုင်ပါ။")
    url = str(source.get("url", ""))
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or parsed.username or parsed.password:
        raise LicensedClipError("ခွင့်ပြုထားသော Wikimedia upload ရင်းမြစ်မဟုတ်ပါ။")
    if not narration_mp3 or len(narration_mp3) > 20 * 1024 * 1024:
        raise LicensedClipError("Narration MP3 သည် ဗလာဖြစ်နေခြင်း သို့မဟုတ် 20 MB ထက်ကြီးနေပါတယ်။")
    if not isinstance(subtitles_srt, str) or not subtitles_srt.strip() or "-->" not in subtitles_srt:
        raise LicensedClipError("မြန်မာ SRT စာတန်းပုံစံ မမှန်ပါ။")
    srt_data = subtitles_srt.encode("utf-8")
    if len(srt_data) > 1024 * 1024:
        raise LicensedClipError("SRT ဖိုင်သည် 1 MB ထက်ကြီးနေပါတယ်။")

    dimensions = {"youtube": (1280, 720), "facebook": (864, 1080), "tiktok": (720, 1280)}
    if platform not in dimensions:
        raise LicensedClipError("Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမယ်။")
    width, height = dimensions[platform]

    class CommonsRedirectHandler(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            redirected = urlparse(newurl)
            if redirected.scheme != "https" or redirected.hostname != ALLOWED_HOST:
                raise LicensedClipError("ခွင့်မပြုထားသော Redirect ကို ပိတ်လိုက်ပါတယ်။")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    try:
        request = Request(url, headers={"User-Agent": "NEXORA-Myanmar-Recap/1.0"})
        opener = build_opener(CommonsRedirectHandler)
        with opener.open(request, timeout=25) as response:
            source_data = response.read(MAX_SOURCE_BYTES + 1)
    except LicensedClipError:
        raise
    except Exception as exc:
        raise LicensedClipError("Commons Video ကို ဒေါင်းလုဒ်မလုပ်နိုင်ပါ။") from exc
    if not source_data or len(source_data) > MAX_SOURCE_BYTES:
        raise LicensedClipError("Video ဖိုင်သည် ဗလာဖြစ်နေခြင်း သို့မဟုတ် 80 MB ထက်ကြီးနေပါတယ်။")

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    suffix = ".webm" if str(source.get("mime", "")).lower() == "video/webm" else ".mp4"
    with tempfile.TemporaryDirectory(prefix="nexora_narrated_") as temp:
        work = Path(temp)
        video_path = work / ("source" + suffix)
        audio_path = work / "narration.mp3"
        srt_path = work / "captions.srt"
        video_path.write_bytes(source_data)
        audio_path.write_bytes(narration_mp3)
        srt_path.write_bytes(srt_data)
        # Loop the visual source to narration length, but never retain its original soundtrack.
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1", "-i", str(video_path),
            "-i", str(audio_path), "-i", str(srt_path),
            "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0",
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p",
            "-r", "25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
            "-c:a", "aac", "-b:a", "128k", "-c:s", "mov_text",
            "-metadata:s:s:0", "language=bur", "-t", "90", "-shortest",
            "-movflags", "+faststart", str(target),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
        except subprocess.TimeoutExpired as exc:
            raise LicensedClipError("Video ပြင်ဆင်ချိန် ၄ မိနစ်ကျော်သွားပါတယ်။") from exc
        if result.returncode or not target.exists() or not target.stat().st_size:
            raise LicensedClipError("Narration ပါသော MP4 ကို မထုတ်နိုင်ပါ။")
    return target
