"""Telegram integration for the studio. Talks to the real Bot API; reports honestly when unconfigured or unreachable."""
import os
import time

import requests

from . import core, db, store

API = "https://api.telegram.org/bot{token}/{method}"
_cache = {"ts": 0.0, "val": None}

# Set by studio.fastapi_mount: returns the bot's REAL registered commands (never a hard-coded list).
command_source = None


def commands() -> list[dict]:
    try:
        return list(command_source()) if command_source else []
    except Exception:
        return []


WEB_ACTIONS = [
    {"id": "daily_report", "label": "Send daily report", "desc": "Sends today's Studio status (picks, projects, failures) to the configured chat."},
    {"id": "status", "label": "Send studio status", "desc": "Sends queue, automation and resource status to the configured chat."},
]


def token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def chat_id() -> str:
    """Owner chat for notifications. TELEGRAM_CHAT_ID, falling back to the production bridge chat (CHATGPT_BRIDGE_CHAT_ID)."""
    return os.getenv("TELEGRAM_CHAT_ID", "").strip() or os.getenv("CHATGPT_BRIDGE_CHAT_ID", "").strip()


def _call(method, *, json_body=None, data=None, files=None, timeout=30):
    r = requests.post(API.format(token=token(), method=method), json=json_body, data=data, files=files, timeout=timeout)
    try:
        body = r.json()
    except Exception:
        body = {}
    if not body.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {str(body.get('description') or r.status_code)[:160]}")
    return body["result"]


def info(force=False) -> dict:
    """Live connection status (cached 30 s)."""
    if not force and _cache["val"] and time.time() - _cache["ts"] < 30:
        return _cache["val"]
    out = {"configured": bool(token()), "connected": False, "bot_username": None, "webhook_url": None, "pending_updates": None, "error": None,
           "chat_configured": bool(chat_id()), "commands": commands(), "web_actions": WEB_ACTIONS}
    if token():
        try:
            me = _call("getMe", timeout=12)
            out.update(connected=True, bot_username=me.get("username"))
            wh = _call("getWebhookInfo", timeout=12)
            url = wh.get("url") or ""
            out["webhook_url"] = (url.rsplit("/", 1)[0] + "/…") if url else None  # never expose the webhook secret
            out["pending_updates"] = wh.get("pending_update_count")
            if wh.get("last_error_message"):
                out["error"] = f"Webhook: {wh['last_error_message'][:120]}"
        except Exception as e:
            out["error"] = str(e).replace(token(), "***")[:200]
    _cache.update(ts=time.time(), val=out)
    return out


def send(text: str, silent=False) -> bool:
    """Send a message to the configured chat. Returns False (and logs) when unconfigured/unreachable; never raises."""
    if not (token() and chat_id()):
        return False
    try:
        for i in range(0, len(text), 3900):
            _call("sendMessage", json_body={"chat_id": chat_id(), "text": text[i:i + 3900], "disable_web_page_preview": True, "disable_notification": silent})
        return True
    except Exception as e:
        core.syslog("warn", f"Telegram send failed: {str(e).replace(token(), '***')[:160]}")
        return False


def send_file(path, caption="") -> bool:
    from pathlib import Path
    p = Path(path)
    if not (token() and chat_id() and p.exists()) or p.stat().st_size > 49 * 1024 * 1024:
        return False
    try:
        with p.open("rb") as f:
            _call("sendDocument", data={"chat_id": chat_id(), "caption": caption[:900]}, files={"document": (p.name, f)}, timeout=600)
        return True
    except Exception as e:
        core.syslog("warn", f"Telegram file send failed: {str(e).replace(token(), '***')[:160]}")
        return False


def test_message(text: str | None = None) -> bool:
    if not (token() and chat_id()):
        raise LookupError("not_configured")
    _call("sendMessage", json_body={"chat_id": chat_id(), "text": (text or "✅ NEXORA Studio test message").strip()[:500]})
    return True


# ------------------------------------------------------------------ reports
_ICON = {"ready_to_publish": "📝", "published": "✅", "completed": "✅", "failed": "❌", "cancelled": "⛔", "running": "⏳", "queued": "🕒", "paused": "⏸"}


def daily_report(date: str | None = None) -> str:
    date = date or core.bkk_date()
    projects, _ = store.list_projects(date=date, limit=100)
    lines = [f"📊 NEXORA Studio daily report — {date}"]
    if not projects:
        lines.append("No projects were created today.")
    for p in projects:
        pub = store.read_json_file(p["id"], "metadata", {}) or {}
        vid = next((f for f in p["files"] if f["kind"] == "video"), None)
        extra = f" • {vid['size'] / 1e6:.1f} MB" if vid else ""
        lines.append(f"{_ICON.get(p['status'], '•')} {p['platform'].title()}: {p['title']} [{p['status']}]{extra}" +
                     (f"\n   publish: {pub.get('status')} {pub.get('url') or ''}".rstrip() if pub.get("status") else "") +
                     (f"\n   error: {p['error'][:160]}" if p["error"] else ""))
    al = store.alerts()
    if al:
        lines.append("⚠️ Alerts: " + "; ".join(a["msg"][:100] for a in al[:3]))
    sysinfo = core.resources_brief()
    lines.append(f"Disk free: {sysinfo['disk_free_gb']} GB")
    return "\n".join(lines)


def status_text() -> str:
    jobs = store.job_counts()
    from . import settings
    a = settings.automation()
    return (f"🎬 NEXORA Studio\nAutomation: {a['state']} (daily {a['schedule']} Asia/Bangkok)\n"
            f"Jobs — queued {jobs['queued']}, running {jobs['running']}, failed {jobs['failed']}, done {jobs['done']}\n"
            f"Disk free: {core.disk()['free_gb']} GB")
