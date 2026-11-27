"""Mounts NEXORA Studio into the production FastAPI app (``bot.web_app``).

The studio engine/API is an aiohttp application. It runs inside the *same process* on a loopback-only port, and this module adds
FastAPI routes that forward ``/studio`` and ``/api`` to it, so the existing Render service (one public port) serves everything.
The bot is never put at risk: if the studio fails to start, the bot keeps running and the proxy answers 503.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import aiohttp
from aiohttp import web
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

log = logging.getLogger("nexora.studio")

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade",
              "host", "content-length"}
MAX_BODY = 30 * 1024 * 1024  # studio's own upload cap is 25 MB (+ multipart overhead)
METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]


class _Runtime:
    def __init__(self):
        self.runner: web.AppRunner | None = None
        self.session: aiohttp.ClientSession | None = None
        self.base: str | None = None
        self.error: str | None = None

    async def start(self):
        try:
            from studio import api  # imported lazily so a studio import error cannot break the bot
            app = web.Application()
            api.mount(app)
            self.runner = web.AppRunner(app, access_log=None)
            await self.runner.setup()
            port = int(os.getenv("STUDIO_INTERNAL_PORT", "0"))
            site = web.TCPSite(self.runner, "127.0.0.1", port)  # loopback only: never reachable except through the proxy below
            await site.start()
            port = site._server.sockets[0].getsockname()[1]
            self.base = f"http://127.0.0.1:{port}"
            self.session = aiohttp.ClientSession(auto_decompress=False, timeout=aiohttp.ClientTimeout(total=None, sock_connect=5, sock_read=600),
                                                 cookie_jar=aiohttp.DummyCookieJar())
            self.error = None
            log.info("NEXORA Studio running on %s (proxied at /studio and /api)", self.base)
        except Exception as e:  # noqa: BLE001
            self.error = f"{type(e).__name__}: {e}"[:300]
            log.exception("NEXORA Studio failed to start; the Telegram bot is unaffected")
            await self.stop()

    async def stop(self):
        if self.session:
            await self.session.close()
            self.session = None
        if self.runner:
            try:
                await self.runner.cleanup()
            except Exception:  # noqa: BLE001
                log.exception("studio shutdown error")
            self.runner = None
        self.base = None


runtime = _Runtime()


def client_ip(request: Request) -> str:
    """Real client IP for rate limiting. Prefers headers set by Render's edge (clients cannot forge them there); never the raw,
    client-controllable first X-Forwarded-For entry."""
    for h in ("cf-connecting-ip", "true-client-ip"):
        v = request.headers.get(h, "").strip()
        if v:
            return v
    return request.client.host if request.client else "?"


async def proxy(request: Request) -> Response:
    if not runtime.session or not runtime.base:
        return JSONResponse({"error": "NEXORA Studio is not running", "detail": runtime.error or "starting", "code": "studio_unavailable"}, status_code=503)
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        return JSONResponse({"error": "Request too large", "code": "too_large"}, status_code=413)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() not in ("x-forwarded-for", "x-forwarded-proto")}
    headers["X-Forwarded-For"] = client_ip(request)  # overwrite whatever the client sent
    headers["X-Forwarded-Proto"] = request.headers.get("x-forwarded-proto") or request.url.scheme
    body = await request.body() if request.method not in ("GET", "HEAD") else None
    if body is not None and len(body) > MAX_BODY:
        return JSONResponse({"error": "Request too large", "code": "too_large"}, status_code=413)
    url = runtime.base + request.url.path + (f"?{request.url.query}" if request.url.query else "")
    try:
        up = await runtime.session.request(request.method, url, headers=headers, data=body, allow_redirects=False)
    except Exception as e:  # noqa: BLE001
        log.warning("studio proxy error: %s", e)
        return JSONResponse({"error": "NEXORA Studio did not respond", "code": "studio_unavailable"}, status_code=502)

    async def body_iter():
        async for chunk in up.content.iter_chunked(64 * 1024):
            yield chunk

    out = {k: v for k, v in up.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() != "set-cookie"}
    resp = StreamingResponse(body_iter(), status_code=up.status, headers=out, background=BackgroundTask(up.release))
    if "Content-Length" in up.headers and request.method != "HEAD":
        resp.headers["content-length"] = up.headers["Content-Length"]
    for c in up.headers.getall("Set-Cookie", []):  # keep every Set-Cookie (a dict cannot hold duplicates)
        resp.raw_headers.append((b"set-cookie", c.encode("latin-1")))
    return resp


async def _studio_root(request: Request):
    return RedirectResponse("/studio/", status_code=307)


def _bot_commands(get_telegram_app):
    def source():
        app = get_telegram_app()
        out = {}
        for group in (app.handlers or {}).values():
            for h in group:
                for c in sorted(getattr(h, "commands", ()) or ()):
                    cb = getattr(h, "callback", None)
                    doc = ((getattr(cb, "__doc__", "") or "").strip().splitlines() or [""])[0][:120]
                    out.setdefault(c, {"cmd": "/" + c, "desc": doc})
        return sorted(out.values(), key=lambda x: x["cmd"])
    return source


def install(web_app: FastAPI, get_telegram_app=lambda: None):
    """Add the studio to ``web_app``. Safe to call once, at import time, right after ``web_app = FastAPI(...)``."""
    from studio import notifier

    notifier.command_source = _bot_commands(get_telegram_app)
    web_app.add_api_route("/studio", _studio_root, methods=["GET", "HEAD"], include_in_schema=False)
    web_app.add_api_route("/studio/{path:path}", proxy, methods=METHODS, include_in_schema=False)
    web_app.add_api_route("/api/{path:path}", proxy, methods=METHODS, include_in_schema=False)

    original = web_app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        async with original(app) as state:  # the bot starts first; if it cannot start, nothing else does either
            await runtime.start()
            try:
                yield state
            finally:
                await runtime.stop()

    web_app.router.lifespan_context = lifespan
