"""aiohttp HTTP API + static SPA for NEXORA Studio. Contract: studio/API.md.

Mounted into the existing bot web app (see ``mount``), so the Telegram webhook and /health keep working unchanged.
Security: server-side sessions (HttpOnly, SameSite=Strict cookie), CSRF header on every write, role check (viewer = read-only),
per-IP rate limits, strict upload validation, security headers, and no secret ever leaves the server.
"""
import asyncio
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from aiohttp import web

from .base import research as research_mod, state as legacy_state
from . import assets as assets_mod, core, db, notifier, pipeline, providers, publisher, security, settings, store, voice, worker

STATIC = Path(__file__).parent / "static"
PUBLIC = {"/auth/login", "/auth/session", "/health"}
routes = web.RouteTableDef()
_source_cache: dict[str, tuple[float, dict]] = {}


class ApiError(Exception):
    def __init__(self, status, msg, code="error", headers=None):
        super().__init__(msg)
        self.status, self.msg, self.code, self.headers = status, msg, code, headers or {}


def jr(data, status=200, **kw):
    return web.json_response(data, status=status, dumps=lambda d: json.dumps(d, ensure_ascii=False, default=str), **kw)


def ip_of(req) -> str:
    xf = req.headers.get("X-Forwarded-For", "")
    return (xf.split(",")[0].strip() if xf else req.remote) or "?"


async def body(req) -> dict:
    try:
        d = await req.json()
    except Exception:
        raise ApiError(400, "Request body must be valid JSON", "bad_json")
    if not isinstance(d, dict):
        raise ApiError(400, "Request body must be a JSON object", "bad_json")
    return d


def need_confirm(req):
    if req.query.get("confirm") != "1":
        raise ApiError(400, "Confirmation required: add ?confirm=1", "confirm_required")


def pid_of(req) -> int:
    try:
        pid = int(req.match_info["id"])
    except ValueError:
        raise ApiError(404, "Not found", "not_found")
    if not store.get_row(pid):
        raise ApiError(404, "Project not found", "not_found")
    return pid


def limit(req, key, n, window=60):
    ok, retry = security.limiter.hit(f"{key}:{ip_of(req)}", n, window)
    if not ok:
        raise ApiError(429, "Too many requests", "rate_limited", {"Retry-After": str(retry)})


async def th(fn, *a, **kw):
    return await asyncio.to_thread(fn, *a, **kw)


# ------------------------------------------------------------------------------------------------ middleware
@web.middleware
async def guard(req: web.Request, handler):
    path = req.path[len("/api"):] if req.path.startswith("/api") else req.path
    try:
        limit(req, "api", 600)
        sid = req.cookies.get(security.COOKIE)
        sess = await th(security.get_session, sid) if sid else None
        req["session"], req["sid"] = sess, sid  # noqa
        if path not in PUBLIC and not path.startswith("/internal/"):
            if not sess:
                raise ApiError(401, "Login required", "unauthenticated")
            if req.method not in ("GET", "HEAD"):
                if not security.csrf_ok(sess, req.headers.get("X-CSRF-Token")):
                    raise ApiError(403, "Invalid or missing CSRF token", "csrf")
                if sess["role"] != "admin":
                    raise ApiError(403, "Read-only account", "read_only")
        return await handler(req)
    except ApiError as e:
        return jr({"error": e.msg, "code": e.code}, e.status, headers=e.headers)
    except web.HTTPException as e:
        if e.status >= 400:
            return jr({"error": e.reason, "code": "http_" + str(e.status)}, e.status)
        raise
    except KeyError as e:
        return jr({"error": "Not found", "code": "not_found"}, 404)
    except ValueError as e:
        return jr({"error": str(e), "code": "invalid"}, 400)
    except LookupError as e:
        return jr({"error": str(e) if str(e) != "not_configured" else "Not configured on the server", "code": "not_configured"}, 409)
    except providers.ProviderError as e:
        return jr({"error": str(e), "code": e.kind}, 502)
    except Exception:
        core.log.exception("unhandled API error on %s %s", req.method, req.path)
        return jr({"error": "Internal server error", "code": "internal"}, 500)


@web.middleware
async def headers_mw(req, handler):
    resp = await handler(req)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    resp.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                            "font-src https://fonts.gstatic.com; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
    if req.headers.get("X-Forwarded-Proto") == "https" or req.secure:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000")
    if req.path.startswith("/api"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ------------------------------------------------------------------------------------------------ auth
@routes.get("/health")
async def health(req):
    return jr({"ok": True, "version": core.VERSION})


@routes.get("/auth/session")
async def auth_session(req):
    s = req["session"]
    return jr({"configured": security.configured(), "authenticated": bool(s), "role": s["role"] if s else None, "csrf": s["csrf"] if s else None})


@routes.post("/auth/login")
async def auth_login(req):
    ip = ip_of(req)
    wait = security.login_blocked(ip)
    if wait:
        raise ApiError(429, "Too many failed logins", "rate_limited", {"Retry-After": str(wait)})
    if not security.configured():
        raise ApiError(503, "Server has no NEXORA_ADMIN_PASSWORD configured (min 12 characters)", "not_configured")
    role = security.check_password((await body(req)).get("password", ""))
    if not role:
        security.login_failed(ip)
        await th(db.audit, "anonymous", "login_failed", ip)
        await asyncio.sleep(0.4)
        raise ApiError(401, "Incorrect password", "bad_credentials")
    security.login_succeeded(ip)
    sid, csrf = await th(security.create_session, role, ip)
    await th(db.audit, role, "login", ip)
    r = jr({"role": role, "csrf": csrf})
    r.set_cookie(security.COOKIE, sid, max_age=security.SESSION_TTL, httponly=True, samesite="Strict", path="/",
                 secure=req.secure or req.headers.get("X-Forwarded-Proto") == "https")
    return r


@routes.post("/auth/logout")
async def auth_logout(req):
    await th(security.destroy_session, req.get("sid"))
    r = jr({"ok": True})
    r.del_cookie(security.COOKIE, path="/")
    return r


# ------------------------------------------------------------------------------------------------ dashboard / system
def _recent_videos(n=6):
    rows = db.query("""SELECT f.id file_id, f.project_id, f.size, f.duration, f.created, p.title, p.platform FROM project_files f
                       JOIN projects p ON p.id=f.project_id WHERE f.kind='video' ORDER BY f.created DESC LIMIT ?""", (n,))
    return [{"project_id": r["project_id"], "title": r["title"], "platform": r["platform"], "file_id": r["file_id"], "size": r["size"], "duration": r["duration"], "created": r["created"]} for r in rows]


def automation_view() -> dict:
    a = settings.automation()
    today = core.bkk_date()
    projects, _ = store.list_projects(date=today, limit=20)
    hist = {}
    for p in db.query("SELECT id,platform,title,status,date FROM projects WHERE origin='auto' ORDER BY date DESC, id DESC LIMIT 120"):
        hist.setdefault(p["date"], []).append({"platform": p["platform"], "title": p["title"], "status": p["status"], "project_id": p["id"]})
    history = []
    for d, ps in list(hist.items())[:14]:
        sts = {p["status"] for p in ps}
        done = {"ready_to_publish", "published", "completed"}
        status = "running" if sts & {"draft", "queued", "running", "paused"} else "completed" if sts <= done else "failed" if sts <= {"failed", "cancelled"} else "partial"
        history.append({"date": d, "status": status, "projects": ps})
    return {"state": a["state"], "schedule": a["schedule"], "tz": core.TZ_NAME, "next_run": core.next_run_after(a["schedule"]) if a["state"] == "running" else None, "last_run_date": a.get("last_run_date"), "publish_mode": a["publish_mode"],
            "platforms": a["platforms"], "retry": a["retry"], "storage": a["storage"], "today": {"date": today, "picks": store.picks_for(today), "projects": projects},
            "workers": worker.engine.status(), "history": history}


@routes.get("/dashboard")
async def dashboard(req):
    def build():
        tg = notifier.info()
        a = automation_view()
        projects, _ = store.list_projects(limit=6)
        running = [store.job_with_title(r["id"]) for r in db.query("SELECT id FROM jobs WHERE status='running' ORDER BY id")]
        return {"now": time.time(), "tz": core.TZ_NAME,
                "backend": {"ok": True, "version": core.VERSION, "uptime_s": round(time.time() - core.STARTED, 1), "studio_workers": worker.engine.status()["running"], "db_schema": db.schema_version()},
                "telegram": {k: tg[k] for k in ("configured", "connected", "bot_username", "webhook_url", "pending_updates", "error", "chat_configured")},
                "providers": providers.overview()["providers"],
                "automation": {"state": a["state"], "schedule": a["schedule"], "next_run": a["next_run"], "last_run_date": a["last_run_date"], "today": {"date": a["today"]["date"], "picks": a["today"]["picks"]}},
                "jobs": store.job_counts(), "recent_projects": projects, "recent_videos": _recent_videos(), "recent_errors": store.recent_errors(8), "running_jobs": running,
                "alerts": store.alerts(), "resources": core.resources_brief()}
    return jr(await th(build))


@routes.get("/system")
async def system(req):
    return jr(await th(core.system_info))


@routes.post("/internal/tick")
async def internal_tick(req):
    tok = os.getenv("NEXORA_CRON_TOKEN", "")
    if len(tok) < 16 or not hmac.compare_digest(req.headers.get("X-NEXORA-Cron-Token", ""), tok):
        raise ApiError(403, "Invalid cron token", "forbidden")
    await th(worker.engine.tick)
    return jr({"ok": True, "automation": settings.automation()["state"], "workers": worker.engine.status()})


# ------------------------------------------------------------------------------------------------ research
def _cache_source(src: dict) -> str:
    now = time.time()
    for k in [k for k, (t, _) in _source_cache.items() if now - t > 3600]:
        _source_cache.pop(k, None)
    if len(_source_cache) > 50:
        _source_cache.pop(min(_source_cache, key=lambda k: _source_cache[k][0]), None)
    sid = secrets.token_urlsafe(12)
    _source_cache[sid] = (now, src)
    return sid


def catalog_search(q: str, category: str) -> list[dict]:
    out = []
    errors = []
    try:
        gq = 'query($s:String){Page(perPage:10){media(type:ANIME,search:$s,isAdult:false){title{romaji english native} startDate{year} countryOfOrigin format genres siteUrl}}}'
        for m in research_mod.get("https://graphql.anilist.co", json_body={"query": gq, "variables": {"s": q}})["data"]["Page"]["media"]:
            cat = "Donghua" if m["countryOfOrigin"] == "CN" else "Anime"
            out.append({"title": m["title"]["english"] or m["title"]["romaji"], "original_title": m["title"]["native"] or m["title"]["romaji"], "year": (m["startDate"] or {}).get("year"),
                        "country": m["countryOfOrigin"], "category": cat, "genres": m["genres"], "kind": m["format"], "catalog": "AniList", "url": m["siteUrl"], "source_urls": [m["siteUrl"]]})
    except Exception as e:
        errors.append(f"AniList: {str(e)[:100]}")
    from .base import config
    if config.TMDB_ENABLED:
        try:
            for r in research_mod.tmdb("/search/multi", query=q)["results"][:10]:
                if r.get("media_type") not in ("movie", "tv"):
                    continue
                c = research_mod._tm(r, r["media_type"], "film" if r["media_type"] == "movie" else "TV series")
                anim = 16 in (c["genres"] or [])
                cat = category if category in ("Cartoon", "3D Animation") and anim else ("Cartoon" if anim else "International Movies")
                out.append({"title": c["title"], "original_title": c["alt"] or c["title"], "year": c["year"], "country": c["country"], "category": cat, "genres": ["Animation"] if anim else [],
                            "kind": c["kind"], "catalog": "TMDB", "url": c["url"], "source_urls": [c["url"]]})
        except Exception as e:
            errors.append(f"TMDB: {str(e)[:100]}")
    else:
        errors.append("TMDB_API_READ_ACCESS_TOKEN (or TMDB_API_KEY) is not configured (movies/cartoons/3D need it)")
    real = [e for e in errors if "not configured" not in e]
    if not out and real:
        raise RuntimeError("; ".join(real))
    for r in out:
        r["excluded"] = str(r["country"]) in pipeline.INDIA
        r["exclusion_reason"] = "Indian titles are excluded" if r["excluded"] else None
    if category in core.CATEGORIES:
        out = [r for r in out if r["category"] == category or (category == "3D Animation" and r["category"] == "Cartoon" and r["catalog"] == "TMDB")]
    return out


@routes.get("/research/search")
async def r_search(req):
    limit(req, "research", 30)
    q = req.query.get("q", "").strip()
    if not (2 <= len(q) <= 120):
        raise ApiError(400, "Search text must be 2-120 characters", "invalid")
    cat = req.query.get("category", "")
    try:
        results = await th(catalog_search, q, cat)
    except RuntimeError as e:
        raise ApiError(502, f"Catalog lookup failed: {e}", "upstream")
    return jr({"results": results})


@routes.post("/research/verify")
async def r_verify(req):
    limit(req, "research", 30)
    d = await body(req)
    title, platform = str(d.get("title", "")).strip(), d.get("platform", "youtube")
    if not title or len(title) > 200 or platform not in core.PLATFORMS:
        raise ApiError(400, "title and a valid platform are required", "invalid")

    def work():
        try:
            src = research_mod.resolve_title(title, platform)
        except Exception as e:
            return {"verified": False, "status": "not_found", "title": title, "original_title": title, "year": d.get("year"), "country": None, "category": d.get("category"), "genres": [],
                    "wiki_url": None, "plot_chars": 0, "sources": [], "views_30d": 0, "checks": [{"name": "title found in catalogs + Wikipedia", "ok": False, "detail": str(e)[:200]}], "source_id": ""}
        if d.get("category") in core.CATEGORIES:
            src["category"] = d["category"]
        v = pipeline.source_view(src, platform)
        if v["verified"]:
            src["source_refs"] = v["sources"]
            v["source_id"] = _cache_source(src)
        return v
    return jr(await th(work))


@routes.get("/research/trends")
async def r_trends(req):
    limit(req, "research", 30)
    cat = req.query.get("category", "Anime")
    if cat not in core.CATEGORIES:
        raise ApiError(400, "Unknown category", "invalid")

    def work():
        used = legacy_state.used_titles() | {legacy_state.norm(r["title"]) for r in db.query("SELECT title FROM projects")}
        items = []
        for c in sorted(research_mod.candidates(cat), key=lambda x: -(x.get("popularity") or 0))[:20]:
            if str(c.get("country")) in pipeline.INDIA:
                continue
            items.append({"title": c["title"], "year": c.get("year"), "country": c.get("country"), "popularity": c.get("popularity"), "catalog": c.get("catalog"), "url": c.get("url"),
                          "used_before": legacy_state.norm(c["title"]) in used})
        return items
    try:
        items = await th(work)
    except Exception as e:
        raise ApiError(502, f"Trend sources unavailable: {str(e)[:160]}", "upstream")
    return jr({"category": cat, "items": items, "fetched_at": time.time()})


@routes.get("/research/today")
async def r_today(req):
    today = core.bkk_date()
    picks = await th(store.picks_for, today)
    return jr({"date": today, "picks": picks, "distinct": len({p["title"] for p in picks}) == len(picks) and len({p["category"] for p in picks}) == len(picks)})


# ------------------------------------------------------------------------------------------------ projects
def project_detail(pid: int) -> dict:
    return {"project": store.get_project(pid), "jobs": store.list_jobs(project_id=pid, limit=100), "assets": assets_mod.list_assets(pid), "logs": store.project_logs(pid),
            "source": store.read_json_file(pid, "source")}


@routes.get("/projects")
async def p_list(req):
    q = req.query
    items, total = await th(store.list_projects, q.get("platform"), q.get("date"), q.get("status"), q.get("limit", 50))
    return jr({"projects": items, "total": total})


@routes.post("/projects")
async def p_create(req):
    d = await body(req)
    platform, title = d.get("platform"), d.get("title", "")
    research = None
    if d.get("source_id"):
        ent = _source_cache.get(str(d["source_id"]))
        if not ent:
            raise ApiError(400, "source_id expired; verify the title again", "invalid")
        research = ent[1]
        title = research.get("title") or title
    p = await th(store.create_project, platform, title, category=d.get("category") or (research or {}).get("category", ""), year=(research or {}).get("year"),
                 country=(research or {}).get("country", ""), origin="manual", config=d.get("config") or {}, research=research)
    if d.get("autostart"):
        await th(store.enqueue, p["id"], p["platform"], "research", trigger="manual")
        p = store.get_project(p["id"])
    await th(db.audit, req["session"]["role"], "project_create", f"{p['id']} {p['title']}")
    return jr(p, 201)


@routes.get("/projects/{id}")
async def p_get(req):
    return jr(await th(project_detail, pid_of(req)))


@routes.delete("/projects/{id}")
async def p_delete(req):
    need_confirm(req)
    pid = pid_of(req)
    if db.one("SELECT 1 FROM jobs WHERE project_id=? AND status='running'", (pid,)):
        raise ApiError(409, "A job is running for this project; cancel it first", "busy")
    n = await th(store.delete_project, pid)
    await th(db.audit, "admin", "project_delete", str(pid))
    return jr({"ok": True, "deleted_files": n})


@routes.post("/projects/{id}/run")
async def p_run(req):
    pid = pid_of(req)
    d = await body(req) if req.can_read_body else {}
    job = await th(worker.enqueue_from_stage, pid, d.get("from_stage") or "research", "manual", bool(d.get("force")))
    return jr({"ok": True, "job": store.job_to_api(job)})


@routes.post("/projects/{id}/cancel")
async def p_cancel(req):
    n = await th(worker.cancel_project, pid_of(req))
    return jr({"ok": True, "cancelled_jobs": n})


# ---- script
def script_view(pid: int) -> dict:
    doc = pipeline.script_doc(pid)
    if not doc:
        raise ApiError(404, "No script yet", "no_script")
    src = store.research_of(pid) or {}
    srcs = src.get("source_refs") or []
    return {"sections": doc["sections"], "provider": doc.get("provider"), "verified": bool(src.get("wiki_url")), "sources": srcs, "stats": pipeline.script_stats(doc["sections"]), "edited": bool(doc.get("edited"))}


def invalidate_from(pid: int, stage: str):
    if db.one("SELECT 1 FROM jobs WHERE project_id=? AND status='running'", (pid,)):
        raise ApiError(409, "A job is running for this project; cancel it first", "busy")
    store.cancel_queued("project_id=?", (pid,))
    for st in core.STAGES[core.STAGES.index(stage):]:
        store.invalidate_kinds(pid, pipeline.STAGE_OUTPUTS.get(st, []))
    with db.tx() as c:
        c.execute("UPDATE projects SET run=run+1, status='draft', stage='', progress=0 WHERE id=?", (pid,))


@routes.get("/projects/{id}/script")
async def s_get(req):
    return jr(await th(script_view, pid_of(req)))


@routes.put("/projects/{id}/script")
async def s_put(req):
    pid = pid_of(req)
    sections = pipeline.validate_sections((await body(req)).get("sections"))
    old = pipeline.script_doc(pid) or {}

    def work():
        invalidate_from(pid, "voice")
        store.invalidate_kinds(pid, ["cues"])
        pipeline.save_script(pid, sections, provider=old.get("provider"), edited=True)
        return script_view(pid)
    return jr(await th(work))


@routes.post("/projects/{id}/script/regenerate")
async def s_regen(req):
    pid = pid_of(req)
    job = await th(worker.enqueue_from_stage, pid, "script", "manual", True)
    return jr({"ok": True, "job": store.job_to_api(job)})


# ---- subtitles
def subs_view(pid: int) -> dict:
    cd = pipeline.cues_doc(pid)
    if not cd:
        raise ApiError(404, "No narration/subtitle timing yet", "no_subtitles")
    mp3 = store.get_file_by_kind(pid, "audio_mp3")
    rep = {}
    for lang in ("en", "my"):
        p = store.file_path(pid, f"srt_{lang}")
        if p:
            try:
                v = pipeline.subs.validate_srt(p)
                rep[lang] = {"ok": v["ok"], "cues": v["cues"], "issues": v["issues"][:10]}
            except Exception as e:
                rep[lang] = {"ok": False, "cues": 0, "issues": [str(e)[:100]]}
    return {"cues": [{"i": i + 1, "start": c["start"], "end": c["end"], "my": c.get("my", ""), "en": c.get("en", "")} for i, c in enumerate(cd["cues"])], "duration": cd.get("duration"),
            "audio_url": f"/api/files/{mp3['id']}/download?inline=1" if mp3 else None, "srt": rep}


def save_cues(pid: int, cues: list):
    cd = pipeline.cues_doc(pid)
    if not cd:
        raise ApiError(404, "No narration timing yet", "no_subtitles")
    if not isinstance(cues, list) or not (1 <= len(cues) <= 5000):
        raise ValueError("cues must be a list of 1-5000 items")
    out, prev_end, dur = [], 0.0, float(cd.get("duration") or 0)
    for i, c in enumerate(cues, 1):
        try:
            s, e = round(float(c["start"]), 3), round(float(c["end"]), 3)
        except Exception:
            raise ValueError(f"cue {i}: start/end must be numbers (seconds)")
        if s < 0 or e <= s:
            raise ValueError(f"cue {i}: end must be after start (and start ≥ 0)")
        if s < prev_end - 0.001:
            raise ValueError(f"cue {i}: overlaps the previous cue")
        if dur and e > dur + 1.0:
            raise ValueError(f"cue {i}: ends after the narration audio ({dur:.1f}s)")
        old = cd["cues"][i - 1] if i - 1 < len(cd["cues"]) else {}
        my, en = str(c.get("my", "")).strip()[:800], str(c.get("en", "")).strip()[:600]
        if not (my or en):
            raise ValueError(f"cue {i}: needs Burmese or English text")
        out.append({"start": s, "end": e, "my": my, "en": en, "sec": old.get("sec", out[-1]["sec"] if out else 0)})
        prev_end = e
    cd["cues"] = out
    cd["edited"] = True
    store.write_json_file(pid, "cues", "cues.json", cd)
    pipeline.write_srts(pid, out)
    for k in ("scenes", "video", "qc", "metadata"):  # derived from timing; must be rebuilt
        store.invalidate_kinds(pid, [k])
    store.update_project(pid, status="draft")


@routes.get("/projects/{id}/subtitles")
async def sub_get(req):
    return jr(await th(subs_view, pid_of(req)))


@routes.put("/projects/{id}/subtitles")
async def sub_put(req):
    pid = pid_of(req)
    cues = (await body(req)).get("cues")

    def work():
        save_cues(pid, cues)
        return subs_view(pid)
    return jr(await th(work))


@routes.post("/projects/{id}/subtitles/shift")
async def sub_shift(req):
    pid = pid_of(req)
    try:
        sec = float((await body(req)).get("seconds"))
    except Exception:
        raise ApiError(400, "seconds must be a number", "invalid")
    if abs(sec) > 30:
        raise ApiError(400, "seconds must be between -30 and 30", "invalid")

    def work():
        cd = pipeline.cues_doc(pid)
        if not cd:
            raise ApiError(404, "No timing yet", "no_subtitles")
        cues = [{**c, "start": max(0.0, c["start"] + sec), "end": max(0.01, c["end"] + sec)} for c in cd["cues"]]
        save_cues(pid, cues)
        return subs_view(pid)
    return jr(await th(work))


# ---- files / timeline / publish
@routes.get("/projects/{id}/files")
async def p_files(req):
    files = await th(store.list_files, pid_of(req))
    return jr({"files": files, "total_size": sum(f["size"] for f in files)})


@routes.get("/projects/{id}/timeline")
async def p_timeline(req):
    pid = pid_of(req)
    tl = await th(store.read_json_file, pid, "scenes")
    if not tl:
        return jr({"scenes": [], "total": 0, "has_scenes": False})
    titles = {a["id"]: a["title"] for a in assets_mod.list_assets(pid)}
    return jr({"scenes": [{"i": s["i"], "start": s["start"], "end": s["end"], "section": s["section"], "asset_id": s.get("asset_id"), "asset_title": titles.get(s.get("asset_id")), "label": s.get("label", "")}
                          for s in tl["scenes"]], "total": tl["total"], "has_scenes": True})


@routes.get("/projects/{id}/publish")
async def p_publish(req):
    pid = pid_of(req)
    d = await th(store.read_json_file, pid, "metadata")
    if not d:
        return jr({"mode": settings.effective_publish_mode(json.loads(store.get_row(pid)["config_json"]).get("publish_mode", "draft")), "status": "not_ready", "url": None, "detail": "The video has not reached the publish stage yet.", "metadata": None})
    return jr({k: d.get(k) for k in ("mode", "status", "url", "detail", "metadata")})


def _file_or_404(fid: int):
    f = store.get_file(fid)
    if not f or not f["path"]:
        raise ApiError(404, "File not found", "not_found")
    p = Path(f["path"])
    if not core.is_within(p, core.PROJECTS_DIR) or not p.exists():
        raise ApiError(404, "File not found", "not_found")
    return f, p


@routes.get("/files/{id}/download")
async def f_download(req):
    try:
        f, p = _file_or_404(int(req.match_info["id"]))
    except ValueError:
        raise ApiError(404, "Not found", "not_found")
    inline = req.query.get("inline") == "1" and f["kind"] in ("audio_mp3", "audio_wav", "video")
    r = web.FileResponse(p)
    r.headers["Content-Disposition"] = f'{"inline" if inline else "attachment"}; filename="{p.name}"'
    return r


@routes.delete("/files/{id}")
async def f_delete(req):
    need_confirm(req)
    f, _ = _file_or_404(int(req.match_info["id"]))
    if db.one("SELECT 1 FROM jobs WHERE project_id=? AND status='running'", (f["project_id"],)):
        raise ApiError(409, "A job is running for this project", "busy")
    await th(store.delete_file_row, f["id"])
    await th(db.audit, "admin", "file_delete", f"{f['id']} {f['kind']}")
    return jr({"ok": True})


# ------------------------------------------------------------------------------------------------ jobs / queues
@routes.get("/jobs")
async def j_list(req):
    q = req.query
    jobs = await th(store.list_jobs, q.get("status"), q.get("platform"), int(q["project_id"]) if q.get("project_id", "").isdigit() else None, q.get("limit", 50))
    return jr({"jobs": jobs, "counts": store.job_counts()})


def _jid(req):
    try:
        j = store.job_with_title(int(req.match_info["id"]))
    except ValueError:
        j = None
    if not j:
        raise ApiError(404, "Job not found", "not_found")
    return j


@routes.get("/jobs/{id}")
async def j_get(req):
    j = _jid(req)
    return jr({"job": j, "logs": await th(store.job_logs, j["id"])})


@routes.post("/jobs/{id}/retry")
async def j_retry(req):
    j = _jid(req)
    return jr({"ok": True, "job": await th(worker.retry_job, j["id"])})


@routes.post("/jobs/{id}/cancel")
async def j_cancel(req):
    j = _jid(req)
    if not await th(worker.cancel_job, j["id"]):
        raise ApiError(409, "Only queued or running jobs can be cancelled", "invalid_state")
    return jr({"ok": True})


@routes.get("/queues")
async def queues(req):
    def work():
        out = {}
        for lane in (*core.PLATFORMS, "system"):
            c = {r["status"]: r["n"] for r in db.query("SELECT status, COUNT(*) n FROM jobs WHERE platform=? GROUP BY status", (lane,))}
            cur = db.one("SELECT id FROM jobs WHERE platform=? AND status='running' ORDER BY id LIMIT 1", (lane,))
            out[lane] = {"queued": c.get("queued", 0), "running": c.get("running", 0), "failed": c.get("failed", 0), "current": store.job_with_title(cur["id"]) if cur else None}
        rj = db.one("SELECT id FROM jobs WHERE status='running' AND stage='render' LIMIT 1")
        return {"queues": {k: v for k, v in out.items() if k in core.PLATFORMS}, "render_slot": {"busy": worker.render_slot.locked(), "job_id": rj["id"] if rj else None}}
    return jr(await th(work))


# ------------------------------------------------------------------------------------------------ platforms
@routes.get("/platforms")
async def pf_get(req):
    return jr({"platforms": await th(settings.platforms), "cta_defaults": {"youtube_url": settings.YOUTUBE_URL, "facebook_url": settings.FACEBOOK_URL}, "rules": settings.RULES})


@routes.get("/platforms/status")
async def pf_status(req):
    return jr({"platforms": {p: publisher.capability(p) for p in core.PLATFORMS}})


@routes.put("/platforms/{p}")
async def pf_put(req):
    p = req.match_info["p"]
    if p not in core.PLATFORMS:
        raise ApiError(404, "Unknown platform", "not_found")
    cfg = await th(settings.set_platform, p, await body(req))
    await th(db.audit, "admin", "platform_update", p)
    return jr(cfg)


# ------------------------------------------------------------------------------------------------ voice
@routes.get("/voice/presets")
async def v_presets(req):
    gpu = voice.clone_configured()
    return jr({"presets": settings.voice_presets(), "offline_fallback": {"available": voice.espeak_available(), "note": "Offline espeak-ng Burmese is used only when internet TTS is unreachable. It is robotic (low quality)."},
               "gpu": {"configured": gpu, "clone_supported": gpu, "note": voice.clone_status()["note"]}})


@routes.post("/voice/preview")
async def v_preview(req):
    limit(req, "tts", 20)
    d = await body(req)
    vs = settings.voice_settings()
    voice_key = settings.resolve_voice(d.get("voice") or vs["default_voice"])
    try:
        r = await th(voice.preview, d.get("text", ""), voice_key, vs["rate"], vs["pitch"], None)
    except voice.VoiceError as e:
        raise ApiError(502, str(e), "tts_unavailable")
    return jr({"ok": True, "engine": r["engine"], "quality": r["quality"], "duration": r["duration"], "audio_url": f"/api/voice/preview-audio/{r['id']}", "note": r["note"]})


@routes.get("/voice/preview-audio/{pid}")
async def v_preview_audio(req):
    pid = req.match_info["pid"]
    if not pid.isalnum() or len(pid) != 32:
        raise ApiError(404, "Not found", "not_found")
    p = core.PREVIEW_DIR / f"{pid}.mp3"
    if not p.exists():
        raise ApiError(404, "Preview expired", "not_found")
    return web.FileResponse(p, headers={"Content-Type": "audio/mpeg"})


@routes.get("/voice/profiles")
async def vp_list(req):
    from .base import voices

    def work():
        return {"profiles": [voice.profile_view(p) for p in voices.listing()], "clone": voice.clone_status()}
    return jr(await th(work))


async def _read_upload(req, field="file", max_bytes=security.MAX_UPLOAD_BYTES):
    if not (req.content_type or "").startswith("multipart/"):
        raise ApiError(400, "multipart/form-data required", "invalid")
    fields, data = {}, None
    reader = await req.multipart()
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == field:
            buf = bytearray()
            while True:
                chunk = await part.read_chunk(256 * 1024)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > max_bytes:
                    raise ApiError(413, f"File too large (max {max_bytes // 1024 // 1024} MB)", "too_large")
            data = bytes(buf)
        elif part.name:
            fields[part.name] = (await part.text())[:500]
    if not data:
        raise ApiError(400, "No file uploaded", "invalid")
    return fields, data


@routes.post("/voice/profiles")
async def vp_add(req):
    limit(req, "upload", 10)
    f, data = await _read_upload(req)
    name = security.safe_name(f.get("name", ""))
    if not name:
        raise ApiError(400, "Profile name is required (letters, digits, - and _)", "invalid")
    if f.get("consent") != "yes":
        raise ApiError(400, "You must confirm you have the right to use this voice (consent=yes)", "consent_required")
    ext = security.sniff_audio(data[:16])
    if not ext:
        raise ApiError(400, "Unsupported or corrupt audio. Use ogg, mp3, wav, m4a or flac.", "invalid_file")

    def work():
        from .base import voices
        tmp = core.work_dir(0) / f"upl_{secrets.token_hex(6)}.{ext}"
        tmp.write_bytes(data)
        try:
            dur = core.ffprobe_duration(tmp)
        finally:
            tmp.unlink(missing_ok=True)
        if not dur or dur < 1 or dur > 600:
            raise ValueError("Audio must be readable and between 1 second and 10 minutes long")
        voices.add(name, data, ext=ext, meta={"owner": "web", "consent": True})
        return voice.profile_view(voices.get_profile(name))
    p = await th(work)
    await th(db.audit, "admin", "voice_profile_add", name)
    return jr({"ok": True, "profile": p})


@routes.delete("/voice/profiles/{name}")
async def vp_del(req):
    need_confirm(req)
    from .base import voices
    name = security.safe_name(req.match_info["name"])
    try:
        await th(voices.delete, name)
    except RuntimeError:
        raise ApiError(404, "Profile not found", "not_found")
    await th(db.audit, "admin", "voice_profile_delete", name)
    return jr({"ok": True})


@routes.get("/voice/profile-audio/{name}")
async def vp_audio(req):
    from .base import voices
    try:
        p = Path((await th(voices.get_profile, security.safe_name(req.match_info["name"])))["sample_path"])
    except RuntimeError:
        raise ApiError(404, "Profile not found", "not_found")
    if not p.exists() or not core.is_within(p, voices.ROOT):
        raise ApiError(404, "Sample missing", "not_found")
    return web.FileResponse(p)


@routes.get("/voice/settings")
async def vs_get(req):
    return jr(await th(settings.voice_settings))


@routes.put("/voice/settings")
async def vs_put(req):
    return jr(await th(settings.update_voice_settings, await body(req)))


# ------------------------------------------------------------------------------------------------ assets
@routes.get("/assets/policy")
async def as_policy(req):
    return jr({"allowed_licenses": assets_mod.ALLOWED_LICENSES, "rules": assets_mod.RULES})


@routes.get("/assets/search")
async def as_search(req):
    limit(req, "assets", 30)
    q = req.query.get("q", "").strip()
    if not (2 <= len(q) <= 120):
        raise ApiError(400, "Search text must be 2-120 characters", "invalid")
    src = req.query.get("source", "all")
    if src not in ("commons", "openverse", "all"):
        raise ApiError(400, "source must be commons, openverse or all", "invalid")
    try:
        return jr({"results": await th(assets_mod.search, q, src)})
    except Exception as e:
        raise ApiError(502, f"Asset search failed: {str(e)[:160]}", "upstream")


@routes.post("/projects/{id}/assets")
async def as_add(req):
    limit(req, "assets", 30)
    pid, d = pid_of(req), await body(req)
    try:
        a = await th(assets_mod.add_remote, pid, origin=str(d.get("origin", "")), file_url=str(d.get("file_url", "")), title=str(d.get("title", ""))[:200], page_url=str(d.get("page_url", "")),
                     license=str(d.get("license", "")), license_url=str(d.get("license_url", "")), attribution=str(d.get("attribution", ""))[:300])
    except assets_mod.LicenseRejected as e:
        raise ApiError(422, str(e), "license_rejected")
    store.invalidate_kinds(pid, ["scenes", "video", "qc"])
    return jr(a, 201)


@routes.post("/projects/{id}/assets/upload")
async def as_upload(req):
    limit(req, "upload", 20)
    pid = pid_of(req)
    f, data = await _read_upload(req)
    if f.get("declaration") != "yes":
        raise ApiError(400, "You must declare that you own or are licensed to use this image (declaration=yes)", "declaration_required")
    if not security.sniff_image(data[:16]):
        raise ApiError(400, "Unsupported or corrupt image (png, jpg, webp, gif)", "invalid_file")
    try:
        a = await th(assets_mod.add_upload, pid, data, f.get("license", ""), f.get("attribution", ""), "upload")
    except assets_mod.LicenseRejected as e:
        raise ApiError(422, str(e), "license_rejected")
    store.invalidate_kinds(pid, ["scenes", "video", "qc"])
    return jr(a, 201)


@routes.delete("/assets/{id}")
async def as_del(req):
    need_confirm(req)
    if not await th(assets_mod.delete_asset, int(req.match_info["id"])):
        raise ApiError(404, "Asset not found", "not_found")
    return jr({"ok": True})


@routes.get("/assets/{id}/image")
async def as_image(req):
    a = assets_mod.get_asset(int(req.match_info["id"])) if req.match_info["id"].isdigit() else None
    if not a or not a["local_path"] or not core.is_within(Path(a["local_path"]), core.DATA_DIR) or not Path(a["local_path"]).exists():
        raise ApiError(404, "Image not found", "not_found")
    return web.FileResponse(a["local_path"])


# ------------------------------------------------------------------------------------------------ automation / telegram / ai
@routes.get("/automation")
async def au_get(req):
    return jr(await th(automation_view))


@routes.post("/automation/{action}")
async def au_action(req):
    action = req.match_info["action"]
    if action in ("start", "pause", "resume", "stop"):
        cur = settings.automation()["state"]
        target = {"start": "running", "resume": "running", "pause": "paused", "stop": "stopped"}[action]
        if (action == "start" and cur != "stopped") or (action == "resume" and cur != "paused") or (action == "pause" and cur != "running") or (action == "stop" and cur == "stopped"):
            raise ApiError(409, f"Cannot {action} while automation is {cur}", "invalid_state")
        await th(worker.set_automation_state, target)
        return jr(await th(automation_view))
    if action == "run-now":
        job, existed = await th(worker.run_now)
        return jr({"ok": True, "job": store.job_to_api(job), "already_ran_today": existed})
    raise ApiError(404, "Not found", "not_found")


@routes.put("/automation/settings")
async def au_settings(req):
    await th(settings.update_automation, await body(req))
    return jr(await th(automation_view))


@routes.get("/automation/logs")
async def au_logs(req):
    n = max(1, min(int(req.query.get("limit", 100)) if req.query.get("limit", "100").isdigit() else 100, 500))
    rows = await th(db.query, "SELECT ts,level,msg FROM syslog ORDER BY id DESC LIMIT ?", (n,))
    return jr({"logs": list(reversed(rows))})


@routes.get("/telegram")
async def tg_get(req):
    return jr(await th(notifier.info, req.query.get("refresh") == "1"))


@routes.post("/telegram/test")
async def tg_test(req):
    d = await body(req) if req.can_read_body else {}
    limit(req, "tg", 6)
    await th(notifier.test_message, d.get("text"))
    return jr({"ok": True, "sent": True})


@routes.post("/telegram/action")
async def tg_action(req):
    a = (await body(req)).get("action")
    if a not in ("daily_report", "status"):
        raise ApiError(400, "Unknown action", "invalid")
    limit(req, "tg", 6)
    if not (notifier.token() and notifier.chat_id()):
        raise LookupError("not_configured")
    ok = await th(notifier.send, notifier.daily_report() if a == "daily_report" else notifier.status_text())
    if not ok:
        raise ApiError(502, "Telegram did not accept the message", "upstream")
    return jr({"ok": True})


@routes.get("/ai")
async def ai_get(req):
    return jr(await th(providers.overview))


@routes.put("/ai")
async def ai_put(req):
    await th(settings.update_ai, await body(req))
    await th(db.audit, "admin", "ai_settings")
    return jr(await th(providers.overview))


@routes.post("/ai/test")
async def ai_test(req):
    limit(req, "aitest", 10)
    prov = (await body(req)).get("provider")
    r = await th(providers.test, prov)
    if not r.get("configured", True):
        raise ApiError(409, f"{prov} is not configured on the server", "not_configured")
    return jr({"ok": r["ok"], "latency_ms": r["latency_ms"], "error": r["error"]})


# ------------------------------------------------------------------------------------------------ settings / storage / analytics
@routes.get("/settings")
async def st_get(req):
    def work():
        return {"audit": db.query("SELECT ts,actor,action,detail FROM audit ORDER BY id DESC LIMIT 50"), "env": core.system_info()["env"], "limits": {"max_upload_mb": security.MAX_UPLOAD_BYTES // 1024 // 1024}, "version": core.VERSION}
    return jr(await th(work))


@routes.get("/storage")
async def storage(req):
    def work():
        per = [{"id": p["id"], "title": p["title"], "platform": p["platform"], "date": p["date"], "size": core.dir_size(core.PROJECTS_DIR / p["platform"] / p["date"] / str(p["id"]))}
               for p in db.query("SELECT id,title,platform,date FROM projects ORDER BY id DESC LIMIT 200")]
        pe = core.persistence()
        return {"persistent": pe["persistent"], "note": pe["note"], "data_dir_gb": round(core.dir_size(core.DATA_DIR) / 1e9, 3), "free_gb": core.disk()["free_gb"],
                "projects": per, "temp_gb": round(core.dir_size(core.WORK_ROOT) / 1e9, 3)}
    return jr(await th(work))


@routes.post("/storage/cleanup")
async def cleanup(req):
    r = await th(worker.cleanup_temp, 0)
    await th(db.audit, "admin", "storage_cleanup", str(r))
    return jr({"ok": True, **r})


@routes.get("/analytics")
async def analytics(req):
    days = max(1, min(int(req.query["days"]) if req.query.get("days", "").isdigit() else 30, 365))

    def work():
        cutoff = time.time() - days * 86400
        dd = {}
        for r in db.query("SELECT date, status, COUNT(*) n FROM projects WHERE created>=? GROUP BY date,status", (cutoff,)):
            d = dd.setdefault(r["date"], {"date": r["date"], "completed": 0, "failed": 0})
            if r["status"] in ("completed", "ready_to_publish", "published"):
                d["completed"] += r["n"]
            elif r["status"] == "failed":
                d["failed"] += r["n"]
        by_p = {}
        for p in core.PLATFORMS:
            ok = db.one("SELECT COUNT(*) n FROM projects WHERE platform=? AND status IN ('completed','ready_to_publish','published') AND created>=?", (p, cutoff))["n"]
            bad = db.one("SELECT COUNT(*) n FROM projects WHERE platform=? AND status='failed' AND created>=?", (p, cutoff))["n"]
            avg = db.one("SELECT AVG(f.duration) a FROM project_files f JOIN projects p ON p.id=f.project_id WHERE f.kind='video' AND p.platform=?", (p,))["a"]
            by_p[p] = {"completed": ok, "failed": bad, "avg_minutes": round((avg or 0) / 60, 1)}
        by_c = {r["category"]: r["n"] for r in db.query("SELECT category, COUNT(*) n FROM projects WHERE category<>'' AND created>=? GROUP BY category", (cutoff,))}
        rt = db.one("SELECT AVG(finished-started) a FROM jobs WHERE stage='render' AND status='done'")["a"]
        tt = db.one("SELECT AVG(finished-started) a FROM jobs WHERE status='done' AND started IS NOT NULL")["a"]
        fr = [{"reason": r["reason"], "count": r["n"]} for r in db.query("SELECT substr(error,1,80) reason, COUNT(*) n FROM jobs WHERE status='failed' AND error<>'' GROUP BY reason ORDER BY n DESC LIMIT 8")]
        vids = db.one("SELECT COUNT(*) n, COALESCE(SUM(duration),0) d, COALESCE(SUM(size),0) s FROM project_files WHERE kind='video'")
        return {"days": sorted(dd.values(), key=lambda x: x["date"]), "by_platform": by_p, "by_category": by_c, "durations": {"avg_render_s": round(rt or 0, 1), "avg_total_s": round(tt or 0, 1)},
                "failure_reasons": fr, "totals": {"projects": db.one("SELECT COUNT(*) n FROM projects")["n"], "videos": vids["n"], "minutes_produced": round(vids["d"] / 60, 1), "storage_mb": round(vids["s"] / 1e6, 1)}}
    return jr(await th(work))


# ------------------------------------------------------------------------------------------------ static SPA + mounting
async def spa_index(req):
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


async def spa_file(req):
    rel = req.match_info["path"]
    p = (STATIC / rel).resolve()
    if not core.is_within(p, STATIC.resolve()) or not p.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(p, headers={"Cache-Control": "no-cache"})


async def root_redirect(req):
    raise web.HTTPFound("/studio/")


def build_api_app() -> web.Application:
    app = web.Application(middlewares=[headers_mw, guard], client_max_size=security.MAX_UPLOAD_BYTES + 1024 * 1024)
    app.add_routes(routes)
    return app


def mount(app: web.Application, start_engine=True):
    """Attach the studio to an existing aiohttp app (the Telegram bot's web server)."""
    db.migrate()
    core.configure()
    core.setup_logging()
    app.add_subapp("/api", build_api_app())
    static = web.Application(middlewares=[headers_mw])
    static.router.add_get("/", spa_index)
    static.router.add_get("/{path:.+}", spa_file)
    app.add_subapp("/studio", static)
    app.router.add_get("/", root_redirect)
    if start_engine:
        async def _start(_):
            await asyncio.to_thread(worker.engine.start)

        async def _stop(_):
            await asyncio.to_thread(worker.engine.stop)
        app.on_startup.append(_start)
        app.on_cleanup.append(_stop)
    return app
