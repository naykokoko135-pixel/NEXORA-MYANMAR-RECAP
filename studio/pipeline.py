"""The ten pipeline stages. Each stage is idempotent: it recomputes only what is missing/invalidated and records real outputs.

research -> script -> voice -> srt -> assets -> timeline -> render -> qc -> publish -> notify

A stage raises ``StageError(recoverable=...)``. Recoverable errors (network, quota, transient ffmpeg) are retried by the worker with
backoff; non-recoverable ones (unverifiable title, invalid script) fail the job at once so a human can change the input.
Nothing here marks a video "completed"/"published" unless the file exists and passed QC / the platform API answered.
"""
import json
import re
import shutil
import time
from pathlib import Path

from .. import config, render as base, research as research_mod, script as script_mod, subs
from . import assets as assets_mod, core, notifier, publisher, qcx, renderer, settings, store, voice
from . import providers

INDIA = {"hi", "ta", "te", "ml", "kn", "bn", "mr", "pa", "ur", "gu", "IN"}
NEXT_STAGE = {s: core.STAGES[i + 1] for i, s in enumerate(core.STAGES[:-1])}
# outputs produced by a stage (used to invalidate downstream work when an earlier stage is re-run)
STAGE_OUTPUTS = {"research": ["source"], "script": ["script", "script_txt"], "voice": ["audio_mp3", "audio_wav", "cues"], "srt": ["srt_en", "srt_my"],
                 "timeline": ["scenes"], "render": ["video"], "qc": ["qc"], "publish": ["metadata", "credits"]}


class StageError(RuntimeError):
    def __init__(self, msg, recoverable=True):
        super().__init__(msg)
        self.recoverable = recoverable


class Cancelled(Exception):
    pass


class Ctx:
    """Everything a stage needs: the project, a logger bound to the job, progress + cancellation hooks."""

    def __init__(self, job, project_id, check_cancel, render_slot=None):
        self.job, self.pid = job, project_id
        self.check_cancel = check_cancel
        self.render_slot = render_slot
        self.row = store.get_row(project_id)
        self.cfg = json.loads(self.row["config_json"] or "{}")
        self.platform = self.row["platform"]

    def log(self, msg, level="info"):
        store.joblog(self.job["id"], level, msg)
        core.log.info(msg, extra={"job": self.job["id"], "project": self.pid})

    def progress(self, frac, step=""):
        store.set_job_progress(self.job["id"], max(0.0, min(1.0, frac)) * 100, step)
        i = core.STAGES.index(self.job["stage"])
        store.update_project(self.pid, progress=round((i + max(0.0, min(1.0, frac))) / len(core.STAGES) * 100, 1))


# ------------------------------------------------------------------------------------------------ research
def validate_source(src: dict, platform: str) -> list[dict]:
    """Concrete, user-visible checks. A title is accepted only when every check passes."""
    cat, country = src.get("category") or "", str(src.get("country") or "")
    genres = [str(g).lower() for g in (src.get("genres") or [])]
    animated = "16" in genres or "animation" in genres or src.get("hint") == "anime" or src.get("catalog") in ("AniList", "Jikan/MyAnimeList", "Blender Open Movies")
    checks = [
        {"name": "not an Indian title", "ok": country not in INDIA, "detail": f"origin: {country or 'unknown'}"},
        {"name": "category is allowed", "ok": cat in core.CATEGORIES, "detail": cat or "missing"},
        {"name": "Wikipedia source found", "ok": bool(src.get("wiki_url")), "detail": src.get("wiki_url") or "no article"},
        {"name": "enough factual source text", "ok": len(src.get("plot", "")) >= 600 and
            len(src.get("plot", "")) + len(src.get("intro", "")) + sum(len(v) for v in (src.get("extras") or {}).values()) >= config.PLATFORMS[platform]["min_source"],
         "detail": f"plot {len(src.get('plot', ''))} chars"},
    ]
    if cat == "Donghua":
        checks.append({"name": "Donghua is Chinese-origin", "ok": country in ("CN", "zh", "TW", "HK"), "detail": country})
    if cat == "Anime":
        checks.append({"name": "Anime is Japanese-origin", "ok": country in ("JP", "ja"), "detail": country})
    if cat in ("3D Animation", "Cartoon", "Anime", "Donghua"):
        checks.append({"name": "animated work (not live-action)", "ok": animated, "detail": "genre/catalog says animation" if animated else "no animation genre"})
    if cat == "International Movies":
        checks.append({"name": "live-action category excludes animation", "ok": "16" not in genres and "animation" not in genres, "detail": ""})
    return checks


def source_view(src: dict, platform: str, source_id: str = "") -> dict:
    checks = validate_source(src, platform)
    ok = all(c["ok"] for c in checks)
    status = "verified" if ok else ("excluded" if not checks[0]["ok"] else "insufficient_sources")
    refs = [{"name": "Wikipedia", "url": src.get("wiki_url", "")}] if src.get("wiki_url") else []
    if src.get("url"):
        refs.insert(0, {"name": src.get("catalog") or "Catalog", "url": src["url"]})
    return {"verified": ok, "status": status, "title": src.get("title"), "original_title": src.get("alt") or src.get("title"), "year": src.get("year"),
            "country": src.get("country"), "category": src.get("category"), "genres": [g for g in src.get("genres", []) if isinstance(g, str)],
            "wiki_url": src.get("wiki_url"), "plot_chars": len(src.get("plot", "")), "sources": refs, "views_30d": src.get("views", 0),
            "checks": checks, "source_id": source_id}


def stage_research(ctx: Ctx):
    src = store.research_of(ctx.pid)
    if not src or not src.get("plot"):
        ctx.log(f"Resolving '{ctx.row['title']}' against catalogs + Wikipedia")
        try:
            src = research_mod.resolve_title(ctx.row["title"], ctx.platform, ctx.log)
        except Exception as e:
            raise StageError(f"Research failed: {e}", recoverable=_is_network(e))
        if ctx.row["category"]:
            src["category"] = ctx.row["category"]
    ctx.check_cancel()
    view = source_view(src, ctx.platform)
    bad = [c for c in view["checks"] if not c["ok"]]
    if bad:
        raise StageError("Title rejected: " + "; ".join(f"{c['name']} ({c['detail']})" for c in bad), recoverable=False)
    src["source_refs"] = view["sources"]
    store.set_research(ctx.pid, src)
    store.write_json_file(ctx.pid, "source", "source.json", {k: v for k, v in view.items()} | {"fetched": time.time()})
    ctx.log(f"Verified: {src['title']} ({src.get('year')}) [{src.get('category')}] from {', '.join(src.get('sources', []))}")
    ctx.progress(1.0, "verified")


# ------------------------------------------------------------------------------------------------ script
def script_doc(pid: int) -> dict | None:
    return store.read_json_file(pid, "script")


def script_stats(sections) -> dict:
    items = [it for s in sections for it in s.get("items", [])]
    chars = sum(len(i.get("my", "")) for i in items)
    return {"sentences": len(items), "my_chars": chars, "est_minutes": round(chars / config.CHARS_PER_SEC / 60, 1)}


def save_script(pid: int, sections, provider=None, edited=False) -> dict:
    row = store.get_row(pid)
    doc = {"sections": sections, "provider": provider, "edited": edited, "saved": time.time()}
    store.write_json_file(pid, "script", "script.json", doc)
    txt = store.project_path(pid) / "script_my.txt"
    txt.write_text("\n\n".join(f"{s['title']}\n" + " ".join(i["my"] for i in s["items"]) for s in sections), "utf-8")
    store.save_file(pid, "script_txt", txt)
    return doc


def validate_sections(sections) -> list:
    if not isinstance(sections, list) or not sections or len(sections) > 60:
        raise ValueError("sections must be a list of 1-60 sections")
    out = []
    for s in sections:
        if not isinstance(s, dict) or not isinstance(s.get("items"), list):
            raise ValueError("each section needs a title and items")
        items = []
        for it in s["items"]:
            my, en = str((it or {}).get("my", "")).strip(), str((it or {}).get("en", "")).strip()
            if not my:
                continue
            if len(my) > 800 or len(en) > 600:
                raise ValueError("a sentence is too long (max 800 Burmese / 600 English characters)")
            items.append({"my": my, "en": en})
        if items:
            out.append({"title": str(s.get("title", "Part"))[:120], "kind": str(s.get("kind", "story"))[:20], "items": items})
    if not out:
        raise ValueError("script has no sentences")
    return out


def stage_script(ctx: Ctx):
    doc = script_doc(ctx.pid)
    if doc and doc.get("sections"):
        ctx.log("Script already exists" + (" (manually edited)" if doc.get("edited") else "") + "; keeping it")
        ctx.progress(1.0, "script ready")
        return
    src = store.research_of(ctx.pid)
    if not src:
        raise StageError("No verified research for this project; run the research stage first", recoverable=False)
    providers.install_script_hook()
    ctx.log(f"Generating Burmese script (~{ctx.cfg['target_min']} min) with AI provider router")
    try:
        sections = script_mod.generate(src, ctx.platform, ctx.cfg["target_min"], ctx.log)
    except providers.ProviderError as e:
        raise StageError(str(e), recoverable=e.kind != "not_configured" and e.kind != "auth")
    except Exception as e:
        raise StageError(f"Script generation failed: {e}", recoverable=_is_network(e))
    ctx.check_cancel()
    q = qcx.check_script(sections, ctx.platform)
    if not q["ok"]:
        raise StageError("Script QC failed: " + "; ".join(q["issues"]), recoverable=True)
    st = providers.stats()
    last = max(st.items(), key=lambda kv: kv[1].get("last_ok") or 0)[0] if st else None
    save_script(ctx.pid, sections, provider=last)
    ctx.log(f"Script saved: {q['sentences']} sentences" + (f"; warnings: {'; '.join(q['warnings'])}" if q["warnings"] else ""))
    ctx.progress(1.0, "script saved")


# ------------------------------------------------------------------------------------------------ voice / srt
def _profile(name: str):
    if not name:
        return None
    from .. import voices
    return voices.get_profile(name)


def stage_voice(ctx: Ctx):
    mp3, cues = store.file_path(ctx.pid, "audio_mp3"), store.read_json_file(ctx.pid, "cues")
    if mp3 and cues:
        ctx.log("Narration already exists; keeping it")
        ctx.progress(1.0, "narration ready")
        return
    doc = script_doc(ctx.pid)
    if not doc:
        raise StageError("No script to narrate", recoverable=False)
    sections = doc["sections"]
    P = config.PLATFORMS[ctx.platform]
    vs = settings.voice_settings()
    pdir, wd = store.project_path(ctx.pid), core.work_dir(ctx.pid) / "tts"
    out_mp3, out_wav = pdir / "narration.mp3", (pdir / "narration.wav") if ctx.cfg.get("export_wav") else None
    profile = _profile(ctx.cfg.get("voice_profile") or "")
    src = store.research_of(ctx.pid)
    res = None
    for attempt in range(4):
        shutil.rmtree(wd, ignore_errors=True)
        try:
            res = voice.build_narration(sections, ctx.cfg["voice"], profile, wd, out_mp3, out_wav, user_rate=vs["rate"], user_pitch=vs["pitch"],
                                        log=ctx.log, progress=lambda f: ctx.progress(0.9 * f, "synthesizing narration"), check_cancel=ctx.check_cancel)
        except voice.VoiceError as e:
            raise StageError(str(e), recoverable=True)
        dur = res["duration"]
        if P["min"] * 60 <= dur <= P["max"] * 60:
            break
        if dur < P["min"] * 60:
            need = P["min"] * 60 + 20 - dur
            ctx.log(f"Narration is {dur / 60:.1f} min < {P['min']} min; adding analysis sections from the verified source ({need:.0f}s needed)")
            added = 0
            try:
                providers.install_script_hook()
                added = script_mod.extend(src, ctx.platform, sections, need, ctx.log) if src else 0
            except Exception as e:
                ctx.log(f"Could not extend script: {str(e)[:150]}", "warn")
            if not added:
                break
            save_script(ctx.pid, sections, provider=doc.get("provider"), edited=doc.get("edited", False))
        else:
            while dur > P["max"] * 60 and len(sections) > 3:
                sections.pop(-2)
                dur -= 60  # rough; real duration is re-measured on the next loop
            save_script(ctx.pid, sections, provider=doc.get("provider"), edited=doc.get("edited", False))
            ctx.log("Narration longer than the platform maximum; trimmed middle sections and re-synthesizing")
    if not res or not (P["min"] * 60 <= res["duration"] <= P["max"] * 60):
        got = f"{res['duration'] / 60:.1f} min" if res else "none"
        raise StageError(f"Narration length ({got}) is outside {ctx.platform}'s {P['min']}-{P['max']} min range and the verified source is too thin to extend honestly. "
                         "Pick a title with more source material or edit the script.", recoverable=False)
    store.save_file(ctx.pid, "audio_mp3", out_mp3, res["duration"])
    if out_wav is not None and out_wav.exists():
        store.save_file(ctx.pid, "audio_wav", out_wav, res["duration"])
    store.write_json_file(ctx.pid, "cues", "cues.json", {"cues": res["timeline"], "duration": res["duration"], "engine": res["engine"], "quality": res["quality"],
                                                           "voice": res["voice"], "notes": res["notes"]})
    shutil.rmtree(wd, ignore_errors=True)
    a = qcx.check_audio(out_mp3, ctx.platform, res["duration"])
    for w in a.get("warnings", []):
        ctx.log("Audio warning: " + w, "warn")
    if not a["ok"]:
        raise StageError("Audio QC failed: " + "; ".join(a["issues"]), recoverable=False)
    ctx.log(f"Narration {res['duration'] / 60:.2f} min via {res['engine']} ({res['quality']} quality)" + (f"; notes: {'; '.join(res['notes'])}" if res["notes"] else ""))
    ctx.progress(1.0, "narration ready")


def cues_doc(pid: int) -> dict | None:
    return store.read_json_file(pid, "cues")


def write_srts(pid: int, cues, langs=("en", "my")) -> dict:
    pdir = store.project_path(pid)
    rep = {}
    for lang in langs:
        p = pdir / f"subtitles_{lang}.srt"
        timeline = [{"start": c["start"], "end": c["end"], "en": c.get("en") or c.get("my", ""), "my": c.get("my", "")} for c in cues]
        rep[lang] = subs.write_srt(timeline, p, lang)
        store.save_file(pid, f"srt_{lang}", p, None)
    return rep


def stage_srt(ctx: Ctx):
    cd = cues_doc(ctx.pid)
    if not cd:
        raise StageError("No narration timing available for subtitles", recoverable=False)
    langs = [l for l in ctx.cfg.get("srt_langs", ["en", "my"]) if l in ("en", "my")] or ["en"]
    if "en" not in langs and ctx.cfg.get("burn_subs") == "en":
        langs.append("en")
    rep = write_srts(ctx.pid, cd["cues"], langs)
    q = qcx.check_subtitles({l: store.file_path(ctx.pid, f"srt_{l}") for l in langs}, cd["duration"])
    if not q["ok"]:
        raise StageError("Subtitle QC failed: " + "; ".join(q["issues"]), recoverable=False)
    ctx.log("SRT written: " + ", ".join(f"{l} {r['cues']} cues" for l, r in rep.items()))
    ctx.progress(1.0, "subtitles ready")


# ------------------------------------------------------------------------------------------------ assets / timeline
def stage_assets(ctx: Ctx):
    if not ctx.cfg.get("use_assets", True):
        ctx.log("Visual assets disabled for this project: using self-generated graphics")
        return
    existing = assets_mod.list_assets(ctx.pid)
    if existing:
        ctx.log(f"{len(existing)} authorised asset(s) already attached")
        return
    try:
        got = assets_mod.auto_collect(ctx.pid, ctx.row["title"], ctx.row["year"], limit=8, log=ctx.log)
    except Exception as e:
        # Visuals are optional: the renderer has a legal self-generated fallback, so this must not block the video.
        ctx.log(f"Authorised asset search unavailable ({str(e)[:120]}); continuing with self-generated graphics", "warn")
        return
    ctx.log(f"{len(got)} licence-verified asset(s) attached" if got else "No relevant licence-verified assets found; using self-generated graphics")
    ctx.progress(1.0, "assets done")


def build_scenes(pid: int) -> dict:
    cd = cues_doc(pid)
    if not cd:
        raise StageError("No narration timing for the scene timeline", recoverable=False)
    timeline = [{"start": c["start"], "end": c["end"], "my": c.get("my", ""), "en": c.get("en", ""), "sec": c.get("sec", 0)} for c in cd["cues"]]
    scenes = base.make_scenes(timeline)
    usable = [a for a in assets_mod.list_assets(pid) if a["verified"] and a["local_path"]]
    doc = script_doc(pid)
    titles = [s["title"] for s in (doc or {}).get("sections", [])]
    for i, sc in enumerate(scenes):
        sc["section"] = sc.pop("sec", 0)
        sc["label"] = titles[sc["section"]] if sc["section"] < len(titles) else ""
        sc["asset_id"] = usable[i % len(usable)]["id"] if usable else None
        sc["i"] = i
    return {"scenes": scenes, "total": scenes[-1]["end"] if scenes else 0.0, "has_scenes": bool(scenes)}


def stage_timeline(ctx: Ctx):
    tl = build_scenes(ctx.pid)
    store.write_json_file(ctx.pid, "scenes", "scenes.json", tl)
    ctx.log(f"Scene timeline: {len(tl['scenes'])} scenes over {tl['total'] / 60:.1f} min" +
            (f", {len({s['asset_id'] for s in tl['scenes'] if s['asset_id']})} authorised image(s)" if any(s["asset_id"] for s in tl["scenes"]) else ", self-generated graphics"))
    ctx.progress(1.0, "timeline ready")


# ------------------------------------------------------------------------------------------------ render / qc
def _asset_map(pid: int) -> dict:
    out = {}
    for r in assets_mod.db.query("SELECT * FROM source_assets WHERE project_id=? AND verified=1", (pid,)):
        if r["local_path"] and Path(r["local_path"]).exists():
            out[r["id"]] = {"path": r["local_path"], "title": r["title"], "attribution": r["attribution"], "license": r["license"], "attribution_required": bool(r["attribution_required"])}
    return out


def stage_render(ctx: Ctx):
    existing = store.file_path(ctx.pid, "video")
    if existing:
        ctx.log("Video already rendered; keeping it")
        return
    tl = store.read_json_file(ctx.pid, "scenes")
    cd, srt = cues_doc(ctx.pid), store.file_path(ctx.pid, "srt_en")
    mp3 = store.file_path(ctx.pid, "audio_mp3")
    if not (tl and tl.get("scenes") and cd and mp3):
        raise StageError("Missing timeline/narration for rendering", recoverable=False)
    W, H = core.output_size(ctx.cfg["format"], ctx.cfg["resolution"])
    burn = ctx.cfg.get("burn_subs") == "en" and srt is not None
    wd = core.work_dir(ctx.pid) / "render"
    shutil.rmtree(wd, ignore_errors=True)
    out = store.project_path(ctx.pid) / f"{ctx.platform}_{re.sub(r'[^a-z0-9]+', '-', ctx.row['title'].lower()).strip('-')[:40] or 'video'}_{ctx.row['date']}.mp4"
    if burn:
        wd.mkdir(parents=True, exist_ok=True)
        shutil.copy(srt, wd / "subs.srt")
    ctx.log(f"Rendering {W}x{H} H.264/AAC MP4 ({len(tl['scenes'])} scenes); waiting for render slot")
    from . import worker
    with worker.render_slot:
        ctx.check_cancel()
        ctx.log("Render slot acquired")
        try:
            meta = renderer.render(tl["scenes"], mp3, (wd / "subs.srt") if burn else None, out, title=ctx.row["title"], channel=config.CHANNEL_NAME, W=W, H=H, workdir=wd,
                                   burn_subs=burn, assets=_asset_map(ctx.pid), progress=lambda f, s="": ctx.progress(f, s or "rendering"),
                                   run=worker.cancellable_run(ctx), cancel=ctx.check_cancel, workers=2, log=ctx.log)
        except Cancelled:
            raise
        except Exception as e:
            out.unlink(missing_ok=True)
            raise StageError(f"Render failed: {e}", recoverable=True)
    shutil.rmtree(wd, ignore_errors=True)
    store.save_file(ctx.pid, "video", out, core.ffprobe_duration(out))
    ctx.log(f"Rendered {out.name}: {out.stat().st_size / 1e6:.1f} MB in {meta['seconds']}s")


def stage_qc(ctx: Ctx):
    v = store.file_path(ctx.pid, "video")
    cd = cues_doc(ctx.pid)
    if not v:
        raise StageError("No video to check", recoverable=False)
    W, H = core.output_size(ctx.cfg["format"], ctx.cfg["resolution"])
    q = qcx.check_video(v, ctx.platform, W, H, expect_duration=cd["duration"] if cd else None)
    sc = qcx.check_script((script_doc(ctx.pid) or {}).get("sections", []), ctx.platform)
    report = {"video": q, "script": sc, "checked": time.time()}
    store.write_json_file(ctx.pid, "qc", "qc.json", report)
    if not q["ok"]:
        store.invalidate_kinds(ctx.pid, ["video"])  # a failed video must not be left looking finished
        raise StageError("Video QC failed: " + "; ".join(q["issues"]), recoverable=True)
    ctx.log(f"Video QC passed: {q['duration_min']} min, {q['width']}x{q['height']}, {q['codec']}, {q['size_mb']} MB, fully decoded={q['fully_decoded']}")
    ctx.progress(1.0, "qc passed")


# ------------------------------------------------------------------------------------------------ publish / notify
def stage_publish(ctx: Ctx):
    v = store.file_path(ctx.pid, "video")
    if not v:
        raise StageError("No video to publish", recoverable=False)
    project = store.get_project(ctx.pid, with_files=False)
    credits = [a for a in assets_mod.list_assets(ctx.pid) if a["verified"]]
    used = {s["asset_id"] for s in (store.read_json_file(ctx.pid, "scenes") or {}).get("scenes", []) if s.get("asset_id")}
    credits = [a for a in credits if a["id"] in used]
    meta = publisher.build_metadata(project, store.research_of(ctx.pid), credits, ctx.cfg)
    mode = settings.effective_publish_mode(ctx.cfg.get("publish_mode", "draft"))
    res = publisher.publish(project, v, meta, mode, ctx.log)
    store.write_json_file(ctx.pid, "metadata", "publish.json", res)
    store.write_json_file(ctx.pid, "credits", "credits.json", {"credits": credits})
    ctx.log(f"Publish: {res['status']} — {res['detail'][:160]}")
    if res["status"] == "failed":
        store.raise_alert(f"publish_{ctx.platform}", "warn", f"{ctx.platform} upload failed; draft prepared: {res['detail'][:140]}")
    else:
        store.clear_alert(f"publish_{ctx.platform}")
    ctx.progress(1.0, res["status"])


def stage_notify(ctx: Ctx):
    pub = store.read_json_file(ctx.pid, "metadata", {}) or {}
    status = "published" if pub.get("status") in ("uploaded", "verified") else "ready_to_publish"
    store.update_project(ctx.pid, status=status, stage="notify", progress=100, error="")
    v = store.file_path(ctx.pid, "video")
    qc = (store.read_json_file(ctx.pid, "qc", {}) or {}).get("video", {})
    msg = (f"✅ {ctx.platform.title()} recap ready: {ctx.row['title']}\n{qc.get('duration_min', '?')} min • {qc.get('width')}x{qc.get('height')} • {qc.get('size_mb', '?')} MB • QC passed\n"
           f"Publish: {pub.get('status', 'n/a')}" + (f" {pub.get('url')}" if pub.get("url") else " (draft — upload manually)"))
    sent = notifier.send(msg)
    if v and v.stat().st_size < 49 * 1024 * 1024:
        sent = notifier.send_file(v, ctx.row["title"][:200]) or sent
    ctx.log("Telegram notification sent" if sent else "Telegram not configured or unreachable; notification skipped", "info" if sent else "warn")
    ctx.progress(1.0, "done")


STAGE_FUNCS = {"research": stage_research, "script": stage_script, "voice": stage_voice, "srt": stage_srt, "assets": stage_assets,
               "timeline": stage_timeline, "render": stage_render, "qc": stage_qc, "publish": stage_publish, "notify": stage_notify}


def _is_network(e: Exception) -> bool:
    s = f"{type(e).__name__} {e}".lower()
    return any(k in s for k in ("timeout", "connection", "temporarily", "502", "503", "504", "429", "reset", "network", "unreachable", "max retries", "proxy"))
