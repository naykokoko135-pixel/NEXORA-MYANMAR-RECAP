"""Download and make a short preview from an explicitly reusable Commons video."""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

MAX_SOURCE_BYTES = 80 * 1024 * 1024
MAX_PREVIEW_SECONDS = 45
ALLOWED_HOST = "upload.wikimedia.org"


class LicensedClipError(ValueError):
    """Raised when a reusable video cannot safely be processed."""


def choose_matching_source(query: str, sources: list[dict]) -> dict | None:
    """Choose only a strongly title-matching Commons file; never guess from weak matches."""
    terms = {x for x in re.findall(r"[a-z0-9]+", query.lower()) if len(x) > 2}
    if not terms:
        return None
    ranked = []
    for source in sources:
        title = str(source.get("title", "")).lower().replace("_", " ")
        title_terms = set(re.findall(r"[a-z0-9]+", title))
        score = len(terms & title_terms) / len(terms)
        if score >= 0.75:
            ranked.append((score, source))
    return max(ranked, key=lambda item: item[0])[1] if ranked else None


def render_licensed_preview(source: dict, output_path: str | Path, platform: str = "youtube") -> Path:
    """Fetch only Commons upload-host media and render a short, attributed preview."""
    from urllib.request import Request, HTTPRedirectHandler, build_opener
    import imageio_ffmpeg

    license_name = str(source.get("license", "")).lower()
    if not any(x in license_name for x in ("cc0", "cc by", "cc by-sa", "public domain")):
        raise LicensedClipError("လိုင်စင်အမျိုးအစားကို အတည်မပြုနိုင်ပါ။")
    url = str(source.get("url", ""))
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or parsed.username or parsed.password:
        raise LicensedClipError("ခွင့်ပြုထားသော Wikimedia upload ရင်းမြစ်မဟုတ်ပါ။")
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
            data = response.read(MAX_SOURCE_BYTES + 1)
    except LicensedClipError:
        raise
    except Exception as exc:
        raise LicensedClipError("Commons Video ကို ဒေါင်းလုဒ်မလုပ်နိုင်ပါ။") from exc
    if not data or len(data) > MAX_SOURCE_BYTES:
        raise LicensedClipError("Video ဖိုင်သည် ဗလာဖြစ်နေခြင်း သို့မဟုတ် 80 MB ထက်ကြီးနေပါတယ်။")

    dimensions = {"youtube": (1280, 720), "facebook": (864, 1080), "tiktok": (720, 1280)}
    if platform not in dimensions:
        raise LicensedClipError("Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမယ်။")
    width, height = dimensions[platform]
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    suffix = ".webm" if str(source.get("mime", "")).lower() == "video/webm" else ".mp4"
    with tempfile.TemporaryDirectory(prefix="nexora_licensed_") as temp:
        input_path = Path(temp) / ("source" + suffix)
        input_path.write_bytes(data)
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(input_path), "-t", str(MAX_PREVIEW_SECONDS),
            "-map", "0:v:0", "-map", "0:a?", "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p",
            "-r", "25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(target),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
        except subprocess.TimeoutExpired as exc:
            raise LicensedClipError("Video ပြင်ဆင်ချိန် ၃ မိနစ်ကျော်သွားပါတယ်။") from exc
        if result.returncode or not target.exists() or not target.stat().st_size:
            raise LicensedClipError("Commons Video ကို MP4 ပြောင်းမရပါ။")
    return target
