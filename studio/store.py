"""Data access for projects, files, jobs, alerts and daily picks (SQLite, see db.py)."""
import json
import os
import shutil
import time
from pathlib import Path

from . import core, db, settings

INTERNAL_KINDS = {"cues"}
FILE_KINDS = {"source", "script", "script_txt", "audio_mp3", "audio_wav", "srt_en", "srt_my", "scenes", "video", "metadata", "qc", "credits", "cues"}
PROJECT_STATUSES = {"draft", "queued", "running", "paused", "failed", "completed", "ready_to_publish", "published", "cancelled"}
TERMINAL_JOB = ("done", "failed", "cancelled")


# =============================================================== alerts
def raise_alert(code: str, level: str, msg: str):
    a = db.kv_get("alerts", {}) or {}
    first = code not in a or a[code].get("msg") != msg
    a[code] = {"level": level, "code": code, "msg": msg[:300], "ts": time.time()}
    db.kv_set("alerts", a)
    if first:
        core.syslog("error" if level == "error" else "warn", f"ALERT {code}: {msg}")
    return first


def clear_alert(code: str):
    a = db.kv_get("alerts", {}) or {}
    if code in a:
        del a[code]
        db.kv_set("alerts", a)


def alerts() -> list[dict]:
    return sorted((db.kv_get("alerts", {}) or {}).values(), key=lambda x: -x["ts"])


# =============================================================== files
def file_to_api(r: dict) -> dict:
    return {"id": r["id"], "project_id": r["project_id"], "kind": r["kind"], "name": Path(r["path"]).name if r["path"] else r["kind"],
            "size": r["size"], "duration": r["duration"], "created": r["created"], "download_url": f"/api/files/{r['id']}/download"}


def save_file(project_id: int, kind: str, path, duration: float | None = None) -> dict:
    p = Path(path)
    size = p.stat().st_size if p.exists() else 0
    with db.tx() as c:
        c.execute("""INSERT INTO project_files(project_id,kind,path,size,duration,created) VALUES(?,?,?,?,?,?)
                     ON CONFLICT(project_id,kind) DO UPDATE SET path=excluded.path,size=excluded.size,duration=excluded.duration,created=excluded.created""",
                  (project_id, kind, str(p), size, duration, time.time()))
    return get_file_by_kind(project_id, kind)


def get_file_by_kind(project_id: int, kind: str) -> dict | None:
    return db.one("SELECT * FROM project_files WHERE project_id=? AND kind=?", (project_id, kind))


def get_file(file_id: int) -> dict | None:
    return db.one("SELECT * FROM project_files WHERE id=?", (file_id,))


def list_files(project_id: int, include_internal=False) -> list[dict]:
    rows = db.query("SELECT * FROM project_files WHERE project_id=? ORDER BY id", (project_id,))
    return [file_to_api(r) for r in rows if include_internal or r["kind"] not in INTERNAL_KINDS]


def file_path(project_id: int, kind: str) -> Path | None:
    r = get_file_by_kind(project_id, kind)
    if r and r["path"] and Path(r["path"]).exists():
        return Path(r["path"])
    return None


def read_json_file(project_id: int, kind: str, default=None):
    p = file_path(project_id, kind)
    if not p:
        return default
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return default


def write_json_file(project_id: int, kind: str, filename: str, data, duration=None) -> dict:
    p = project_path(project_id) / filename
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, p)
    return save_file(project_id, kind, p, duration)


def delete_file_row(file_id: int) -> bool:
    r = get_file(file_id)
    if not r:
        return False
    p = Path(r["path"]) if r["path"] else None
    if p and core.is_within(p, core.PROJECTS_DIR):
        p.unlink(missing_ok=True)
    with db.tx() as c:
        c.execute("DELETE FROM project_files WHERE id=?", (file_id,))
    return True


def invalidate_kinds(project_id: int, kinds):
    """Drop generated outputs (rows and files) so downstream stages must recompute them."""
    for k in kinds:
        r = get_file_by_kind(project_id, k)
        if r:
            delete_file_row(r["id"])


# =============================================================== projects
def project_to_api(r: dict, files: list | None = None) -> dict:
    return {"id": r["id"], "platform": r["platform"], "date": r["date"], "title": r["title"], "category": r["category"], "year": r["year"],
            "country": r["country"], "status": r["status"], "stage": r["stage"] or None, "progress": round(r["progress"] or 0, 1),
            "origin": r["origin"], "config": json.loads(r["config_json"] or "{}"), "error": r["error"] or "",
            "created": r["created"], "updated": r["updated"], "files": files if files is not None else []}


def project_path(project_id: int) -> Path:
    r = db.one("SELECT platform,date FROM projects WHERE id=?", (project_id,))
    if not r:
        raise KeyError(project_id)
    return core.project_dir(r["platform"], r["date"], project_id)


def create_project(platform: str, title: str, *, category="", year=None, country="", origin="manual", config=None,
                   research=None, date=None) -> dict:
    if platform not in core.PLATFORMS:
        raise ValueError("Unknown platform")
    title = " ".join(str(title or "").split())
    if not (1 <= len(title) <= 200):
        raise ValueError("Title is required (max 200 characters)")
    if category and category not in core.CATEGORIES:
        raise ValueError("Unknown category")
    cfg = settings.validate_platform_config(platform, {**settings.platforms()[platform], **(config or {})})
    now = time.time()
    with db.tx() as c:
        cur = c.execute("""INSERT INTO projects(platform,date,title,category,year,country,status,config_json,research_json,origin,created,updated)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (platform, date or core.bkk_date(), title, category, year, country or "", "draft", json.dumps(cfg, ensure_ascii=False),
                         json.dumps(research, ensure_ascii=False) if research else "", origin, now, now))
        pid = cur.lastrowid
    return get_project(pid)


def get_row(project_id: int) -> dict | None:
    return db.one("SELECT * FROM projects WHERE id=?", (project_id,))


def get_project(project_id: int, with_files=True) -> dict | None:
    r = get_row(project_id)
    if not r:
        return None
    return project_to_api(r, list_files(project_id) if with_files else [])


def research_of(project_id: int) -> dict | None:
    r = get_row(project_id)
    if r and r["research_json"]:
        try:
            return json.loads(r["research_json"])
        except Exception:
            return None
    return None


def set_research(project_id: int, research: dict):
    meta = {k: research.get(k) for k in ("title", "category", "year", "country")}
    with db.tx() as c:
        c.execute("UPDATE projects SET research_json=?, category=COALESCE(NULLIF(?,''),category), year=COALESCE(?,year), country=COALESCE(NULLIF(?,''),country), updated=? WHERE id=?",
                  (json.dumps(research, ensure_ascii=False), meta["category"] or "", meta["year"], meta["country"] or "", time.time(), project_id))


def update_project(project_id: int, **fields):
    allowed = {"status", "stage", "progress", "error", "title", "category", "year", "country", "run", "config_json"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"cannot update {bad}")
    if "status" in fields and fields["status"] not in PROJECT_STATUSES:
        raise ValueError("bad status")
    sets = ", ".join(f"{k}=?" for k in fields)
    with db.tx() as c:
        c.execute(f"UPDATE projects SET {sets}, updated=? WHERE id=?", (*fields.values(), time.time(), project_id))


def set_config(project_id: int, patch: dict) -> dict:
    r = get_row(project_id)
    cfg = settings.validate_platform_config(r["platform"], {**json.loads(r["config_json"] or "{}"), **patch})
    update_project(project_id, config_json=json.dumps(cfg, ensure_ascii=False))
    return cfg


def list_projects(platform=None, date=None, status=None, limit=50) -> tuple[list[dict], int]:
    where, args = [], []
    for col, v in (("platform", platform), ("date", date), ("status", status)):
        if v:
            where.append(f"{col}=?")
            args.append(v)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.one(f"SELECT COUNT(*) n FROM projects{w}", args)["n"]
    rows = db.query(f"SELECT * FROM projects{w} ORDER BY created DESC, id DESC LIMIT ?", (*args, max(1, min(int(limit), 500))))
    by_proj: dict[int, list] = {}
    if rows:
        ids = [r["id"] for r in rows]
        q = ",".join("?" * len(ids))
        for f in db.query(f"SELECT * FROM project_files WHERE project_id IN ({q}) ORDER BY id", ids):
            if f["kind"] not in INTERNAL_KINDS:
                by_proj.setdefault(f["project_id"], []).append(file_to_api(f))
    return [project_to_api(r, by_proj.get(r["id"], [])) for r in rows], total


def delete_project(project_id: int) -> int:
    r = get_row(project_id)
    if not r:
        raise KeyError(project_id)
    n = db.one("SELECT COUNT(*) n FROM project_files WHERE project_id=?", (project_id,))["n"]
    d = core.PROJECTS_DIR / r["platform"] / r["date"] / str(project_id)
    if d.exists() and core.is_within(d, core.PROJECTS_DIR):
        shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(core.WORK_ROOT / str(project_id), ignore_errors=True)
    for a in db.query("SELECT local_path FROM source_assets WHERE project_id=?", (project_id,)):
        if a["local_path"] and core.is_within(Path(a["local_path"]), core.DATA_DIR):
            Path(a["local_path"]).unlink(missing_ok=True)
    with db.tx() as c:
        c.execute("DELETE FROM job_logs WHERE job_id IN (SELECT id FROM jobs WHERE project_id=?)", (project_id,))
        c.execute("DELETE FROM jobs WHERE project_id=?", (project_id,))
        c.execute("DELETE FROM projects WHERE id=?", (project_id,))  # files/assets cascade
    return n


# =============================================================== jobs
def job_to_api(r: dict) -> dict:
    return {"id": r["id"], "project_id": r["project_id"], "platform": r["platform"], "stage": r["stage"], "status": r["status"],
            "attempts": r["attempts"], "max_attempts": r["max_attempts"], "progress": round(r["progress"] or 0, 1), "step": r["step"],
            "error": r["error"], "trigger": r["trigger"], "created": r["created"], "started": r["started"], "finished": r["finished"],
            "not_before": r["not_before"], "executor": "local", **({"project_title": r["project_title"]} if "project_title" in r else {})}


def enqueue(project_id: int | None, platform: str, stage: str, *, trigger="manual", key: str | None = None, payload=None,
            not_before=0.0) -> tuple[dict, bool]:
    """Insert a job unless the idempotency key already exists. Returns (job_row, created)."""
    if project_id is not None:
        run = get_row(project_id)["run"]
        key = key or f"p{project_id}:r{run}:{stage}"
    if not key:
        raise ValueError("key required for project-less jobs")
    ma = settings.automation()["retry"]["max_attempts"]
    with db.tx() as c:
        cur = c.execute("""INSERT OR IGNORE INTO jobs(project_id,platform,stage,status,idem_key,max_attempts,not_before,payload_json,trigger,created)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (project_id, platform, stage, "queued", key, ma, not_before, json.dumps(payload or {}), trigger, time.time()))
        created = cur.rowcount == 1
    row = db.one("SELECT * FROM jobs WHERE idem_key=?", (key,))
    if created and project_id is not None:
        update_project(project_id, status="queued", stage=stage, error="")
    return row, created


def get_job(job_id: int) -> dict | None:
    return db.one("SELECT * FROM jobs WHERE id=?", (job_id,))


def job_with_title(job_id: int) -> dict | None:
    r = db.one("SELECT j.*, COALESCE(p.title,'') project_title FROM jobs j LEFT JOIN projects p ON p.id=j.project_id WHERE j.id=?", (job_id,))
    return job_to_api(r) if r else None


def list_jobs(status=None, platform=None, project_id=None, limit=50) -> list[dict]:
    where, args = [], []
    for col, v in (("j.status", status), ("j.platform", platform), ("j.project_id", project_id)):
        if v:
            where.append(f"{col}=?")
            args.append(v)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    rows = db.query(f"SELECT j.*, COALESCE(p.title,'') project_title FROM jobs j LEFT JOIN projects p ON p.id=j.project_id{w} ORDER BY j.id DESC LIMIT ?",
                    (*args, max(1, min(int(limit), 500))))
    return [job_to_api(r) for r in rows]


def job_counts() -> dict:
    out = {s: 0 for s in ("queued", "running", "failed", "done", "cancelled")}
    for r in db.query("SELECT status, COUNT(*) n FROM jobs GROUP BY status"):
        out[r["status"]] = r["n"]
    return out


def claim_next(platform: str, *, skip_auto: bool) -> dict | None:
    """Atomically claim the oldest runnable queued job for a platform lane."""
    now = time.time()
    extra = " AND j.trigger NOT IN ('auto','system')" if skip_auto else ""
    with db.tx() as c:
        row = c.execute(f"SELECT j.id FROM jobs j WHERE j.status='queued' AND j.platform=? AND j.not_before<=?{extra} ORDER BY j.id LIMIT 1",
                        (platform, now)).fetchone()
        if not row:
            return None
        cur = c.execute("UPDATE jobs SET status='running', started=?, finished=NULL, attempts=attempts+1, progress=0, step='starting' WHERE id=? AND status='queued'",
                        (now, row["id"]))
        if cur.rowcount != 1:
            return None
    return get_job(row["id"])


def set_job_progress(job_id: int, progress: float, step: str = ""):
    with db.tx() as c:
        c.execute("UPDATE jobs SET progress=?, step=COALESCE(NULLIF(?,''),step) WHERE id=? AND status='running'", (max(0, min(100, progress)), step, job_id))


def finish_job(job_id: int, status: str, error: str = ""):
    with db.tx() as c:
        c.execute("UPDATE jobs SET status=?, error=?, finished=?, progress=CASE WHEN ?='done' THEN 100 ELSE progress END WHERE id=?",
                  (status, error[:1500], time.time(), status, job_id))


def requeue_job(job_id: int, error: str, not_before: float):
    with db.tx() as c:
        c.execute("UPDATE jobs SET status='queued', error=?, not_before=?, started=NULL WHERE id=?", (error[:1500], not_before, job_id))


def reset_job_for_retry(job_id: int):
    with db.tx() as c:
        c.execute("UPDATE jobs SET status='queued', attempts=0, error='', not_before=0, started=NULL, finished=NULL, progress=0, trigger='retry' WHERE id=? AND status IN ('failed','cancelled')",
                  (job_id,))


def recover_running_jobs() -> int:
    """After a restart no worker owns 'running' jobs: put them back in the queue (stage code is idempotent)."""
    with db.tx() as c:
        cur = c.execute("UPDATE jobs SET status='queued', step='recovered after restart', not_before=0, attempts=MAX(attempts-1,0) WHERE status='running'")
        n = cur.rowcount
        c.execute("UPDATE projects SET status='queued' WHERE status='running'")
    return n


def cancel_queued(where_sql: str = "1=1", args=()) -> int:
    with db.tx() as c:
        cur = c.execute(f"UPDATE jobs SET status='cancelled', finished=?, error='cancelled' WHERE status='queued' AND ({where_sql})", (time.time(), *args))
        return cur.rowcount


def joblog(job_id: int | None, level: str, msg: str):
    if job_id is None:
        return
    with db.tx() as c:
        c.execute("INSERT INTO job_logs(job_id,ts,level,msg) VALUES(?,?,?,?)", (job_id, time.time(), level, str(msg)[:1500]))


def job_logs(job_id: int, limit=500) -> list[dict]:
    rows = db.query("SELECT ts,level,msg FROM job_logs WHERE job_id=? ORDER BY id DESC LIMIT ?", (job_id, limit))
    return list(reversed(rows))


def project_logs(project_id: int, limit=300) -> list[dict]:
    rows = db.query("""SELECT l.ts,l.level,l.msg,l.job_id,j.stage FROM job_logs l JOIN jobs j ON j.id=l.job_id
                       WHERE j.project_id=? ORDER BY l.id DESC LIMIT ?""", (project_id, limit))
    return list(reversed(rows))


def recent_errors(limit=10) -> list[dict]:
    rows = db.query("""SELECT j.finished ts, j.id job_id, j.project_id, j.stage, j.platform, j.error msg FROM jobs j
                       WHERE j.status='failed' AND j.error<>'' ORDER BY j.finished DESC LIMIT ?""", (limit,))
    return rows


# =============================================================== daily picks
def save_pick(date: str, platform: str, title: str, category: str, src: dict):
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO daily_picks(date,platform,title,category,src_json,created) VALUES(?,?,?,?,?,?)",
                  (date, platform, title, category, json.dumps({k: src.get(k) for k in ("year", "sources", "wiki_url", "country")}, ensure_ascii=False), time.time()))


def picks_for(date: str) -> list[dict]:
    out = []
    for r in db.query("SELECT * FROM daily_picks WHERE date=? ORDER BY platform", (date,)):
        meta = json.loads(r["src_json"] or "{}")
        pr = db.one("SELECT id FROM projects WHERE platform=? AND date=? AND origin='auto'", (r["platform"], date))
        out.append({"platform": r["platform"], "title": r["title"], "category": r["category"], "year": meta.get("year"),
                    "sources": meta.get("sources") or [], "project_id": pr["id"] if pr else None})
    order = {p: i for i, p in enumerate(core.PLATFORMS)}
    return sorted(out, key=lambda x: order.get(x["platform"], 9))


def titles_used_on(date: str) -> list[str]:
    return [r["title"] for r in db.query("SELECT title FROM projects WHERE date=?", (date,))]
