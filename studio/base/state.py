import json
import re
from pathlib import Path
from .config import STATE_DIR


def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def _load(name, default):
    p = Path(STATE_DIR) / name
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return default


def _save(name, data):
    p = Path(STATE_DIR) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")


def used_titles() -> set:
    return {norm(x["title"]) for x in _load("used_titles.json", [])}


def mark_used(title, platform, date, category=""):
    d = _load("used_titles.json", [])
    d.append(dict(title=title, platform=platform, date=date, category=category))
    _save("used_titles.json", d)


def job_done(key) -> bool:
    return _load("jobs.json", {}).get(key, {}).get("status") == "done"


def mark_job(key, **info):
    d = _load("jobs.json", {})
    d[key] = info
    _save("jobs.json", d)


def save_daily(date, picks):
    _save(f"daily/{date}.json", picks)


def load_daily(date):
    return _load(f"daily/{date}.json", None)
