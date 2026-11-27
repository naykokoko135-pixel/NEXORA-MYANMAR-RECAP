"""Authentication, sessions, CSRF, rate limiting and upload validation for the studio API.

* Passwords come only from environment variables and are compared in constant time.
* Sessions are random 256-bit ids; only a SHA-256 hash is stored server-side. Cookie is HttpOnly + SameSite=Strict.
* Every state-changing request needs the per-session CSRF token (header ``X-CSRF-Token``).
"""
import collections
import hashlib
import hmac
import os
import secrets
import threading
import time

from . import db

SESSION_TTL = 12 * 3600
MIN_PASSWORD_LEN = 12
COOKIE = "nx_sid"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _digest(s: str) -> bytes:
    return hashlib.sha256(s.encode("utf-8")).digest()


def admin_password() -> str:
    p = os.getenv("NEXORA_ADMIN_PASSWORD", "")
    return p if len(p) >= MIN_PASSWORD_LEN else ""


def viewer_password() -> str:
    p = os.getenv("NEXORA_VIEWER_PASSWORD", "")
    return p if len(p) >= MIN_PASSWORD_LEN else ""


def configured() -> bool:
    return bool(admin_password())


def check_password(candidate: str) -> str | None:
    """Return the role for a correct password or None. Compares digests of equal length in constant time."""
    cand = _digest(str(candidate or ""))
    role = None
    a, v = admin_password(), viewer_password()
    if a and hmac.compare_digest(cand, _digest(a)):
        role = "admin"
    elif v and hmac.compare_digest(cand, _digest(v)):
        role = "viewer"
    return role


# ---------------------------------------------------------------- sessions
def _sid_hash(sid: str) -> str:
    return hashlib.sha256(sid.encode()).hexdigest()


def create_session(role: str, ip: str = "") -> tuple[str, str]:
    sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    now = time.time()
    with db.tx() as c:
        c.execute("DELETE FROM sessions WHERE expires < ?", (now,))
        c.execute("INSERT INTO sessions(sid,role,csrf,created,expires,ip) VALUES(?,?,?,?,?,?)",
                  (_sid_hash(sid), role, csrf, now, now + SESSION_TTL, ip[:64]))
    return sid, csrf


def get_session(sid: str | None) -> dict | None:
    if not sid or len(sid) > 200:
        return None
    r = db.one("SELECT role,csrf,expires FROM sessions WHERE sid=?", (_sid_hash(sid),))
    if not r or r["expires"] < time.time():
        return None
    return r


def destroy_session(sid: str | None):
    if sid:
        with db.tx() as c:
            c.execute("DELETE FROM sessions WHERE sid=?", (_sid_hash(sid),))


def csrf_ok(session: dict, token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(str(token), session["csrf"])


# ---------------------------------------------------------------- rate limiting
class RateLimiter:
    """Sliding-window limiter, in-process (the studio runs as a single process)."""

    def __init__(self):
        self._hits: dict[str, collections.deque] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: float) -> tuple[bool, int]:
        """Record a hit; return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, collections.deque())
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return False, max(1, int(q[0] + window - now) + 1)
            q.append(now)
            if len(self._hits) > 20000:  # bound memory
                for k in list(self._hits)[:5000]:
                    if not self._hits[k]:
                        del self._hits[k]
            return True, 0

    def count(self, key: str, window: float) -> int:
        now = time.monotonic()
        with self._lock:
            q = self._hits.get(key)
            if not q:
                return 0
            while q and q[0] <= now - window:
                q.popleft()
            return len(q)

    def reset(self, key: str):
        with self._lock:
            self._hits.pop(key, None)


limiter = RateLimiter()
LOGIN_FAILS, LOGIN_WINDOW = 5, 15 * 60


def login_blocked(ip: str) -> int:
    """Seconds until another login attempt is allowed (0 = allowed)."""
    if limiter.count("loginfail:" + ip, LOGIN_WINDOW) >= LOGIN_FAILS:
        with limiter._lock:
            q = limiter._hits.get("loginfail:" + ip)
            return max(1, int(q[0] + LOGIN_WINDOW - time.monotonic()) + 1) if q else 0
    return 0


def login_failed(ip: str):
    limiter.hit("loginfail:" + ip, 10 ** 6, LOGIN_WINDOW)


def login_succeeded(ip: str):
    limiter.reset("loginfail:" + ip)


# ---------------------------------------------------------------- upload validation
AUDIO_EXT = {"ogg": "ogg", "oga": "ogg", "opus": "ogg", "mp3": "mp3", "wav": "wav", "m4a": "m4a", "flac": "flac"}
IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif"}


def sniff_audio(head: bytes) -> str | None:
    if head[:4] == b"OggS":
        return "ogg"
    if head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "mp3"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[4:8] == b"ftyp":
        return "m4a"
    if head[:4] == b"fLaC":
        return "flac"
    return None


def sniff_image(head: bytes) -> str | None:
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:3] == b"\xff\xd8\xff":
        return "jpg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def safe_name(name: str, maxlen: int = 40) -> str:
    return "".join(c for c in str(name or "") if c.isalnum() or c in "-_")[:maxlen]
