import asyncio
import json
import re
import unittest
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from studio import api, core, db, pipeline, security, settings, store, worker, acceptance_fixture as fx

STATIC_JS = Path(api.STATIC) / "js"


class ApiBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        db.migrate()
        security.limiter._hits.clear()
        with db.tx() as c:
            for t in ("job_logs", "jobs", "project_files", "source_assets", "projects", "sessions", "kv", "daily_picks", "audit", "syslog"):
                c.execute(f"DELETE FROM {t}")
        app = api.mount(web.Application(), start_engine=False)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def login(self, pw="test-admin-password-123"):
        r = await self.client.post("/api/auth/login", json={"password": pw})
        self.assertEqual(r.status, 200, await r.text())
        self.csrf = (await r.json())["csrf"]
        self.h = {"X-CSRF-Token": self.csrf}
        return r

    async def post(self, path, **kw):
        return await self.client.post(path, headers=self.h, **kw)


class AuthTests(ApiBase):
    async def test_protected_routes_require_login(self):
        for p in ("/api/dashboard", "/api/projects", "/api/system", "/api/automation", "/api/files/1/download"):
            r = await self.client.get(p)
            self.assertEqual(r.status, 401, p)
            self.assertEqual((await r.json())["code"], "unauthenticated")

    async def test_login_flow_cookie_flags_and_logout(self):
        r = await self.login()
        cookie = r.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        s = await (await self.client.get("/api/auth/session")).json()
        self.assertTrue(s["authenticated"] and s["role"] == "admin" and s["csrf"] == self.csrf)
        self.assertEqual((await self.client.get("/api/dashboard")).status, 200)
        await self.post("/api/auth/logout")
        self.assertEqual((await self.client.get("/api/dashboard")).status, 401)

    async def test_wrong_password_then_lockout(self):
        for _ in range(5):
            r = await self.client.post("/api/auth/login", json={"password": "wrong-password-123"})
            self.assertEqual(r.status, 401)
        r = await self.client.post("/api/auth/login", json={"password": "test-admin-password-123"})
        self.assertEqual(r.status, 429)
        self.assertIn("Retry-After", r.headers)

    async def test_csrf_required_and_viewer_is_read_only(self):
        await self.login()
        r = await self.client.post("/api/projects", json={"title": "X", "platform": "youtube"})
        self.assertEqual((r.status, (await r.json())["code"]), (403, "csrf"))
        await self.post("/api/auth/logout")
        await self.login("test-viewer-password-123")
        self.assertEqual((await self.client.get("/api/projects")).status, 200)
        r = await self.post("/api/projects", json={"title": "X", "platform": "youtube"})
        self.assertEqual((r.status, (await r.json())["code"]), (403, "read_only"))

    async def test_security_headers_and_static_traversal(self):
        r = await self.client.get("/studio/")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])
        for p in ("/studio/..%2f..%2f__init__.py", "/studio/../api.py", "/studio/nope.js"):
            self.assertEqual((await self.client.get(p)).status, 404, p)
        self.assertEqual((await self.client.get("/studio/js/app.js")).status, 200)


class FrontendContractTests(ApiBase):
    async def test_every_endpoint_the_frontend_calls_exists(self):
        sub = [s for s in self.client.server.app._subapps if any("/api" in str(x.canonical) for x in s.router.resources())][0]
        pats = [re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", ("" if res.canonical.startswith("/api") else "/api") + res.canonical) + "$") for res in sub.router.resources()]
        called = set()
        for f in STATIC_JS.rglob("*.js"):
            for m in re.finditer(r"""[`'"](/api/[^`'"?]*)""", f.read_text("utf-8")):
                p = re.sub(r"\$\{[^}]*\}", "1", m.group(1)).rstrip("/")
                called.add(p)
        self.assertGreater(len(called), 30)
        missing = [p for p in called if not any(rx.match(p) for rx in pats) and not p.endswith("/")]
        self.assertEqual(missing, [])


class ProjectFlowTests(ApiBase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.login()

    async def new_project(self, **kw):
        r = await self.post("/api/projects", json={"title": "Big Buck Bunny", "platform": "tiktok", **kw})
        self.assertEqual(r.status, 201, await r.text())
        return await r.json()

    async def test_dashboard_shape(self):
        d = await (await self.client.get("/api/dashboard")).json()
        for k in ("backend", "telegram", "providers", "automation", "jobs", "recent_projects", "recent_videos", "recent_errors", "running_jobs", "alerts", "resources"):
            self.assertIn(k, d)
        self.assertFalse(d["telegram"]["configured"])
        self.assertEqual({p["id"] for p in d["providers"]}, {"openai", "gemini"})
        self.assertNotIn("test-admin-password", json.dumps(d))

    async def test_create_validate_delete(self):
        p = await self.new_project()
        self.assertEqual((p["platform"], p["status"], p["config"]["format"]), ("tiktok", "draft", "vertical_9_16"))
        self.assertIn("youtube.com/@ze.recab.channel", p["config"]["cta"])
        self.assertEqual((await self.post("/api/projects", json={"title": "", "platform": "tiktok"})).status, 400)
        self.assertEqual((await self.post("/api/projects", json={"title": "A", "platform": "vimeo"})).status, 400)
        self.assertEqual((await self.client.delete(f"/api/projects/{p['id']}", headers=self.h)).status, 400)  # confirm required
        r = await self.client.delete(f"/api/projects/{p['id']}?confirm=1", headers=self.h)
        self.assertEqual(r.status, 200)
        self.assertEqual((await self.client.get(f"/api/projects/{p['id']}")).status, 404)

    async def test_platform_rules(self):
        r = await self.client.put("/api/platforms/tiktok", json={"target_min": 30}, headers=self.h)
        self.assertEqual(r.status, 400)
        r = await self.client.put("/api/platforms/youtube", json={"target_min": 10}, headers=self.h)
        self.assertEqual(r.status, 400)
        r = await self.client.put("/api/platforms/tiktok", json={"cta": "no links here"}, headers=self.h)
        self.assertEqual(r.status, 400)
        r = await self.client.put("/api/platforms/youtube", json={"target_min": 50, "resolution": "1080p"}, headers=self.h)
        self.assertEqual(r.status, 200)
        self.assertEqual((await r.json())["target_min"], 50)

    async def test_script_edit_invalidates_downstream_and_subtitle_validation(self):
        p = await self.new_project()
        pid = p["id"]
        self.assertEqual((await self.client.get(f"/api/projects/{pid}/script")).status, 404)
        pipeline.save_script(pid, fx.sections()[:2], provider="fixture")
        store.write_json_file(pid, "cues", "cues.json", {"cues": [{"start": 0, "end": 2, "my": "က", "en": "a", "sec": 0}, {"start": 2.2, "end": 4, "my": "ခ", "en": "b", "sec": 0}], "duration": 4.5})
        (store.project_path(pid) / "v.mp4").write_bytes(b"x" * 20000)
        store.save_file(pid, "video", store.project_path(pid) / "v.mp4", 4.5)
        s = await (await self.client.get(f"/api/projects/{pid}/script")).json()
        self.assertEqual((s["edited"], s["stats"]["sentences"]), (False, 16))
        bad = await self.client.put(f"/api/projects/{pid}/script", json={"sections": [{"title": "t", "items": []}]}, headers=self.h)
        self.assertEqual(bad.status, 400)
        r = await self.client.put(f"/api/projects/{pid}/script", json={"sections": [{"title": "t", "kind": "story", "items": [{"my": "မင်္ဂလာပါ", "en": "Hello"}]}]}, headers=self.h)
        self.assertEqual(r.status, 200)
        self.assertTrue((await r.json())["edited"])
        self.assertIsNone(store.get_file_by_kind(pid, "video"))  # downstream output dropped
        self.assertIsNone(store.get_file_by_kind(pid, "cues"))
        # subtitles
        store.write_json_file(pid, "cues", "cues.json", {"cues": [{"start": 0, "end": 2, "my": "က", "en": "a", "sec": 0}, {"start": 2.2, "end": 4, "my": "ခ", "en": "b", "sec": 0}], "duration": 4.5})
        sv = await (await self.client.get(f"/api/projects/{pid}/subtitles")).json()
        self.assertEqual(len(sv["cues"]), 2)
        overlap = [{"start": 0, "end": 3, "my": "က", "en": "a"}, {"start": 2, "end": 4, "my": "ခ", "en": "b"}]
        self.assertEqual((await self.client.put(f"/api/projects/{pid}/subtitles", json={"cues": overlap}, headers=self.h)).status, 400)
        past = [{"start": 0, "end": 99, "my": "က", "en": "a"}]
        self.assertEqual((await self.client.put(f"/api/projects/{pid}/subtitles", json={"cues": past}, headers=self.h)).status, 400)
        ok = [{"start": 0, "end": 2, "my": "က", "en": "a"}, {"start": 2.5, "end": 4, "my": "ခ", "en": "b2"}]
        r = await self.client.put(f"/api/projects/{pid}/subtitles", json={"cues": ok}, headers=self.h)
        self.assertEqual(r.status, 200, await r.text())
        self.assertIn("b2", store.file_path(pid, "srt_en").read_text("utf-8"))
        r = await self.post(f"/api/projects/{pid}/subtitles/shift", json={"seconds": 0.5})
        self.assertAlmostEqual((await r.json())["cues"][0]["start"], 0.5)
        self.assertEqual((await self.post(f"/api/projects/{pid}/subtitles/shift", json={"seconds": 99})).status, 400)

    async def test_file_download_is_confined_and_delete_needs_confirm(self):
        p = await self.new_project()
        pipeline.save_script(p["id"], fx.sections()[:1])
        f = store.get_file_by_kind(p["id"], "script_txt")
        r = await self.client.get(f"/api/files/{f['id']}/download")
        self.assertEqual(r.status, 200)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        with db.tx() as c:  # a tampered DB row pointing outside the data dir must not be served
            c.execute("UPDATE project_files SET path='/etc/hostname' WHERE id=?", (f["id"],))
        self.assertEqual((await self.client.get(f"/api/files/{f['id']}/download")).status, 404)
        self.assertEqual((await self.client.delete(f"/api/files/{f['id']}", headers=self.h)).status, 400)

    async def test_upload_validation(self):
        p = await self.new_project()
        import aiohttp
        def form(data, **fields):
            fd = aiohttp.FormData()
            for k, v in fields.items():
                fd.add_field(k, v)
            fd.add_field("file", data, filename="x.bin")
            return fd
        r = await self.client.post("/api/voice/profiles", data=form(b"not audio at all", name="me", consent="yes"), headers=self.h)
        self.assertEqual((r.status, (await r.json())["code"]), (400, "invalid_file"))
        r = await self.client.post("/api/voice/profiles", data=form(b"OggS" + b"\0" * 100, name="me"), headers=self.h)
        self.assertEqual((await r.json())["code"], "consent_required")
        r = await self.client.post(f"/api/projects/{p['id']}/assets/upload", data=form(b"<script>alert(1)</script>", license="own-work", declaration="yes"), headers=self.h)
        self.assertEqual((await r.json())["code"], "invalid_file")
        r = await self.client.post(f"/api/projects/{p['id']}/assets/upload", data=form(b"\x89PNG\r\n\x1a\n" + b"0" * 50, license="own-work"), headers=self.h)
        self.assertEqual((await r.json())["code"], "declaration_required")


class AutomationApiTests(ApiBase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.login()

    async def test_state_machine_and_run_now_idempotency(self):
        a = await (await self.client.get("/api/automation")).json()
        self.assertEqual(a["state"], "stopped")
        self.assertEqual((await self.post("/api/automation/pause")).status, 409)
        self.assertEqual((await self.post("/api/automation/stop")).status, 409)
        a = await (await self.post("/api/automation/start")).json()
        self.assertEqual(a["state"], "running")
        self.assertIsNotNone(a["next_run"])
        self.assertEqual((await (await self.post("/api/automation/pause")).json())["state"], "paused")
        self.assertEqual((await (await self.post("/api/automation/resume")).json())["state"], "running")
        r1 = await (await self.post("/api/automation/run-now")).json()
        r2 = await (await self.post("/api/automation/run-now")).json()
        self.assertIn("job", r1)
        self.assertEqual(r1["job"]["id"], r2["job"]["id"])
        self.assertTrue(r2["already_ran_today"])
        self.assertEqual(db.one("SELECT COUNT(*) n FROM jobs WHERE idem_key LIKE 'daily:%'")["n"], 1)
        await self.post("/api/automation/stop")  # cancels queued automatic jobs
        self.assertEqual(db.one("SELECT status FROM jobs WHERE idem_key LIKE 'daily:%'")["status"], "cancelled")

    async def test_settings_validation(self):
        for bad in ({"schedule": "25:99"}, {"platforms": {"youtube": False, "facebook": False, "tiktok": False}}, {"retry": {"max_attempts": 99}}, {"publish_mode": "yolo"}):
            r = await self.client.put("/api/automation/settings", json=bad, headers=self.h)
            self.assertEqual(r.status, 400, bad)
        r = await self.client.put("/api/automation/settings", json={"schedule": "7:05", "publish_mode": "draft"}, headers=self.h)
        self.assertEqual((await r.json())["schedule"], "07:05")

    async def test_integrations_report_not_configured_honestly(self):
        self.assertEqual((await self.post("/api/telegram/test", json={})).status, 409)
        self.assertEqual((await self.post("/api/telegram/action", json={"action": "status"})).status, 409)
        self.assertEqual((await self.post("/api/ai/test", json={"provider": "openai"})).status, 409)
        t = await (await self.client.get("/api/telegram")).json()
        self.assertFalse(t["configured"] or t["connected"])
        st = await (await self.client.get("/api/platforms/status")).json()
        self.assertEqual(st["platforms"]["tiktok"]["method"], "draft")
        self.assertFalse(st["platforms"]["youtube"]["publish_ready"])


if __name__ == "__main__":
    unittest.main()
