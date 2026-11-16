"""Helpers for safely reusing the latest per-user automatic research result."""


def matching_cached_research(topic: str, cached_topic: str, cached_result: str) -> str | None:
    """Return cached research only when it belongs to the requested movie title."""
    requested = " ".join((topic or "").split()).strip().casefold()
    saved = " ".join((cached_topic or "").split()).strip().casefold()
    result = (cached_result or "").strip()
    if not requested or requested != saved or not result:
        return None
    if "ကိုက်ညီသော Wikipedia ဆောင်းပါး မတွေ့ပါ" in result:
        return None
    return result
