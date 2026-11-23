"""Select one paid AI script provider without silently double-billing."""
from __future__ import annotations
import os
from gemini_script_provider import GeminiScriptError, generate_burmese_recap_script as generate_gemini_script, gemini_script_status
from openai_script_provider import AIScriptError, generate_burmese_recap_script as generate_openai_script, openai_script_status


def script_provider_status() -> dict:
    selected = os.getenv("NEXORA_SCRIPT_PROVIDER", "auto").strip().lower() or "auto"
    gemini = gemini_script_status()
    openai = openai_script_status()
    if selected not in {"auto", "gemini", "openai"}:
        return {"selected": selected, "provider": "invalid", "configured": False, "model": ""}
    provider = "gemini" if selected == "gemini" or (selected == "auto" and gemini["configured"]) else "openai"
    status = gemini if provider == "gemini" else openai
    return {"selected": selected, "provider": provider, "configured": bool(status["configured"]), "model": status["model"]}


def generate_burmese_recap_script(topic: str, notes: str, platform: str = "youtube", duration: str = "46-60") -> str:
    status = script_provider_status()
    if status["provider"] == "invalid":
        raise AIScriptError("NEXORA_SCRIPT_PROVIDER ကို auto, gemini သို့မဟုတ် openai သာ သတ်မှတ်ပါ။")
    if status["provider"] == "gemini":
        if not status["configured"]:
            raise GeminiScriptError("Gemini ကို ရွေးထားသော်လည်း API key သို့မဟုတ် Paid AI ခွင့်ပြုချက် မပြည့်စုံပါ။")
        return generate_gemini_script(topic, notes, platform, duration)
    return generate_openai_script(topic, notes, platform, duration)
