"""Persistent job engine: per-platform worker lanes, a planner (daily research), a scheduler and housekeeping.

* State lives in SQLite (db.py); after a restart ``recover_running_jobs`` re-queues interrupted work and the scheduler catches up.
* Lanes: youtube / facebook / tiktok each run their own queue (one job at a time per lane); the CPU-heavy render step is serialised
  across lanes by ``render_slot``. A fourth ``system`` lane runs the daily planner (research + choosing distinct titles).
* Auto jobs (trigger auto/system) only run while automation is ``running``; manual jobs always run.
"""
import datetime as dt
import json
import shutil
import subprocess
import tempfile
import threading
import time
import traceback
from pathlib import Path

from .base import research as research_mod, state as legacy_state
from . import core, db, notifier, pipeline, providers, settings, store
from .pipeline import Cancelled, Ctx, StageError

render_slot = threading.Lock()
LANES = ("youtube", "facebook", "tiktok")
POLL_S = 2.0
_cancel_lock = threading.Lock()
_cancel_jobs: set[int] = set()
_render_owner = {"job_id": None}


# ------------------------------------------------------------------------------------------------ cancellation + ffmpeg runner
def request_cancel(job_ids):
    with _cancel_lock:
        _cancel_jobs.update(job_ids)


def _is_cancelled(job_id):
    with _cancel_lock:
        return job_id in _cancel_jobs


def _clear_cancel(job_id):
    with _cancel_lock:
        _cancel_jobs.discard(job_id)


def cancellable_run(ctx):
    """ffmpeg runner that kills the process promptly when the job is cancelled. Returns (returncode, stderr tail)."""
    def run(cmd, cwd=None, line_cb=None):
        with tempfile.TemporaryFile("w+") as err, tempfile.TemporaryFile("w+") as out:
            p = subprocess.Popen(cmd, cwd=cwd, stdout=out, stderr=err, text=True)
            pos = 0
            while True:
                try:
                    rc = p.wait(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if _is_cancelled(ctx.job["id"]):
                    p.kill()
                    p.wait()
                    raise Cancelled()
                if line_cb:
                    out.seek(pos)
                    chunk = out.read()
                    pos = out.tell()
                    for line in chunk.splitlines():
                        line_cb(line)
            if line_cb:
                out.seek(pos)
                for line in out.read().splitlines():
                    line_cb(line)
            err.seek(0)
            return rc, err.read()[-2000:]
    return run


# ------------------------------------------------------------------------------------------------ engine
class Engine:
    def __init__(self):
        self.threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self.running = False

    # ---- lifecycle
    def start(self):
        if self.running:
            return
        db.migrate()
        core.configure()
        n = store.recover_running_jobs()
        if n:
            core.syslog("warn", f"Recovered {n} interrupted job(s) after restart")
        providers.install_script_hook()
        self._stop.clear()
        for lane in (*LANES, "system"):
            self._spawn(f"lane-{lane}", self._lane_loop, lane)
        self._spawn("scheduler", self._scheduler_loop)
        self.running = True
        core.syslog("info", f"Studio engine started ({len(self.threads)} threads); automation is {settings.automation()['state']}")

    def stop(self, timeout=5):
        self._stop.set()
        for t in self.threads:
            t.join(timeout)
        self.threads.clear()
        self.running = False

    def _spawn(self, name, fn, *args):
        t = threading.Thread(target=fn, args=args, name=name, daemon=True)
        t.start()
        self.threads.append(t)

    def status(self) -> dict:
        return {"running": self.running and any(t.is_alive() for t in self.threads), "threads": sum(1 for t in self.threads if t.is_alive())}

    # ---- lanes
    def _lane_loop(self, lane):
        while not self._stop.is_set():
            try:
                skip_auto = settings.automation()["state"] != "running"
                job = store.claim_next(lane, skip_auto=skip_auto)
            except Exception:
                core.log.exception("claim failed")
                self._stop.wait(5)
                continue
            if not job:
                self._stop.wait(POLL_S)
                continue
            try:
                self._execute(job)
            except Exception:  # never let a lane die
                core.log.exception("lane crashed while executing job")
                store.finish_job(job["id"], "failed", "internal error: " + traceback.format_exc()[-300:])

    def _execute(self, job):
        jid, pid, stage = job["id"], job["project_id"], job["stage"]
        _clear_cancel(jid) if job["status"] != "running" else None
        store.joblog(jid, "info", f"▶ {stage} (attempt {job['attempts']}/{job['max_attempts']}, trigger {job['trigger']})")
        guard = self._resource_guard(job)
        if guard:
            store.requeue_job(jid, guard, time.time() + 300)
            with db.tx() as c:
                c.execute("UPDATE jobs SET attempts=MAX(attempts-1,0) WHERE id=?", (jid,))
            store.joblog(jid, "warn", guard + " — waiting 5 min before trying again")
            return
        try:
            if job["platform"] == "system":
                self._plan_day(job)
            else:
                if not store.get_row(pid):
                    store.finish_job(jid, "cancelled", "project deleted")
                    return
                store.update_project(pid, status="running", stage=stage, error="")
                ctx = Ctx(job, pid, check_cancel=lambda: self._check(jid), render_slot=render_slot)
                pipeline.STAGE_FUNCS[stage](ctx)
            self._check(jid)
        except Cancelled:
            store.finish_job(jid, "cancelled", "cancelled by user")
            store.joblog(jid, "warn", "Cancelled")
            if pid:
                store.update_project(pid, status="cancelled", error="")
            _clear_cancel(jid)
            return
        except Exception as e:
            self._on_failure(job, e)
            return
        store.finish_job(jid, "done")
        store.joblog(jid, "info", f"✔ {stage} done")
        _clear_cancel(jid)
        if pid and stage != "notify":
            nxt = pipeline.NEXT_STAGE[stage]
            store.enqueue(pid, job["platform"], nxt, trigger=job["trigger"])

    def _check(self, jid):
        if _is_cancelled(jid) or self._stop.is_set():
            raise Cancelled()

    def _resource_guard(self, job) -> str | None:
        if job["stage"] in ("voice", "assets", "render", "timeline") and job["platform"] != "system":
            need = settings.automation()["storage"]["min_free_gb"]
            free = core.disk()["free_gb"]
            if free < need:
                msg = f"Low disk space: {free} GB free, {need} GB required"
                store.raise_alert("disk_low", "error", msg + ". Delete old projects or enlarge the disk; jobs resume automatically.")
                return msg
            store.clear_alert("disk_low")
        return None

    def _on_failure(self, job, e: Exception):
        jid, pid = job["id"], job["project_id"]
        recoverable = e.recoverable if isinstance(e, StageError) else pipeline._is_network(e)
        msg = str(e)[:600] or type(e).__name__
        if not isinstance(e, StageError):
            core.log.error("stage crashed: %s", traceback.format_exc())
        a = settings.automation()["retry"]
        row = store.get_job(jid)
        if recoverable and row["attempts"] < row["max_attempts"]:
            delay = a["backoff_s"] * (2 ** (row["attempts"] - 1))
            store.requeue_job(jid, msg, time.time() + delay)
            store.joblog(jid, "warn", f"Attempt {row['attempts']}/{row['max_attempts']} failed (recoverable): {msg} — retry in {int(delay)}s")
            if pid:
                store.update_project(pid, status="queued", error=msg)
            return
        store.finish_job(jid, "failed", msg)
        store.joblog(jid, "error", f"Failed: {msg}" + ("" if recoverable else " (not retryable without changing the input)"))
        if pid:
            store.update_project(pid, status="failed", error=msg, stage=job["stage"])
            r = store.get_row(pid)
            notifier.send(f"❌ {job['platform'].title()} • {r['title']}\nStage '{job['stage']}' failed after {row['attempts']} attempt(s):\n{msg[:400]}")
        else:
            notifier.send(f"❌ Daily automation planner failed after {row['attempts']} attempt(s):\n{msg[:400]}")
        if "quota" in msg.lower() or "rate limit" in msg.lower():
            store.raise_alert("ai_quota", "error", "AI quota/rate limit prevented a job from completing.")

    # ---- daily planner (runs as a job on the 'system' lane)
    def _plan_day(self, job):
        key = job["idem_key"]
        date = key.split(":", 1)[1] if key.startswith("daily:") else core.bkk_date()
        a = settings.automation()
        pcfg = settings.platforms()
        enabled = [p for p in core.PLATFORMS if a["platforms"].get(p) and pcfg[p]["enabled"]]
        if not enabled:
            raise StageError("No platform is enabled for automation", recoverable=False)
        log = lambda m: store.joblog(job["id"], "info", str(m))  # noqa: E731
        taken_titles = [r["title"] for r in db.query("SELECT title FROM projects")]
        taken_cats, created = [], []
        for p in enabled:
            ex = db.one("SELECT * FROM projects WHERE platform=? AND date=? AND origin='auto'", (p, date))
            if ex:
                log(f"{p}: already planned ({ex['title']})")
                taken_titles.append(ex["title"])
                taken_cats.append(ex["category"])
                continue
            src, rejected = None, []
            for _ in range(4):
                try:
                    cand = research_mod.pick(p, taken_cats, taken_titles + rejected, dt.date.fromisoformat(date), log)
                except Exception as e:
                    log(f"{p}: research failed: {str(e)[:200]}")
                    break
                bad = [c for c in pipeline.validate_source(cand, p) if not c["ok"]]
                if bad:
                    log(f"{p}: rejected '{cand['title']}': " + "; ".join(c["name"] for c in bad))
                    rejected.append(cand["title"])
                    continue
                src = cand
                break
            if not src:
                continue
            cfg = {**pcfg[p]}
            proj = store.create_project(p, src["title"], category=src["category"], year=src.get("year"), country=src.get("country") or "", origin="auto",
                                        config=cfg, research={**src, "source_refs": pipeline.source_view(src, p)["sources"]}, date=date)
            store.save_pick(date, p, src["title"], src["category"], src)
            legacy_state.mark_used(src["title"], p, date, src["category"])
            store.enqueue(proj["id"], p, "research", trigger="auto")
            taken_titles.append(src["title"])
            taken_cats.append(src["category"])
            created.append((p, src["title"], src["category"]))
            log(f"{p}: picked '{src['title']}' [{src['category']}]")
        if not created and not db.query("SELECT 1 FROM projects WHERE date=? AND origin='auto'", (date,)):
            raise StageError("Daily research could not verify a title for any platform (catalogs unreachable or no verifiable titles).", recoverable=True)
        a = settings.automation()
        a["last_run_date"] = date
        settings.save_automation(a)
        if created:
            notifier.send(f"🔎 NEXORA daily picks {date}\n" + "\n".join(f"• {p.title()}: {t} [{c}]" for p, t, c in created) + "\nPipelines are now running.")

    # ---- scheduler + housekeeping
    def _scheduler_loop(self):
        tick = 0
        while not self._stop.is_set():
            try:
                self.tick(tick)
            except Exception:
                core.log.exception("scheduler tick failed")
            tick += 1
            self._stop.wait(15)

    def tick(self, tick=0):
        a = settings.automation()
        if a["state"] == "running":
            now = core.bkk_now()
            h, m = core.parse_hhmm(a["schedule"])
            today = core.bkk_date()
            due = now >= now.replace(hour=h, minute=m, second=0, microsecond=0)
            if due and a.get("last_run_date") != today:
                self.trigger_daily(today, "auto")
        self.monitor()
        self._maybe_daily_report()
        if tick % 40 == 0:
            cleanup_temp(max_age_h=24)

    def trigger_daily(self, date: str, trigger: str):
        job, created = store.enqueue(None, "system", "research", trigger=trigger, key=f"daily:{date}", payload={"date": date})
        if created:
            core.syslog("info", f"Daily automation queued for {date} (job #{job['id']}, trigger {trigger})")
        return job, not created

    def monitor(self):
        s = core.system_info()
        if not s["ffmpeg"]["ok"]:
            store.raise_alert("no_ffmpeg", "error", "ffmpeg is not installed on this host; rendering is impossible.")
        else:
            store.clear_alert("no_ffmpeg")
        if not s["persistence"]["persistent"]:
            store.raise_alert("ephemeral_storage", "warn", "Storage is ephemeral: projects and the job database are lost on restart/redeploy. Attach a persistent disk and set DATA_DIR.")
        else:
            store.clear_alert("ephemeral_storage")
        free, need = s["disk"]["free_gb"], settings.automation()["storage"]["min_free_gb"]
        if free < need:
            store.raise_alert("disk_low", "error", f"Low disk space: {free} GB free, {need} GB required.")
        if not (providers.configured("openai") or providers.configured("gemini")):
            store.raise_alert("ai_not_configured", "error", "No AI provider is configured. Set OPENAI_API_KEY and/or GEMINI_API_KEY on the server.")
        if not s["executor"]["can_render_local"]:
            store.raise_alert("host_too_small", "warn", "This host has too little memory/CPU for long renders: " + "; ".join(s["executor"]["reasons"])[:200])
        else:
            store.clear_alert("host_too_small")

    def _maybe_daily_report(self):
        today = core.bkk_date()
        if db.kv_get(f"report_sent:{today}"):
            return
        rows = db.query("SELECT status FROM projects WHERE date=? AND origin='auto'", (today,))
        if not rows or any(r["status"] in ("draft", "queued", "running", "paused") for r in rows):
            return
        if notifier.send(notifier.daily_report(today)) or not notifier.token():
            db.kv_set(f"report_sent:{today}", time.time())


# ------------------------------------------------------------------------------------------------ operations used by the API
engine = Engine()


def set_automation_state(state: str) -> dict:
    if state not in ("running", "paused", "stopped"):
        raise ValueError("bad state")
    a = settings.automation()
    prev = a["state"]
    a["state"] = state
    settings.save_automation(a)
    if state == "stopped":
        ids = [r["id"] for r in db.query("SELECT id FROM jobs WHERE status IN ('queued','running') AND trigger IN ('auto','system')")]
        store.cancel_queued("trigger IN ('auto','system')")
        request_cancel(ids)
        db.query("SELECT 1")
        with db.tx() as c:
            c.execute("UPDATE projects SET status='cancelled' WHERE origin='auto' AND status IN ('queued','running') AND id NOT IN (SELECT project_id FROM jobs WHERE status='queued' AND project_id IS NOT NULL)")
    core.syslog("info", f"Automation {prev} → {state}")
    db.audit("system", f"automation_{state}")
    if state == "running":
        engine.tick()  # schedule check without waiting for the next 15 s tick
    return a


def run_now() -> tuple[dict, bool]:
    today = core.bkk_date()
    job, existed = engine.trigger_daily(today, "system")
    return job, existed


def enqueue_from_stage(pid: int, from_stage: str, trigger="manual", force=False) -> dict:
    if from_stage not in core.STAGES:
        raise ValueError("Unknown stage")
    row = store.get_row(pid)
    if not row:
        raise KeyError(pid)
    ids = [r["id"] for r in db.query("SELECT id FROM jobs WHERE project_id=? AND status='running'", (pid,))]
    if ids:
        raise ValueError("A job for this project is currently running; cancel it first")
    store.cancel_queued("project_id=?", (pid,))
    if not force and from_stage != "research":
        prev_needs = {"voice": ["script"], "srt": ["cues"], "timeline": ["cues"], "render": ["scenes", "audio_mp3"], "qc": ["video"], "publish": ["video"], "notify": ["video"]}
        for kind in prev_needs.get(from_stage, []):
            if not store.get_file_by_kind(pid, kind):
                raise ValueError(f"Cannot start at '{from_stage}': earlier output '{kind}' does not exist yet")
    for st in core.STAGES[core.STAGES.index(from_stage):]:
        store.invalidate_kinds(pid, pipeline.STAGE_OUTPUTS.get(st, []))
    if from_stage in ("script",):
        store.invalidate_kinds(pid, ["cues"])
    with db.tx() as c:
        c.execute("UPDATE projects SET run=run+1, error='', status='queued' WHERE id=?", (pid,))
    job, _ = store.enqueue(pid, row["platform"], from_stage, trigger=trigger)
    return job


def cancel_project(pid: int) -> int:
    ids = [r["id"] for r in db.query("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','running')", (pid,))]
    store.cancel_queued("project_id=?", (pid,))
    request_cancel(ids)
    store.update_project(pid, status="cancelled")
    return len(ids)


def cancel_job(jid: int) -> bool:
    j = store.get_job(jid)
    if not j or j["status"] not in ("queued", "running"):
        return False
    request_cancel([jid])
    if j["status"] == "queued":
        store.finish_job(jid, "cancelled", "cancelled by user")
        if j["project_id"]:
            store.update_project(j["project_id"], status="cancelled")
    return True


def retry_job(jid: int) -> dict:
    j = store.get_job(jid)
    if not j or j["status"] not in ("failed", "cancelled"):
        raise ValueError("Only failed or cancelled jobs can be retried")
    _clear_cancel(jid)
    store.reset_job_for_retry(jid)
    if j["project_id"]:
        store.update_project(j["project_id"], status="queued", error="")
    return store.job_with_title(jid)


def cleanup_temp(max_age_h: float = 0) -> dict:
    """Remove scratch/work directories and old previews. Never touches project output files."""
    freed, removed = 0, 0
    busy = {r["project_id"] for r in db.query("SELECT DISTINCT project_id FROM jobs WHERE status IN ('queued','running') AND project_id IS NOT NULL")}
    root = core.WORK_ROOT
    if root.exists():
        for d in root.iterdir():
            if not d.is_dir():
                continue
            if d.name.isdigit() and int(d.name) in busy:
                continue
            if d.name == "0" or max_age_h == 0 or time.time() - d.stat().st_mtime > max_age_h * 3600:
                if d.name == "0" and max_age_h and time.time() - d.stat().st_mtime < 3600:
                    continue
                freed += core.dir_size(d)
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
    if core.PREVIEW_DIR.exists():
        for f in core.PREVIEW_DIR.glob("*.mp3"):
            if time.time() - f.stat().st_mtime > 3600:
                freed += f.stat().st_size
                f.unlink(missing_ok=True)
                removed += 1
    return {"freed_mb": round(freed / 1e6, 2), "removed": removed}
