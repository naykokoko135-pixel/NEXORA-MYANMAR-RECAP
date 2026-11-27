"""Integration layer: studio mounted into a FastAPI app via studio.fastapi_mount (the production wiring)."""
import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio import fastapi_mount


def make_app():
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    fastapi_mount.install(app, lambda: None)
    return app


class MountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cm = TestClient(make_app())
        cls.c = cls.cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.cm.__exit__(None, None, None)

    def login(self, **headers):
        r = self.c.post("/api/auth/login", json={"password": os.environ["NEXORA_ADMIN_PASSWORD"]}, headers=headers)
        self.assertEqual(r.status_code, 200, r.text)
        return r

    def test_existing_routes_untouched(self):
        self.assertEqual(self.c.get("/health").json(), {"status": "ok"})

    def test_studio_redirect_index_and_assets(self):
        r = self.c.get("/studio", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (307, "/studio/"))
        r = self.c.get("/studio/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers["content-type"])
        for asset in ("/studio/js/app.js", "/studio/css/app.css"):
            self.assertEqual(self.c.get(asset).status_code, 200, asset)

    def test_api_is_protected_and_path_traversal_blocked(self):
        self.assertEqual(self.c.get("/api/dashboard").status_code, 401)
        self.assertIn(self.c.get("/studio/..%2f..%2fetc/passwd").status_code, (400, 404))

    def test_login_session_cookie_and_csrf_through_proxy(self):
        r = self.login()
        self.assertIn("httponly", r.headers["set-cookie"].lower())
        csrf = self.c.get("/api/auth/session").json()["csrf"]
        self.assertEqual(self.c.post("/api/automation/pause").status_code, 403)  # no CSRF header
        self.assertNotEqual(self.c.post("/api/automation/pause", headers={"X-CSRF-Token": csrf}).status_code, 403)
        self.c.cookies.clear()

    def test_cookie_secure_flag_follows_edge_scheme(self):
        r = self.login(**{"X-Forwarded-Proto": "https"})
        self.assertIn("secure", r.headers["set-cookie"].lower())
        self.c.cookies.clear()

    def test_lockout_is_per_real_client_ip_and_xff_cannot_be_spoofed(self):
        bad = {"password": "definitely-wrong-password"}
        codes = [self.c.post("/api/auth/login", json=bad, headers={"CF-Connecting-IP": "203.0.113.50", "X-Forwarded-For": f"10.9.9.{i}"}).status_code
                 for i in range(8)]
        self.assertEqual(codes[0], 401)
        self.assertEqual(codes[-1], 429)  # same real IP keeps counting although X-Forwarded-For changes every request
        other = self.c.post("/api/auth/login", json={"password": os.environ["NEXORA_ADMIN_PASSWORD"]}, headers={"CF-Connecting-IP": "198.51.100.77"})
        self.assertEqual(other.status_code, 200)  # a different user is not locked out
        self.c.cookies.clear()

    def test_client_ip_prefers_edge_headers(self):
        class R:  # minimal request double
            def __init__(self, h, host="10.0.0.1"):
                self.headers, self.client = h, type("C", (), {"host": host})()
        self.assertEqual(fastapi_mount.client_ip(R({"cf-connecting-ip": "1.2.3.4", "x-forwarded-for": "9.9.9.9"})), "1.2.3.4")
        self.assertEqual(fastapi_mount.client_ip(R({"x-forwarded-for": "9.9.9.9"})), "10.0.0.1")


class UnavailableTests(unittest.TestCase):
    def test_503_when_studio_runtime_is_down(self):
        app = FastAPI()
        app.add_api_route("/api/{path:path}", fastapi_mount.proxy, methods=["GET"])
        saved = fastapi_mount.runtime.session, fastapi_mount.runtime.base
        fastapi_mount.runtime.session = fastapi_mount.runtime.base = None
        try:
            r = TestClient(app).get("/api/anything")
            self.assertEqual((r.status_code, r.json()["code"]), (503, "studio_unavailable"))
        finally:
            fastapi_mount.runtime.session, fastapi_mount.runtime.base = saved


class ProductionWiringTests(unittest.TestCase):
    def test_bot_web_app_keeps_all_original_routes_and_adds_studio(self):
        os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
        import bot
        paths = {getattr(r, "path", "") for r in bot.web_app.routes}
        for original in ("/", "/health", "/telegram-webhook", "/console", "/chatgpt/command", "/internal/daily-recap", "/download/{token}"):
            self.assertIn(original, paths)
        self.assertIn("/studio/{path:path}", paths)
        self.assertIn("/api/{path:path}", paths)


if __name__ == "__main__":
    unittest.main()
