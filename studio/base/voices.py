"""Voice profile store (persistent). Sample audio + metadata JSON; export/import for backup."""
import json
import os
import shutil
import zipfile
from pathlib import Path

from . import config

ROOT = Path(os.getenv("VOICE_PROFILE_DB_PATH", str(config.DATA_DIR / "voices")))
ROOT.mkdir(parents=True, exist_ok=True)


def _safe(n):
    return "".join(c for c in n if c.isalnum() or c in "-_")[:40]


def add(name, sample_bytes, ext="ogg", meta=None):
    n = _safe(name)
    if not n:
        raise ValueError("name မမှန်ပါ")
    d = ROOT / n
    d.mkdir(exist_ok=True)
    s = d / f"sample.{ext}"
    s.write_bytes(sample_bytes)
    (d / "profile.json").write_text(json.dumps(dict(name=n, sample_path=str(s), **(meta or {})), ensure_ascii=False), "utf-8")
    try:  # also push to R2 so GitHub Actions workers can read it
        from .publish import r2_upload
        r2_upload(s, f"voices/{n}/sample.{ext}")
    except Exception:
        pass
    return n


def listing():
    return [json.loads(p.read_text("utf-8")) for p in sorted(ROOT.glob("*/profile.json"))]


def get_profile(name):
    p = ROOT / _safe(name) / "profile.json"
    if p.exists():
        return json.loads(p.read_text("utf-8"))
    raise RuntimeError(f"voice profile '{name}' မတွေ့ပါ")


def delete(name):
    d = ROOT / _safe(name)
    if not d.exists():
        raise RuntimeError("မတွေ့ပါ")
    shutil.rmtree(d)


def export_zip(dst):
    with zipfile.ZipFile(dst, "w") as z:
        for f in ROOT.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(ROOT))
    return dst


def import_zip(src):
    with zipfile.ZipFile(src) as z:
        z.extractall(ROOT)
