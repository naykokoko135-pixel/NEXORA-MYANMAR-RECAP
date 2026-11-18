"""Create editable Burmese SRT captions from a creator-supplied Burmese script.

Timing is estimated from character count, not aligned to recorded speech. Review against
the final narration before publishing.
"""
import re

MAX_CAPTION_CHARS = 42
MIN_CAPTION_SECONDS = 1.5
DEFAULT_CHARS_PER_SECOND = 12.0


def _stamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _split_long_piece(piece: str, limit: int) -> list[str]:
    result = []
    remaining = piece.strip()
    while len(remaining) > limit:
        result.append(remaining[:limit].strip())
        remaining = remaining[limit:].strip()
    if remaining:
        result.append(remaining)
    return result


def _caption_chunks(script: str, limit: int) -> list[str]:
    chunks = []
    for paragraph in re.split(r"\\n+", (script or "").replace("\\r", "\\n")):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        # Prefer sentence boundaries, then Burmese/Latin spaces.
        sentences = re.split(r"(?<=[။.!?])\\s*|(?<=၊)\\s*", paragraph)
        for sentence in sentences:
            words = sentence.split()
            current = ""
            for word in words:
                if len(word) > limit:
                    if current:
                        chunks.append(current)
                        current = ""
                    chunks.extend(_split_long_piece(word, limit))
                    continue
                candidate = f"{current} {word}".strip()
                if len(candidate) <= limit:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = word
            if current:
                chunks.append(current)
    return chunks


def build_burmese_srt(script: str, chars_per_second: float = DEFAULT_CHARS_PER_SECOND) -> str:
    """Build sequential estimated timestamps for Burmese script captions."""
    if not (script or "").strip():
        raise ValueError("မြန်မာစာဇာတ်ညွှန်း ထည့်ပါ။")
    if len(script) > 20000:
        raise ValueError("စာသားသည် စာလုံး ၂၀,၀၀၀ ထက် မကျော်ရပါ။")
    if not (4.0 <= float(chars_per_second) <= 24.0):
        raise ValueError("ဖတ်နှုန်းကို 4 မှ 24 characters/second အတွင်းထားပါ။")

    chunks = _caption_chunks(script, MAX_CAPTION_CHARS)
    if not chunks:
        raise ValueError("စာတန်းထုတ်ရန် စာသားမတွေ့ပါ။")

    entries = []
    cursor_ms = 0
    for index, caption in enumerate(chunks, start=1):
        duration_ms = max(
            int(MIN_CAPTION_SECONDS * 1000),
            int(len(caption) / float(chars_per_second) * 1000),
        )
        start = _stamp(cursor_ms)
        cursor_ms += duration_ms
        end = _stamp(cursor_ms)
        entries.append(f"{index}\\n{start} --> {end}\\n{caption}")
    return "\\n\\n".join(entries) + "\\n"
