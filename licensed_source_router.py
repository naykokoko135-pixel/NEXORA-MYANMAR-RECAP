"""Route title-matched video downloads through reusable-license source providers.

Wikimedia Commons accepts CC0, CC BY, CC BY-SA and Public Domain metadata.
Internet Archive downloads are narrower: only CC0/Public Domain Mark records
are automatically downloadable because Archive rights metadata is uploader-supplied.
"""
from __future__ import annotations

from pathlib import Path


class LicensedSourceRouterError(ValueError):
    """Raised when no safe, exact-title source can be downloaded."""


def discover_and_download_licensed_source(query: str, output_dir: str | Path) -> tuple[Path, dict, str]:
    """Try exact-match Commons first, then CC0/Public Domain Mark Internet Archive."""
    from clip_source_finder import ClipSourceError, search_licensed_video
    from licensed_video_pipeline import (
        LicensedClipError,
        choose_matching_source,
        download_licensed_source,
    )

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    try:
        sources = search_licensed_video(query, 8)
        source = choose_matching_source(query, sources)
        if source:
            suffix = ".webm" if str(source.get("mime", "")).lower() == "video/webm" else ".mp4"
            target = target_dir / ("licensed_source" + suffix)
            path = download_licensed_source(source, target)
            return path, source, "Wikimedia Commons"
        failures.append("Commons: ခေါင်းစဉ်တိတိကျကျ ကိုက်ညီသော ခွင့်ပြုထားသည့် Video မတွေ့ပါ။")
    except (ClipSourceError, LicensedClipError) as exc:
        failures.append("Commons: " + str(exc))
    except Exception as exc:
        failures.append("Commons: " + type(exc).__name__)

    try:
        from internet_archive_video_finder import search_internet_archive_licensed_video
        from internet_archive_pipeline import (
            InternetArchiveRenderError,
            download_internet_archive_source,
        )

        archive_sources = search_internet_archive_licensed_video(query, 8)
        # The finder may discover CC BY/CC BY-SA records, but auto-download is
        # intentionally limited to CC0 and Public Domain Mark only.
        source = next((item for item in archive_sources if item.get("download_enabled")), None)
        if source:
            path = download_internet_archive_source(source, target_dir)
            return path, source, "Internet Archive (CC0/Public Domain Mark)"
        failures.append(
            "Internet Archive: CC0/Public Domain Mark အလိုအလျောက် Download လုပ်ခွင့်ရှိသော "
            "ခေါင်းစဉ်တူ Original Video မတွေ့ပါ။"
        )
    except Exception as exc:
        failures.append("Internet Archive: " + str(exc))

    raise LicensedSourceRouterError("\n".join(failures) or "ခွင့်ပြုထားသော ရင်းမြစ် မတွေ့ပါ။")
