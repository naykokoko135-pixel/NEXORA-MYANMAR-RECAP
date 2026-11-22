"""Download and make a short preview from an explicitly reusable Commons video."""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

MAX_SOURCE_BYTES = 1024 * 1024 * 1024
MAX_PREVIEW_SOURCE_BYTES = 80 * 1024 * 1024
MAX_PREVIEW_SECONDS = 45
ALLOWED_HOST = "upload.wikimedia.org"


class LicensedClipError(ValueError):
    """Raised when a reusable video cannot safely be processed."""


def choose_matching_source(query: str, sources: list[dict], alternate_titles: list[str] | None = None) -> dict | None:
    """Choose only a strong match to the requested title or a verified title alias."""
    title_queries = [query, *(alternate_titles or [])]
    query_terms = []
    for value in title_queries:
        terms = {x for x in re.findall(r"[a-z0-9]+", str(value).lower()) if len(x) > 2}
        # Ignore short/ambiguous aliases rather than letting them admit unrelated files.
        if len(terms) >= 2 and terms not in query_terms:
            query_terms.append(terms)
    if not query_terms:
        return None
    ranked = []
    for source in sources:
        title = str(source.get("title", "")).lower().replace("_", " ")
        title_terms = set(re.findall(r"[a-z0-9]+", title))
        score = max(len(terms & title_terms) / len(terms) for terms in query_terms)
        if score >= 0.75:
            ranked.append((score, source))
    return max(ranked, key=lambda item: item[0])[1] if ranked else None


def render_licensed_preview(source: dict, output_path: str | Path, platform: str = "youtube") -> Path:
    """Fetch only Commons upload-host media and render a short, attributed preview."""
    from urllib.request import Request, HTTPRedirectHandler, build_opener
    import imageio_ffmpeg

    license_name = str(source.get("license", "")).strip()
    if not re.match(r"^(?:CC0(?:\s|$)|CC BY(?:-SA)?(?:\s|$)|Public domain$)", license_name, re.IGNORECASE):
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
            data = response.read(MAX_PREVIEW_SOURCE_BYTES + 1)
    except LicensedClipError:
        raise
    except Exception as exc:
        raise LicensedClipError("Commons Video ကို ဒေါင်းလုဒ်မလုပ်နိုင်ပါ။") from exc
    if not data or len(data) > MAX_PREVIEW_SOURCE_BYTES:
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


def download_licensed_source(source: dict, output_path: str | Path, max_bytes: int = MAX_SOURCE_BYTES) -> Path:
    """Stream an allowlisted Commons video directly to server disk (never through Telegram)."""
    from urllib.request import Request, HTTPRedirectHandler, build_opener

    license_name = str(source.get("license", "")).strip()
    if not re.match(r"^(?:CC0(?:\s|$)|CC BY(?:-SA)?(?:\s|$)|Public domain$)", license_name, re.IGNORECASE):
        raise LicensedClipError("လိုင်စင်ကို အတည်မပြုနိုင်သောကြောင့် Download ပိတ်ထားပါတယ်။")
    parsed = urlparse(str(source.get("url", "")))
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or parsed.username or parsed.password:
        raise LicensedClipError("Wikimedia Commons တရားဝင် upload host မဟုတ်ပါ။")
    if not isinstance(max_bytes, int) or max_bytes < 1 or max_bytes > MAX_SOURCE_BYTES:
        raise LicensedClipError("Download အရွယ်အစားကန့်သတ်ချက် မမှန်ပါ။")
    declared_size = int(source.get("size", 0) or 0)
    if declared_size > max_bytes:
        raise LicensedClipError("Commons Video သည် Server Download ကန့်သတ်ချက်ထက် ကြီးနေပါတယ်။")

    class SafeRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            target = urlparse(newurl)
            if target.scheme != "https" or target.hostname != ALLOWED_HOST or target.username or target.password:
                raise LicensedClipError("ခွင့်မပြုထားသော Download Redirect ကို ပိတ်ထားပါတယ်။")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    request = Request(str(source["url"]), headers={"User-Agent": "NEXORA-Myanmar-Recap/1.0 (licensed download)"})
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_suffix(target_path.suffix + ".part")
    try:
        with build_opener(SafeRedirect).open(request, timeout=30) as response:
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if not content_type.startswith("video/"):
                raise LicensedClipError("Server က Video Content-Type မပေးပါ။")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise LicensedClipError("Video သည် Server Download ကန့်သတ်ချက်ထက် ကြီးနေပါတယ်။")
            total = 0
            with temporary_path.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise LicensedClipError("Video သည် Server Download ကန့်သတ်ချက်ထက် ကြီးနေပါတယ်။")
                    output.write(chunk)
        if total <= 0:
            raise LicensedClipError("Download Video ဖိုင်သည် ဗလာဖြစ်နေပါတယ်။")
        temporary_path.replace(target_path)
    except LicensedClipError:
        temporary_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        raise LicensedClipError("ခွင့်ပြုထားသော Commons Video ကို Download မလုပ်နိုင်ပါ။") from exc
    return target_path
