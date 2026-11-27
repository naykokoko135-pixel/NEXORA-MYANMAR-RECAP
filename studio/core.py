"""Shared helpers: paths, time (Asia/Bangkok), structured logging, host resource detection.

Everything here is safe to import without side effects other than creating data directories.
"""
import datetime as dt
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from .base import config
from . import db

VERSION = "1.0.0"
TZ = ZoneInfo("Asia/Bangkok")
TZ_NAME = "Asia/Bangkok"
STARTED = time.time()

PLATFORMS = ("youtube", "facebook", "tiktok")
CATEGORIES = tuple(config.CATEGORIES)
STAGES = ("research", "script", "voice", "srt", "assets", "timeline", "render", "qc", "publish", "notify")

FORMATS = {"landscape_16_9": (16, 9), "vertical_9_16": (9, 16), "square_1_1": (1, 1), "portrait_4_5": (4, 5)}
RESOLUTIONS = {"720p": 720, "1080p": 1080, "1440p": 1440, "2160p": 2160}

# Mutable runtime paths. Tests and the acceptance harness call configure() to isolate state.
PROJECTS_DIR = Path(config.DATA_DIR) / "projects"
WORK_ROOT = Path(config.WORK_DIR) / "studio"
PREVIEW_DIR = Path(config.DATA_DIR) / "previews"
DATA_DIR = Path(config.DATA_DIR)

log = logging.getLogger("nexora.studio")


def configure(data_dir=None, work_dir=None):
    """Point the studio at a different data/work directory (used by tests and acceptance runs)."""
    global PROJECTS_DIR, WORK_ROOT, PREVIEW_DIR, DATA_DIR
    if data_dir is not None:
        DATA_DIR = Path(data_dir)
        db.DB_PATH = DATA_DIR / "studio.sqlite3"
        PROJECTS_DIR = DATA_DIR / "projects"
        PREVIEW_DIR = DATA_DIR / "previews"
    if work_dir is not None:
        WORK_ROOT = Path(work_dir)
    for d in (DATA_DIR, PROJECTS_DIR, PREVIEW_DIR, WORK_ROOT):
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- time
def now() -> float:
    return time.time()


def bkk_now() -> dt.datetime:
    return dt.datetime.now(TZ)


def bkk_date(ts: float | None = None) -> str:
    return (dt.datetime.fromtimestamp(ts, TZ) if ts else bkk_now()).strftime("%Y-%m-%d")


def parse_hhmm(text: str) -> tuple[int, int]:
    m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", str(text or "").strip())
    if not m:
        raise ValueError("Schedule must be HH:MM in 24-hour time (Asia/Bangkok)")
    return int(m.group(1)), int(m.group(2))


def next_run_after(hhmm: str, ref: dt.datetime | None = None) -> float:
    """Epoch seconds of the next daily occurrence of HH:MM in Bangkok time."""
    h, m = parse_hhmm(hhmm)
    ref = ref or bkk_now()
    cand = ref.replace(hour=h, minute=m, second=0, microsecond=0)
    if cand <= ref:
        cand += dt.timedelta(days=1)
    return cand.timestamp()


# ---------------------------------------------------------------- logging
class _JsonFormatter(logging.Formatter):
    def format(self, record):
        d = {"ts": round(record.created, 3), "level": record.levelname.lower(), "logger": record.name, "msg": record.getMessage()}
        for k in ("project_id", "job_id", "stage", "platform"):
            if hasattr(record, k):
                d[k] = getattr(record, k)
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info)[-1500:]
        return json.dumps(d, ensure_ascii=False)


def setup_logging():
    if getattr(setup_logging, "done", False):
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(_JsonFormatter())
    root = logging.getLogger("nexora.studio")
    root.handlers[:] = [h]
    root.setLevel(os.getenv("NEXORA_LOG_LEVEL", "INFO").upper())
    root.propagate = False
    setup_logging.done = True


def syslog(level: str, msg: str, project_id=None, job_id=None):
    """Persist an operational event (shown in Automation logs) and mirror it to the structured log."""
    msg = str(msg)[:1000]
    try:
        with db.tx() as c:
            c.execute("INSERT INTO syslog(ts,level,msg,project_id,job_id) VALUES(?,?,?,?,?)", (time.time(), level, msg, project_id, job_id))
            c.execute("DELETE FROM syslog WHERE id < (SELECT COALESCE(MAX(id),0)-5000 FROM syslog)")
    except Exception:  # logging must never break the caller
        pass
    getattr(log, {"warn": "warning"}.get(level, level) if level in ("info", "warn", "warning", "error", "debug") else "info")(
        msg, extra={k: v for k, v in (("project_id", project_id), ("job_id", job_id)) if v is not None})


# ---------------------------------------------------------------- filesystem
def project_dir(platform: str, date: str, project_id: int) -> Path:
    p = PROJECTS_DIR / platform / date / str(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def work_dir(project_id: int) -> Path:
    p = WORK_ROOT / str(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_within(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False


def dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def ffprobe_duration(path) -> float | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip()) if r.stdout.strip() else None
    except Exception:
        return None


# ---------------------------------------------------------------- host resources
def _mem_info() -> tuple[int | None, int | None]:
    """(total_mb, available_mb), honouring a container memory limit when one is set."""
    total = avail = None
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) // 1024
        total, avail = info.get("MemTotal"), info.get("MemAvailable")
    except Exception:
        pass
    for f in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = Path(f).read_text().strip()
            if raw.isdigit() and int(raw) < (1 << 50):
                limit = int(raw) // (1024 * 1024)
                if total is None or limit < total:
                    total = limit
                    if avail is not None:
                        avail = min(avail, limit)
                break
        except Exception:
            continue
    return total, avail


def gpu_info() -> dict:
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=8)
            if r.returncode == 0 and r.stdout.strip():
                return {"available": True, "note": r.stdout.strip().splitlines()[0][:120]}
        except Exception:
            pass
    return {"available": False, "note": "No local NVIDIA GPU detected. Video rendering uses CPU (libx264) and does not need a GPU; "
                                        "reference-voice synthesis needs a separate GPU worker (VOICE_GPU_URL)."}


def persistence() -> dict:
    forced = os.getenv("NEXORA_PERSISTENT_STORAGE", "").strip().lower()
    persistent = False
    note = ""
    try:
        d = DATA_DIR.resolve()
        if forced in ("1", "true", "yes"):
            persistent, note = True, "Marked persistent via NEXORA_PERSISTENT_STORAGE."
        elif forced in ("0", "false", "no"):
            persistent, note = False, "Marked ephemeral via NEXORA_PERSISTENT_STORAGE."
        elif str(d).startswith("/var/data"):
            persistent, note = True, "DATA_DIR is on /var/data (Render persistent disk mount)."
        else:
            persistent = DATA_DIR.stat().st_dev != Path("/").stat().st_dev
            note = "DATA_DIR is on a separate mounted volume." if persistent else ""
    except Exception:
        pass
    if not persistent and not note:
        note = ("DATA_DIR is on the instance's ephemeral filesystem: projects, the database and uploaded voice samples are lost on restart/redeploy. "
                "Attach a persistent disk (see render.studio.yaml) and set DATA_DIR to its mount path.")
    return {"persistent": persistent, "data_dir": str(DATA_DIR), "note": note}


def disk() -> dict:
    try:
        du = shutil.disk_usage(DATA_DIR)
        return {"free_gb": round(du.free / 1e9, 2), "total_gb": round(du.total / 1e9, 2)}
    except Exception:
        return {"free_gb": 0.0, "total_gb": 0.0}


def resolution_support(total_mb, cpus) -> list[dict]:
    needs = {"720p": (1024, 1), "1080p": (2048, 2), "1440p": (4096, 2), "2160p": (6144, 4)}
    out = []
    for rid, (mem, cpu) in needs.items():
        reason = None
        if total_mb is not None and total_mb < mem:
            reason = f"Needs ≥ {mem} MB RAM (this host has {total_mb} MB)."
        elif cpus < cpu:
            reason = f"Needs ≥ {cpu} CPU core(s) (this host has {cpus})."
        out.append({"id": rid, "supported": reason is None, "reason": reason})
    return out


def system_info() -> dict:
    total_mb, avail_mb = _mem_info()
    cpus = os.cpu_count() or 1
    ffmpeg = shutil.which("ffmpeg")
    ver = ""
    if ffmpeg:
        try:
            ver = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=8).stdout.splitlines()[0][:80]
        except Exception:
            ver = "unknown"
    dk = disk()
    try:
        min_free = float((db.kv_get("automation", {}) or {}).get("storage", {}).get("min_free_gb", 3))
    except Exception:  # DB not migrated yet
        min_free = 3.0
    reasons = []
    if not ffmpeg:
        reasons.append("ffmpeg is not installed on this host (use the Docker image / render.studio.yaml).")
    if not shutil.which("ffprobe"):
        reasons.append("ffprobe is not installed on this host.")
    if total_mb is not None and total_mb < 1024:
        reasons.append(f"Only {total_mb} MB RAM available; rendering needs ≥ 1024 MB (Render Free has 512 MB).")
    if dk["free_gb"] < min_free:
        reasons.append(f"Only {dk['free_gb']} GB free disk; at least {min_free} GB is required.")
    env_catalog = [
        ("NEXORA_ADMIN_PASSWORD", "Admin login for this website", "login"),
        ("NEXORA_VIEWER_PASSWORD", "Optional read-only login", "viewer role"),
        ("TELEGRAM_BOT_TOKEN", "Telegram bot", "bot, notifications"),
        ("TELEGRAM_CHAT_ID", "Chat that receives reports", "notifications"),
        ("OPENAI_API_KEY", "OpenAI script provider", "script generation"),
        ("GEMINI_API_KEY", "Gemini script provider", "script generation"),
        ("TMDB_API_READ_ACCESS_TOKEN", "TMDB catalogue (Cartoon / 3D / Movies trends); TMDB_API_KEY also works", "research"),
        ("VOICE_GPU_URL", "GPU voice worker (reference-conditioned synthesis)", "voice profiles"),
        ("VOICE_GPU_TOKEN", "GPU voice worker token", "voice profiles"),
        ("YT_CLIENT_ID", "YouTube OAuth client", "YouTube auto-publish"),
        ("YT_CLIENT_SECRET", "YouTube OAuth secret", "YouTube auto-publish"),
        ("YT_REFRESH_TOKEN", "YouTube OAuth refresh token", "YouTube auto-publish"),
        ("FB_PAGE_ID", "Facebook Page id", "Facebook auto-publish"),
        ("FB_PAGE_TOKEN", "Facebook Page token", "Facebook auto-publish"),
        ("AUTO_UPLOAD", "Set to 1 to allow auto-publish", "auto-publish"),
        ("DATA_DIR", "Persistent data directory", "persistence"),
        ("NEXORA_CRON_TOKEN", "Token for the external scheduler tick endpoint", "wake-up scheduling"),
        ("R2_BUCKET", "Cloudflare R2 bucket for large files", "large-file delivery"),
    ]
    return {
        "ffmpeg": {"ok": bool(ffmpeg), "version": ver}, "ffprobe": bool(shutil.which("ffprobe")),
        "cpu_count": cpus, "mem_total_mb": total_mb, "mem_free_mb": avail_mb, "disk": dk,
        "gpu": gpu_info(), "persistence": persistence(),
        "executor": {"can_render_local": not reasons, "reasons": reasons},
        "resolutions": resolution_support(total_mb, cpus),
        "env": [{"name": n, "present": bool(os.getenv(n)), "purpose": p, "required_for": r} for n, p, r in env_catalog],
        "timezone": TZ_NAME, "python": sys.version.split()[0], "version": VERSION,
    }


def resources_brief() -> dict:
    s = system_info()
    dk = s["disk"]
    return {"disk_free_gb": dk["free_gb"], "disk_total_gb": dk["total_gb"], "data_dir_gb": round(dir_size(DATA_DIR) / 1e9, 3),
            "mem_free_mb": s["mem_free_mb"], "cpu_count": s["cpu_count"], "ffmpeg": s["ffmpeg"]["ok"], "gpu": s["gpu"]["available"]}


def output_size(fmt: str, resolution: str) -> tuple[int, int]:
    """Frame size from aspect ratio and the short-side resolution (1080p vertical = 1080x1920)."""
    if fmt not in FORMATS or resolution not in RESOLUTIONS:
        raise ValueError("Unknown format or resolution")
    a, b = FORMATS[fmt]
    short = RESOLUTIONS[resolution]
    if a >= b:
        w, h = round(short * a / b), short
    else:
        w, h = short, round(short * b / a)
    return w - w % 2, h - h % 2
