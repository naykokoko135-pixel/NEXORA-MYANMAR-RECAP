"""AI provider router: OpenAI + Gemini with configurable models and automatic fallback.

API keys are read from the server environment only and are never returned by any API.
"""
import os
import threading
import time

import requests

from .base import config
from . import settings, store, core, db

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
# Same endpoint/shape as the production gemini_script_provider.py: newer Flash models are served through the Interactions API.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_TIMEOUT = 240
_gem_lock = threading.Lock()
_gem_last = [0.0]
_stats_lock = threading.Lock()


class ProviderError(RuntimeError):
    def __init__(self, provider, kind, message):
        super().__init__(f"{provider}: {message}")
        self.provider, self.kind = provider, kind  # kind: not_configured|quota|auth|server|bad_request|network


def key_for(provider: str) -> str:
    return os.getenv("OPENAI_API_KEY", "") if provider == "openai" else (os.getenv("GEMINI_API_KEY", "") or config.GEMINI_KEY)


def configured(provider: str) -> bool:
    return bool(key_for(provider))


def _classify(status: int, text: str) -> str:
    t = (text or "").lower()
    if status == 429 or "quota" in t or "resource_exhausted" in t or "rate limit" in t or "insufficient_quota" in t:
        return "quota"
    if status in (401, 403):
        return "auth"
    if status >= 500:
        return "server"
    return "bad_request"


def _call_openai(prompt, system, model, timeout=120):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    try:
        r = requests.post(OPENAI_URL, headers={"Authorization": f"Bearer {key_for('openai')}"},
                          json={"model": model, "messages": msgs, "temperature": 0.7}, timeout=timeout)
    except requests.RequestException as e:
        raise ProviderError("openai", "network", str(e)[:200])
    if r.status_code != 200:
        raise ProviderError("openai", _classify(r.status_code, r.text), f"HTTP {r.status_code} {r.text[:200]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        raise ProviderError("openai", "bad_request", "unexpected response shape")


def _gemini_text(result: dict) -> str:
    chunks = []
    for step in result.get("steps", []) if isinstance(result, dict) else []:
        if isinstance(step, dict) and step.get("type") == "model_output":
            for part in step.get("content", []):
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                    chunks.append(str(part["text"]).strip())
    return "\n".join(c for c in chunks if c).strip()


def _call_gemini(prompt, system, model, json_mode, timeout=GEMINI_TIMEOUT):
    model = config.GEMINI_RETIRED.get(model, model)  # a stored/typed retired model name would otherwise 404 forever
    key = key_for("gemini")
    with _gem_lock:  # free-tier pacing shared by all worker threads
        wait = config.LLM_DELAY - (time.time() - _gem_last[0])
        if wait > 0:
            time.sleep(wait)
        _gem_last[0] = time.time()
    text = (f"{system}\n\n" if system else "") + prompt + ("\n\nRespond with raw JSON only, no markdown." if json_mode else "")
    body = {"model": model, "input": text, "store": False, "generation_config": {"max_output_tokens": 8192}}
    try:
        r = requests.post(GEMINI_URL, headers={"x-goog-api-key": key, "Content-Type": "application/json", "Accept": "application/json"},
                          json=body, timeout=timeout)
    except requests.RequestException as e:
        raise ProviderError("gemini", "network", str(e).replace(key, "***")[:200])
    if r.status_code != 200:
        raise ProviderError("gemini", _classify(r.status_code, r.text), f"HTTP {r.status_code} {r.text[:200]}".replace(key, "***"))
    try:
        out = _gemini_text(r.json())
    except (ValueError, TypeError):  # invalid JSON, or null "steps"/"content" fields
        out = ""
    if not out:
        raise ProviderError("gemini", "bad_request", "unexpected response shape (no model_output text)")
    return out


def _call(provider, prompt, system, json_mode, model):
    if provider == "openai":
        return _call_openai(prompt + ("\n\nRespond with raw JSON only, no markdown." if json_mode else ""), system, model)
    return _call_gemini(prompt, system, model, json_mode)


def stats() -> dict:
    return db.kv_get("ai_stats", {}) or {}


def _record(provider, ok, err=None):
    with _stats_lock:
        s = stats()
        d = s.setdefault(provider, {"calls": 0, "failures": 0, "last_ok": None, "last_error": None, "last_error_at": None})
        d["calls"] += 1
        if ok:
            d["last_ok"] = time.time()
        else:
            d["failures"] += 1
            d["last_error"], d["last_error_at"] = str(err)[:240], time.time()
        db.kv_set("ai_stats", s)


def complete(prompt: str, system: str = "", json_mode: bool = True, *, retries: int = 2) -> str:
    """Generate text with the primary provider, falling back to the other on quota/API errors."""
    cfg = settings.ai_settings()
    order = [cfg["primary"]] + ([p for p in ("openai", "gemini") if p != cfg["primary"]] if cfg["fallback"] else [])
    usable = [p for p in order if configured(p)]
    if not usable:
        store.raise_alert("ai_not_configured", "error", "No AI provider is configured. Set OPENAI_API_KEY and/or GEMINI_API_KEY on the server.")
        raise ProviderError("none", "not_configured", "No AI provider configured (set OPENAI_API_KEY or GEMINI_API_KEY)")
    errors, quota_hit = [], False
    for prov in usable:
        model = cfg["models"][prov]
        for attempt in range(retries + 1):
            try:
                out = _call(prov, prompt, system, json_mode, model)
                _record(prov, True)
                store.clear_alert("ai_not_configured")
                if prov == cfg["primary"]:
                    store.clear_alert("ai_quota")
                return out
            except ProviderError as e:
                _record(prov, False, e)
                errors.append(str(e))
                if e.kind == "quota":
                    quota_hit = True
                if e.kind in ("quota", "auth", "bad_request"):
                    break  # retrying the same provider will not help; fall back
                time.sleep(2 * (attempt + 1))
    if quota_hit:
        store.raise_alert("ai_quota", "error", "AI provider quota/rate limit reached; scripts cannot be generated until quota resets or a key is replaced.")
    raise ProviderError("all", "quota" if quota_hit else "server", "All providers failed: " + " | ".join(errors)[:500])


def test(provider: str) -> dict:
    if provider not in ("openai", "gemini"):
        raise ValueError("Unknown provider")
    if not configured(provider):
        return {"ok": False, "latency_ms": 0, "error": "not_configured", "configured": False}
    model = settings.ai_settings()["models"][provider]
    t0 = time.time()
    try:
        _call(provider, "Reply with the single word: ok", "", False, model)
        _record(provider, True)
        return {"ok": True, "latency_ms": int((time.time() - t0) * 1000), "error": None, "configured": True}
    except ProviderError as e:
        _record(provider, False, e)
        return {"ok": False, "latency_ms": int((time.time() - t0) * 1000), "error": str(e)[:240], "configured": True}


def overview() -> dict:
    cfg, st = settings.ai_settings(), stats()
    provs = []
    for pid, suggested in (("openai", settings.OPENAI_MODELS), ("gemini", settings.GEMINI_MODELS)):
        d = st.get(pid, {})
        provs.append({"id": pid, "configured": configured(pid), "model": cfg["models"][pid], "primary": cfg["primary"] == pid,
                      "models_suggested": suggested, "last_ok": d.get("last_ok"), "last_error": d.get("last_error"),
                      "last_error_at": d.get("last_error_at"), "calls": d.get("calls", 0), "failures": d.get("failures", 0)})
    return {"primary": cfg["primary"], "fallback": cfg["fallback"], "providers": provs}


def install_script_hook():
    """Route the existing script generator through this router (Telegram/GitHub-Actions flows are unaffected)."""
    from .base import script
    script.LLM_HOOK = complete
