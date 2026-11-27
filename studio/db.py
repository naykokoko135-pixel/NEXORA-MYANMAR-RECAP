"""SQLite persistence for the NEXORA studio: schema migrations + small helpers.

All state that must survive a restart (projects, jobs, logs, daily picks, automation state)
lives here. The DB path follows DATA_DIR, so on Render it is durable only when a persistent
disk is mounted (see render.paid.yaml); on the free plan it is ephemeral and the UI says so.
"""
import contextlib
import json
import sqlite3
import threading
import time
from pathlib import Path

from .. import config

DB_PATH = Path(config.DATA_DIR) / "studio.sqlite3"
_lock = threading.RLock()

MIGRATIONS = [
    # 1: core tables
    """
    CREATE TABLE projects(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL, date TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '',
        year INTEGER, country TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft',
        config_json TEXT NOT NULL DEFAULT '{}',
        research_json TEXT NOT NULL DEFAULT '',
        origin TEXT NOT NULL DEFAULT 'manual',
        created REAL NOT NULL, updated REAL NOT NULL
    );
    CREATE TABLE project_files(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        kind TEXT NOT NULL, path TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
        size INTEGER NOT NULL DEFAULT 0, duration REAL, created REAL NOT NULL,
        UNIQUE(project_id, kind)
    );
    CREATE TABLE jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        platform TEXT NOT NULL, stage TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',
        idem_key TEXT NOT NULL UNIQUE,
        attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
        not_before REAL NOT NULL DEFAULT 0,
        progress REAL NOT NULL DEFAULT 0, step TEXT NOT NULL DEFAULT '',
        error TEXT NOT NULL DEFAULT '', executor TEXT NOT NULL DEFAULT '', external_ref TEXT NOT NULL DEFAULT '',
        payload_json TEXT NOT NULL DEFAULT '{}',
        trigger TEXT NOT NULL DEFAULT 'manual',
        created REAL NOT NULL, started REAL, finished REAL
    );
    CREATE INDEX jobs_status ON jobs(platform, status);
    CREATE TABLE job_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        ts REAL NOT NULL, level TEXT NOT NULL, msg TEXT NOT NULL
    );
    CREATE INDEX job_logs_job ON job_logs(job_id);
    CREATE TABLE daily_picks(
        date TEXT NOT NULL, platform TEXT NOT NULL,
        title TEXT NOT NULL, category TEXT NOT NULL, src_json TEXT NOT NULL,
        created REAL NOT NULL, PRIMARY KEY(date, platform)
    );
    CREATE TABLE kv(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated REAL NOT NULL);
    CREATE TABLE audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, actor TEXT NOT NULL,
        action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
    """,
    # 2: legal visual sources
    """
    CREATE TABLE source_assets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        origin TEXT NOT NULL, title TEXT NOT NULL, page_url TEXT NOT NULL DEFAULT '',
        file_url TEXT NOT NULL DEFAULT '', local_path TEXT NOT NULL DEFAULT '',
        license TEXT NOT NULL DEFAULT '', license_url TEXT NOT NULL DEFAULT '',
        attribution TEXT NOT NULL DEFAULT '', attribution_required INTEGER NOT NULL DEFAULT 1,
        verified INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', created REAL NOT NULL
    );
    """,
    # 3: server-side sessions
    """
    CREATE TABLE sessions(
        sid TEXT PRIMARY KEY, role TEXT NOT NULL, csrf TEXT NOT NULL,
        created REAL NOT NULL, expires REAL NOT NULL, ip TEXT NOT NULL DEFAULT ''
    );
    """,
    # 4: pipeline progress columns, run counter (idempotent job keys), system log, daily-uniqueness guard
    """
    ALTER TABLE projects ADD COLUMN stage TEXT NOT NULL DEFAULT '';
    ALTER TABLE projects ADD COLUMN progress REAL NOT NULL DEFAULT 0;
    ALTER TABLE projects ADD COLUMN error TEXT NOT NULL DEFAULT '';
    ALTER TABLE projects ADD COLUMN run INTEGER NOT NULL DEFAULT 1;
    CREATE UNIQUE INDEX uniq_auto_project_per_day ON projects(platform, date) WHERE origin='auto';
    CREATE TABLE syslog(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, level TEXT NOT NULL,
        msg TEXT NOT NULL, project_id INTEGER, job_id INTEGER
    );
    CREATE INDEX syslog_ts ON syslog(ts);
    CREATE INDEX projects_pd ON projects(platform, date);
    """,
]


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=30000")
    return c


@contextlib.contextmanager
def tx():
    """Serialised write transaction (single process, many threads)."""
    with _lock:
        c = _connect()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()


def query(sql, args=()):
    with _lock:
        c = _connect()
        try:
            return [dict(r) for r in c.execute(sql, args).fetchall()]
        finally:
            c.close()


def one(sql, args=()):
    r = query(sql, args)
    return r[0] if r else None


def migrate():
    with tx() as c:
        c.execute("CREATE TABLE IF NOT EXISTS schema_version(v INTEGER NOT NULL)")
        row = c.execute("SELECT v FROM schema_version").fetchone()
        cur = row["v"] if row else 0
        if not row:
            c.execute("INSERT INTO schema_version VALUES(0)")
        for i, script in enumerate(MIGRATIONS, 1):
            if i > cur:
                c.executescript(script)
                c.execute("UPDATE schema_version SET v=?", (i,))
    return len(MIGRATIONS)


def schema_version():
    r = one("SELECT v FROM schema_version")
    return r["v"] if r else 0


# ---- key/value (automation state, schedule, provider prefs) ----
def kv_get(key, default=None):
    r = one("SELECT value FROM kv WHERE key=?", (key,))
    if not r:
        return default
    try:
        return json.loads(r["value"])
    except Exception:
        return default


def kv_set(key, value):
    with tx() as c:
        c.execute("INSERT INTO kv(key,value,updated) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
                  (key, json.dumps(value, ensure_ascii=False), time.time()))


def audit(actor, action, detail=""):
    with tx() as c:
        c.execute("INSERT INTO audit(ts,actor,action,detail) VALUES(?,?,?,?)", (time.time(), actor, action, str(detail)[:500]))
