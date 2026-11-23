"""Download and render exact-title Internet Archive CC0/Public Domain Mark movie files.

Internet Archive rights metadata is uploader-supplied, not a legal warranty.
Only exact-title records marked CC0 or Public Domain Mark are eligible here.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from recap_partitioner import render_three_part_longform
from source_video_renderer import render_user_source_video

MAX_DOWNLOAD_BYTES = 1024 * 1024 * 1024
ALLOWED_LICENSE_URIS = {
    "https://creativecommons.org/publicdomain/mark/1.0/",
    "http://creativecommons.org/publicdomain/mark/1.0/",
    "https://creativecommons.org/publicdomain/zero/1.0/",
    "http://creativecommons.org/publicdomain/zero/1.0/",
}
ALLOWED_SUFFIXES = {".mp4", ".m4v", ".mov", ".webm"}


class InternetArchiveRenderError(ValueError):
    """Raised when an Internet Archive movie cannot be safely rendered."""


def download_internet_archive_source(source: dict, output_dir: str | Path) -> Path:
    """Download a source file from archive.org after strict metadata/host checks."""
    if not isinstance(source, dict) or source.get("license_uri") not in ALLOWED_LICENSE_URIS:
        raise InternetArchiveRenderError("CC0/Public Domain Mark လိုင်စင်ကို အတည်မပြုနိုင်ပါ။")
    identifier = str(source.get("identifier") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,100}", identifier):
        raise InternetArchiveRenderError("Internet Archive Identifier မမှန်ပါ။")
    files = source.get("files") or []
    if not files:
        raise InternetArchiveRenderError("ဒေါင်းလုဒ်လုပ်နိုင်သော Original Video ဖိုင် မတွေ့ပါ။")
    file_info = next(
        (entry for entry in files if Path(str(entry.get("name") or "")).suffix.lower() in ALLOWED_SUFFIXES),
        None,
    )
    if not file_info:
        raise InternetArchiveRenderError("MP4/MOV/M4V/WEBM Original Video မရှိပါ။")
    filename = str(file_info.get("name") or "")
    if not filename or filename in {".", ".."} or "/" in filename or "\\\\" in filename:
        raise InternetArchiveRenderError("Internet Archive ဖိုင်အမည် မလုံခြုံပါ။")
    try:
        declared_size = int(file_info.get("size") or 0)
    except (TypeError, ValueError):
        declared_size = 0
    if declared_size <= 0 or declared_size > MAX_DOWNLOAD_BYTES:
        raise InternetArchiveRenderError("Movie ဖိုင်အရွယ်အစားသည် 1 GB ကန့်သတ်ချက်နှင့် မကိုက်ညီပါ။")

    url = f"https://archive.org/download/{quote(identifier, safe='')}/{quote(filename, safe='')}"
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / ("archive_movie" + Path(filename).suffix.lower())
    temporary = target.with_suffix(target.suffix + ".part")

    class SafeArchiveRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            parsed = urlparse(newurl)
            if parsed.scheme != "https" or not (
                parsed.hostname == "archive.org"
                or (parsed.hostname or "").endswith(".archive.org")
            ):
                raise InternetArchiveRenderError("ခွင့်မပြုထားသော Archive Download Redirect ကို ပိတ်ထားပါတယ်။")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    request = Request(url, headers={"User-Agent": "NEXORA-Myanmar-Recap/1.0 (public-domain video rendering)"})
    total = 0
    try:
        with build_opener(SafeArchiveRedirect).open(request, timeout=45) as response:
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if not (content_type.startswith("video/") or content_type in {"application/octet-stream", "binary/octet-stream"}):
                raise InternetArchiveRenderError("Internet Archive က Video Content-Type မပေးပါ။")
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_DOWNLOAD_BYTES:
                raise InternetArchiveRenderError("Movie ဖိုင်သည် 1 GB ထက်ကြီးနေပါတယ်။")
            with temporary.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise InternetArchiveRenderError("Movie ဖိုင်သည် 1 GB ထက်ကြီးနေပါတယ်။")
                    output.write(chunk)
        if total <= 0:
            raise InternetArchiveRenderError("Movie ဖိုင် Download မအောင်မြင်ပါ။")
        temporary.replace(target)
    except InternetArchiveRenderError:
        temporary.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise InternetArchiveRenderError("Internet Archive Movie ကို Download မလုပ်နိုင်ပါ။") from exc
    return target


def render_internet_archive_longform_parts(
    source: dict,
    narration_audio: tuple[str, bytes],
    subtitles_srt: tuple[str, bytes],
    output_dir: str | Path,
    platform: str,
) -> list[Path]:
    """Download a CC0/PD movie and render three non-overlapping 15-20 minute MP4 parts."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexora_archive_movie_") as temp:
        movie = download_internet_archive_source(source, temp)
        return render_three_part_longform(
            movie, narration_audio, subtitles_srt, target_dir, platform
        )


def render_internet_archive_narrated_preview(
    source: dict,
    audio: tuple[str, bytes],
    srt_text: str,
    output_path: str | Path,
    platform: str,
    max_duration_seconds: int = 420,
) -> Path:
    """Render an exact-title CC0/PD movie with supplied narration and timed SRT."""
    import re
    if not isinstance(srt_text, str) or not srt_text.strip():
        raise InternetArchiveRenderError("အချိန်ကိုက် SRT မရှိပါ။")
    matches = re.findall(r"-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})", srt_text)
    if not matches:
        raise InternetArchiveRenderError("SRT Timestamp မမှန်ပါ။")
    h, m, s, ms = matches[-1]
    duration = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    if not 1 <= duration <= min(420, int(max_duration_seconds)):
        raise InternetArchiveRenderError("TikTok Preview သည် ၇ မိနစ်အောက် ဖြစ်ရပါမယ်။")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexora_archive_preview_") as temp:
        movie = download_internet_archive_source(source, temp)
        return render_user_source_video(
            movie,
            audio,
            ("captions.srt", srt_text.encode("utf-8-sig")),
            target,
            platform,
            expected_duration_seconds=duration,
        )
