"""Acceptance harness: runs ONE complete recap through the real engine and verifies the output files.

    python serve_acceptance.py                       # live: real research + real AI provider (needs internet + OPENAI/GEMINI key)
    python serve_acceptance.py --offline-fixture     # sandbox: research + script text come from studio/acceptance_fixture.py

Everything else is the production code path: automation Start -> scheduler/planner job -> per-platform queue -> TTS -> SRT -> asset search ->
scene timeline -> ffmpeg render -> QC -> publish draft -> notification logic. The report states exactly which inputs were fixtures.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", default="tiktok", choices=["youtube", "facebook", "tiktok"])
    ap.add_argument("--offline-fixture", action="store_true", help="use the labelled fixture for research + script (no internet/AI key)")
    ap.add_argument("--data-dir", default="")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--report", default="")
    a = ap.parse_args(argv)

    root = Path(a.data_dir) if a.data_dir else Path(tempfile.mkdtemp(prefix="nexora-accept-"))
    os.environ.update({"DATA_DIR": str(root / "data"), "WORK_DIR": str(root / "work"), "OUT_DIR": str(root / "out"), "STATE_DIR": str(root / "state"),
                       "VOICE_PROFILE_DB_PATH": str(root / "voices")})
    if a.offline_fixture:
        os.environ["NEXORA_TTS_ENGINES"] = "espeak"  # no internet TTS in an offline sandbox
    from nexora import research as research_mod, script as script_mod
    from nexora.studio import acceptance_fixture as fx, core, db, pipeline, qcx, settings, store, worker

    core.configure(data_dir=root / "data", work_dir=root / "work" / "studio")
    db.migrate()
    fixtures = []
    if a.offline_fixture:
        def fake_pick(platform, taken_cats=(), taken_titles=(), date=None, log=print):
            log("[FIXTURE] research.pick -> Big Buck Bunny (offline sandbox; no catalog/Wikipedia access)")
            return dict(fx.SRC)

        research_mod.pick = fake_pick
        script_mod.generate = lambda src, platform, target_min=None, log=print: (log("[FIXTURE] script.generate -> Burmese text from acceptance_fixture.py"), fx.sections())[1]
        fixtures = ["research (catalog + Wikipedia)", "Burmese script generation (AI provider)"]

    settings.update_automation({"platforms": {p: p == a.platform for p in core.PLATFORMS}, "schedule": "00:00", "retry": {"max_attempts": 2, "backoff_s": 2}})
    settings.set_platform(a.platform, {"resolution": "720p", "publish_mode": "draft"})
    worker.engine.start()
    t0 = time.time()
    worker.set_automation_state("running")          # one-click Start Auto Mode (schedule 00:00 is already due, so the planner job is queued)
    job, existed = worker.run_now()                 # idempotent: returns the same job if the scheduler already queued it
    print(f"automation started; daily job #{job['id']} (already queued: {existed})", flush=True)

    seen, proj = 0, None
    while time.time() - t0 < a.timeout:
        time.sleep(3)
        row = db.one("SELECT * FROM projects WHERE platform=? AND origin='auto' ORDER BY id DESC LIMIT 1", (a.platform,))
        if row:
            proj = row
            for j in store.list_jobs(project_id=row["id"], limit=50)[::-1]:
                for l in store.job_logs(j["id"]):
                    pass
            logs = store.project_logs(row["id"], 2000)
            for l in logs[seen:]:
                print(f"  [{l['stage']}] {l['msg'][:140]}", flush=True)
            seen = len(logs)
            if row["status"] in ("ready_to_publish", "published", "failed", "cancelled"):
                break
        else:
            sj = store.get_job(job["id"])
            if sj["status"] == "failed":
                print("planner failed:", sj["error"])
                break
    elapsed = time.time() - t0
    worker.set_automation_state("stopped")
    worker.engine.stop()

    report = {"mode": "offline-fixture" if a.offline_fixture else "live", "fixture_inputs": fixtures, "platform": a.platform, "elapsed_s": round(elapsed, 1), "data_dir": str(root), "checks": []}
    ok = False
    if proj:
        pid = proj["id"]
        proj = store.get_row(pid)
        report.update(project_id=pid, title=proj["title"], status=proj["status"], error=proj["error"])
        files = {f["kind"]: f for f in store.list_files(pid, include_internal=True)}
        report["files"] = {k: {"name": f["name"], "size": f["size"], "duration": f["duration"]} for k, f in files.items()}
        v = store.file_path(pid, "video")
        if v:
            W, H = core.output_size(json.loads(proj["config_json"])["format"], json.loads(proj["config_json"])["resolution"])
            q = qcx.check_video(v, a.platform, W, H)
            report["video_qc"] = q
            info = qcx.probe(v)
            report["ffprobe"] = {"format": info["format"].get("format_name"), "duration_s": float(info["format"]["duration"]), "size_bytes": int(info["format"]["size"]),
                                 "streams": [{k: s.get(k) for k in ("codec_type", "codec_name", "width", "height", "profile", "pix_fmt", "sample_rate", "channels")} for s in info["streams"]]}
            report["path"] = str(v)
        need = ["source", "script", "script_txt", "audio_mp3", "srt_en", "srt_my", "scenes", "video", "qc", "metadata"]
        report["missing_outputs"] = [k for k in need if k not in files]
        publish = store.read_json_file(pid, "metadata", {}) or {}
        report["publish"] = {"status": publish.get("status"), "detail": publish.get("detail")}
        cues = store.read_json_file(pid, "cues", {}) or {}
        report["narration"] = {k: cues.get(k) for k in ("engine", "quality", "voice", "duration", "notes")}
        ok = (proj["status"] in ("ready_to_publish", "published") and bool(v) and not report["missing_outputs"] and report.get("video_qc", {}).get("ok", False))
    report["passed"] = ok
    out = Path(a.report) if a.report else root / "acceptance_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), "utf-8")
    print(json.dumps({k: report.get(k) for k in ("mode", "fixture_inputs", "status", "elapsed_s", "passed", "missing_outputs", "path", "error")}, ensure_ascii=False, indent=1))
    print("report:", out)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
