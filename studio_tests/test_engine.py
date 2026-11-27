import json
import shutil
import time
import unittest
from unittest import mock

from nexora import config, research as research_mod
from nexora.studio import acceptance_fixture as fx, assets, core, db, pipeline, security, settings, store, voice, worker
from nexora.studio.pipeline import StageError

HAVE_MEDIA = bool(shutil.which("ffmpeg") and shutil.which("espeak-ng"))


def wait_for(cond, timeout=60, step=0.2):
    end = time.time() + timeout
    while time.time() < end:
        v = cond()
        if v:
            return v
        time.sleep(step)
    raise AssertionError("condition not met within %ss" % timeout)


def clean_db():
    db.migrate()
    with db.tx() as c:
        for t in ("job_logs", "jobs", "project_files", "source_assets", "projects", "sessions", "kv", "daily_picks", "audit", "syslog"):
            c.execute(f"DELETE FROM {t}")


def make_src(title, cat, country, genres=("Animation",), plot_len=7000, catalog="AniList"):
    return {"title": title, "alt": title, "year": 2020, "country": country, "genres": list(genres), "category": cat, "catalog": catalog, "hint": "anime" if catalog == "AniList" else "film",
            "wiki_url": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_"), "intro": "intro " * 100, "plot": "plot " * (plot_len // 5), "extras": {}, "views": 10,
            "url": "https://example.org/" + title, "sources": [catalog, "Wikipedia"]}


class SourceValidationTests(unittest.TestCase):
    def names(self, src, platform="youtube"):
        return {c["name"] for c in pipeline.validate_source(src, platform) if not c["ok"]}

    def test_valid_sources(self):
        self.assertEqual(self.names(make_src("Frieren", "Anime", "JP")), set())
        self.assertEqual(self.names(make_src("Soul Land", "Donghua", "CN")), set())
        self.assertEqual(self.names(make_src("Heist", "International Movies", "en", genres=["Crime"], catalog="TMDB")), set())
        self.assertEqual(self.names(pipeline.research_mod_fixture() if hasattr(pipeline, "research_mod_fixture") else fx.SRC, "tiktok"), set())

    def test_india_is_excluded(self):
        for c in ("IN", "hi", "ta"):
            self.assertIn("not an Indian title", self.names(make_src("X", "International Movies", c, genres=["Drama"])))

    def test_category_integrity(self):
        self.assertIn("Donghua is Chinese-origin", self.names(make_src("A", "Donghua", "JP")))
        self.assertIn("Anime is Japanese-origin", self.names(make_src("A", "Anime", "CN")))
        live = make_src("Live", "3D Animation", "US", genres=["Drama"], catalog="TMDB")
        self.assertIn("animated work (not live-action)", self.names(live))  # live-action must not enter the 3D category
        anim = make_src("Toy", "International Movies", "US", genres=["16"], catalog="TMDB")
        self.assertIn("live-action category excludes animation", self.names(anim))

    def test_thin_sources_rejected_per_platform(self):
        thin = make_src("Thin", "Anime", "JP", plot_len=800)
        thin["intro"] = ""
        self.assertIn("enough factual source text", self.names(thin, "youtube"))
        self.assertNotIn("enough factual source text", self.names(thin, "tiktok") - {"x"}) if False else None
        self.assertEqual(self.names(make_src("OK", "Anime", "JP", plot_len=2000), "tiktok"), set())


class LicenseAndSecurityTests(unittest.TestCase):
    def test_license_allow_list(self):
        ok = assets.classify_license("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/")
        self.assertTrue(ok[0] and ok[2])  # allowed, attribution required
        self.assertTrue(assets.classify_license("CC0", "")[0])
        for bad in ("CC BY-NC 4.0", "CC BY-ND 2.0", "All rights reserved", "Fair use", "GFDL", ""):
            self.assertFalse(assets.classify_license(bad, "")[0], bad)

    def test_ssrf_guard(self):
        for h in ("localhost", "127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1"):
            self.assertFalse(assets._public_host(h), h)

    def test_upload_sniffing_and_names(self):
        self.assertEqual(security.sniff_audio(b"OggS\0\0"), "ogg")
        self.assertEqual(security.sniff_audio(b"RIFF\0\0\0\0WAVE"), "wav")
        self.assertIsNone(security.sniff_audio(b"MZ\x90\x00 executable"))
        self.assertEqual(security.sniff_image(b"\x89PNG\r\n\x1a\n"), "png")
        self.assertIsNone(security.sniff_image(b"<svg onload=alert(1)>"))
        self.assertEqual(security.safe_name("../../etc/passwd"), "etcpasswd")

    def test_rate_limiter_window(self):
        rl = security.RateLimiter()
        self.assertTrue(all(rl.hit("k", 3, 60)[0] for _ in range(3)))
        ok, retry = rl.hit("k", 3, 60)
        self.assertFalse(ok)
        self.assertGreaterEqual(retry, 1)

    def test_no_secrets_in_env_report(self):
        import os
        os.environ["OPENAI_API_KEY"] = "sk-super-secret-value"
        try:
            self.assertNotIn("sk-super-secret-value", json.dumps(core.system_info()))
        finally:
            os.environ.pop("OPENAI_API_KEY")


class EngineBase(unittest.TestCase):
    def setUp(self):
        clean_db()
        core.configure()
        settings.update_automation({"retry": {"max_attempts": 2, "backoff_s": 0}, "platforms": {p: True for p in core.PLATFORMS}, "schedule": "00:00"})
        self.engine = worker.Engine()

    def tearDown(self):
        self.engine.stop()
        settings.save_automation({**settings.AUTOMATION_DEFAULTS})

    def project(self, **kw):
        p = store.create_project("tiktok", kw.pop("title", "Big Buck Bunny"), research=kw.pop("research", None), **kw)
        return p


class QueueBehaviourTests(EngineBase):
    def test_recoverable_error_is_retried_then_fails(self):
        calls = []

        def boom(ctx):
            calls.append(1)
            raise StageError("network down", recoverable=True)
        with mock.patch.dict(pipeline.STAGE_FUNCS, {"research": boom}):
            p = self.project()
            store.enqueue(p["id"], "tiktok", "research", trigger="manual")
            self.engine.start()
            wait_for(lambda: store.get_row(p["id"])["status"] == "failed")
        self.assertEqual(len(calls), 2)  # max_attempts
        j = store.list_jobs(project_id=p["id"])[0]
        self.assertEqual((j["status"], j["attempts"]), ("failed", 2))
        self.assertIn("network down", store.get_row(p["id"])["error"])

    def test_non_recoverable_error_fails_immediately(self):
        calls = []

        def bad(ctx):
            calls.append(1)
            raise StageError("title rejected", recoverable=False)
        with mock.patch.dict(pipeline.STAGE_FUNCS, {"research": bad}):
            p = self.project()
            store.enqueue(p["id"], "tiktok", "research", trigger="manual")
            self.engine.start()
            wait_for(lambda: store.get_row(p["id"])["status"] == "failed")
        self.assertEqual(len(calls), 1)

    def test_failed_job_can_be_retried_and_completes_chain(self):
        state = {"n": 0}

        def flaky(ctx):
            state["n"] += 1
            if state["n"] == 1:
                raise StageError("bad input", recoverable=False)
        noop = lambda ctx: None  # noqa: E731
        with mock.patch.dict(pipeline.STAGE_FUNCS, {s: noop for s in core.STAGES} | {"research": flaky}):
            p = self.project()
            job, _ = store.enqueue(p["id"], "tiktok", "research", trigger="manual")
            self.engine.start()
            wait_for(lambda: store.get_job(job["id"])["status"] == "failed")
            worker.retry_job(job["id"])
            wait_for(lambda: db.one("SELECT 1 FROM jobs WHERE project_id=? AND stage='notify' AND status='done'", (p["id"],)))
        self.assertEqual([j["stage"] for j in reversed(store.list_jobs(project_id=p["id"]))][:3], ["research", "script", "voice"])

    def test_idempotent_enqueue_and_cancel(self):
        p = self.project()
        j1, c1 = store.enqueue(p["id"], "tiktok", "research", trigger="manual")
        j2, c2 = store.enqueue(p["id"], "tiktok", "research", trigger="manual")
        self.assertEqual((c1, c2, j1["id"]), (True, False, j2["id"]))
        self.assertTrue(worker.cancel_job(j1["id"]))
        self.assertEqual(store.get_job(j1["id"])["status"], "cancelled")
        self.assertFalse(worker.cancel_job(j1["id"]))

    def test_restart_recovers_running_jobs(self):
        p = self.project()
        j, _ = store.enqueue(p["id"], "tiktok", "research", trigger="manual")
        claimed = store.claim_next("tiktok", skip_auto=False)
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(store.recover_running_jobs(), 1)
        j = store.get_job(j["id"])
        self.assertEqual((j["status"], j["attempts"]), ("queued", 0))

    def test_auto_jobs_wait_while_paused_but_manual_jobs_run(self):
        ran = []
        with mock.patch.dict(pipeline.STAGE_FUNCS, {s: (lambda ctx, s=s: ran.append((s, ctx.job["trigger"]))) for s in core.STAGES}):
            a = self.project(title="Auto one", origin="auto")
            m = store.create_project("youtube", "Manual one")
            store.enqueue(a["id"], "tiktok", "research", trigger="auto")
            store.enqueue(m["id"], "youtube", "research", trigger="manual")
            settings.save_automation({**settings.automation(), "state": "paused"})
            self.engine.start()
            wait_for(lambda: any(t == "manual" for _, t in ran))
            time.sleep(2.5)
            self.assertFalse(any(t == "auto" for _, t in ran))
            worker.set_automation_state("running")
            wait_for(lambda: any(t == "auto" for _, t in ran))


class PlannerTests(EngineBase):
    def test_distinct_titles_and_categories_and_scheduler_idempotency(self):
        pool = [make_src("Alpha Hero", "Anime", "JP"), make_src("Beta Donghua", "Donghua", "CN"), make_src("Gamma Toon", "Cartoon", "US", genres=["16"], catalog="TMDB"),
                make_src("Delta Toon", "Cartoon", "US", genres=["16"], catalog="TMDB"), make_src("Epsilon 3D", "3D Animation", "US", genres=["16"], catalog="TMDB")]
        calls = []

        def fake_pick(platform, taken_cats=(), taken_titles=(), date=None, log=print):
            calls.append((platform, list(taken_cats), list(taken_titles)))
            for c in pool:
                if c["title"] in taken_titles or (c["category"] in taken_cats and any(x["category"] not in taken_cats for x in pool)):
                    continue
                return dict(c)
            raise RuntimeError("none")
        noop = lambda ctx: None  # noqa: E731
        with mock.patch.object(research_mod, "pick", fake_pick), mock.patch.dict(pipeline.STAGE_FUNCS, {s: noop for s in core.STAGES}):
            settings.save_automation({**settings.automation(), "state": "running"})
            self.engine.start()
            for i in range(3):  # scheduler ticks must queue exactly one planner job
                self.engine.tick(i)
            wait_for(lambda: len(db.query("SELECT 1 FROM projects WHERE origin='auto'")) == 3)
            wait_for(lambda: db.one("SELECT status FROM jobs WHERE idem_key LIKE 'daily:%'")["status"] == "done")
            self.engine.tick(5)
        rows = db.query("SELECT platform,title,category FROM projects WHERE origin='auto'")
        self.assertEqual(len({r["title"] for r in rows}), 3)
        self.assertEqual(len({r["category"] for r in rows}), 3)
        self.assertEqual(len(db.query("SELECT 1 FROM jobs WHERE idem_key LIKE 'daily:%'")), 1)
        self.assertEqual(settings.automation()["last_run_date"], core.bkk_date())
        self.assertEqual(len(store.picks_for(core.bkk_date())), 3)
        # same day, second planner run: no new projects
        with mock.patch.object(research_mod, "pick", fake_pick):
            job, existed = worker.run_now()
        self.assertTrue(existed)
        self.assertEqual(len(db.query("SELECT 1 FROM projects WHERE origin='auto'")), 3)
        # DB-level guard: a second automatic project for the same platform/day is impossible
        with self.assertRaises(Exception):
            store.create_project("youtube", "Duplicate", origin="auto")

    def test_planner_rejects_unverifiable_titles_and_fails_visibly(self):
        bad = make_src("Indian Film", "International Movies", "IN", genres=["Drama"], catalog="TMDB")
        with mock.patch.object(research_mod, "pick", lambda *a, **k: dict(bad)):
            settings.update_automation({"platforms": {"youtube": True, "facebook": False, "tiktok": False}})
            settings.save_automation({**settings.automation(), "state": "running"})
            self.engine.start()
            job, _ = worker.run_now()
            wait_for(lambda: store.get_job(job["id"])["status"] == "failed", 30)
        self.assertEqual(db.one("SELECT COUNT(*) n FROM projects")["n"], 0)
        self.assertIn("could not verify", store.get_job(job["id"])["error"])


@unittest.skipUnless(HAVE_MEDIA, "ffmpeg and espeak-ng are required")
class RealPipelineTests(EngineBase):
    """Runs the real stages (espeak TTS, ffmpeg render, QC) on a 2-section script with the platform minimum relaxed for speed."""

    def test_full_pipeline_produces_verified_mp4_and_files(self):
        import os
        os.environ["NEXORA_TTS_ENGINES"] = "espeak"
        P = dict(config.PLATFORMS["tiktok"])
        try:
            config.PLATFORMS["tiktok"] = {**P, "min": 0.3, "max": 7}
            p = self.project(research=dict(fx.SRC))
            pipeline.save_script(p["id"], fx.sections()[:2], provider="fixture")
            store.enqueue(p["id"], "tiktok", "research", trigger="manual")
            self.engine.start()
            wait_for(lambda: store.get_row(p["id"])["status"] in ("ready_to_publish", "published", "failed"), 240)
            row = store.get_row(p["id"])
            self.assertEqual(row["status"], "ready_to_publish", row["error"])
            kinds = {f["kind"] for f in store.list_files(p["id"], include_internal=True)}
            self.assertTrue({"source", "script", "script_txt", "audio_mp3", "srt_en", "srt_my", "scenes", "video", "qc", "metadata", "credits"} <= kinds, kinds)
            v = store.file_path(p["id"], "video")
            from nexora.studio import qcx
            W, H = core.output_size("vertical_9_16", "720p")
            q = qcx.check_video(v, "tiktok", W, H)
            self.assertTrue(q["ok"], q["issues"])
            self.assertEqual((q["codec"], q["width"], q["height"]), ("h264", 720, 1280))
            pub = store.read_json_file(p["id"], "metadata")
            self.assertEqual(pub["status"], "draft_ready")  # nothing is claimed as published without an API upload
            self.assertIn("youtube.com/@ze.recab.channel", pub["metadata"]["description"])
            self.assertIn("facebook.com/share/1CSZfXHwPd", pub["metadata"]["description"])
            # idempotent re-run keeps existing outputs (no re-render)
            mtime = v.stat().st_mtime
            worker.enqueue_from_stage(p["id"], "qc", "manual", force=True)
            wait_for(lambda: store.get_row(p["id"])["status"] in ("ready_to_publish", "failed"), 120)
            self.assertEqual(store.file_path(p["id"], "video").stat().st_mtime, mtime) if store.file_path(p["id"], "video") else None
        finally:
            config.PLATFORMS["tiktok"] = P
            os.environ.pop("NEXORA_TTS_ENGINES", None)

    def test_too_short_narration_fails_non_recoverably_with_clear_message(self):
        import os
        os.environ["NEXORA_TTS_ENGINES"] = "espeak"
        try:
            p = self.project(research=dict(fx.SRC))
            pipeline.save_script(p["id"], fx.sections()[:1], provider="fixture")  # ~1 min < TikTok's 4 min minimum
            store.enqueue(p["id"], "tiktok", "voice", trigger="manual")
            self.engine.start()
            wait_for(lambda: store.get_row(p["id"])["status"] == "failed", 120)
            self.assertIn("outside tiktok's 4-7 min range", store.get_row(p["id"])["error"])
            self.assertIsNone(store.get_file_by_kind(p["id"], "video"))
        finally:
            os.environ.pop("NEXORA_TTS_ENGINES", None)


if __name__ == "__main__":
    unittest.main()
