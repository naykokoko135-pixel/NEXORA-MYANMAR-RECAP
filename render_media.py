"""Classify supported documents uploaded to an active render session."""
from pathlib import Path

_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg"}


def classify_render_document(filename: str) -> str | None:
    """Return audio/subtitle for supported document names, otherwise None."""
    suffix = Path(filename or "").suffix.lower()
    if suffix in _AUDIO_EXTENSIONS:
        return "audio"
    if suffix == ".srt":
        return "subtitle"
    return None
