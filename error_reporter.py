"""Send privacy-safe application error reports to GitHub Issues."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import traceback
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_REPO_DEFAULT = "naykokoko135-pixel/NEXORA-MYANMAR-RECAP"
_COOLDOWN_SECONDS = 600
_last_sent: dict[str, float] = {}
_lock = threading.Lock()


def _safe_frame_summary(exc: BaseException) -> str:
    """Return code locations only; never include exception messages or local values."""
    frames = traceback.extract_tb(exc.__traceback__)[-6:]
    if not frames:
        return "No traceback frames available."
    return "\n".join(
        f"- {frame.filename.rsplit('/', 1)[-1]}:{frame.lineno} in {frame.name}"
        for frame in frames
    )


def _claim_report(key: str) -> bool:
    now = time.monotonic()
    with _lock:
        previous = _last_sent.get(key)
        if previous is not None and now - previous < _COOLDOWN_SECONDS:
            return False
        _last_sent[key] = now
        # Bound memory if a process runs for a long time.
        for old_key, sent_at in list(_last_sent.items()):
            if now - sent_at >= _COOLDOWN_SECONDS:
                _last_sent.pop(old_key, None)
    return True


def report_error_to_github(exc: BaseException, *, update_kind: str = "telegram_update") -> bool:
    """Create a GitHub issue when configured. Returns False when disabled or failed."""
    token = os.getenv("GITHUB_ERROR_REPORT_TOKEN", "").strip()
    if not token:
        return False

    repository = os.getenv("GITHUB_REPOSITORY", _REPO_DEFAULT).strip()
    if not repository or "/" not in repository or any(part in repository for part in (" ", "\n", "\r")):
        return False

    error_type = type(exc).__name__
    frames = _safe_frame_summary(exc)
    fingerprint = hashlib.sha256(f"{error_type}:{frames}".encode("utf-8")).hexdigest()[:12]
    if not _claim_report(fingerprint):
        return False

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    title = f"[NEXORA Error] {error_type} ({fingerprint})"
    body = (
        "Automated privacy-safe error report from the NEXORA Telegram service.\n\n"
        f"- Time (UTC): {timestamp}\n"
        f"- Error type: `{error_type}`\n"
        f"- Handler: `{update_kind}`\n"
        f"- Fingerprint: `{fingerprint}`\n\n"
        "### Code locations\n"
        f"{frames}\n\n"
        "### Privacy\n"
        "This report intentionally excludes Telegram message text, user/chat IDs, "
        "exception messages, environment values, and request URLs.\n"
    )
    payload = json.dumps({"title": title, "body": body, "labels": ["bug"]}).encode("utf-8")
    request = Request(
        f"https://api.github.com/repos/{repository}/issues",
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "NEXORA-Error-Reporter",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            return 200 <= response.status < 300
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        # Never log response bodies or request headers; they may contain secrets.
        return False
