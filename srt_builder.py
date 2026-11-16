import re

_TIME = re.compile(r"^(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})\s+\|\s*(.+)$")

def build_srt(source: str) -> str:
    """Convert timestamped subtitle lines into UTF-8 SRT text."""
    entries = []
    previous_end = None
    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        match = _TIME.fullmatch(line)
        if not match:
            raise ValueError(f"စာကြောင်း {line_number}: HH:MM:SS,mmm --> HH:MM:SS,mmm | Subtitle ပုံစံကို သုံးပါ။")
        start, end, subtitle = match.groups()
        start_ms = _to_ms(start)
        end_ms = _to_ms(end)
        if end_ms <= start_ms:
            raise ValueError(f"စာကြောင်း {line_number}: အဆုံးအချိန်သည် အစအချိန်ထက် နောက်ကျရပါမည်။")
        if previous_end is not None and start_ms < previous_end:
            raise ValueError(f"စာကြောင်း {line_number}: အချိန်များ ထပ်နေသည် သို့မဟုတ် အစဉ်မမှန်ပါ။")
        entries.append(f"{len(entries) + 1}\n{start} --> {end}\n{subtitle.strip()}")
        previous_end = end_ms
    if not entries:
        raise ValueError("အနည်းဆုံး စာတန်းတစ်ကြောင်း ထည့်ပါ။")
    return "\n\n".join(entries) + "\n"

def _to_ms(timestamp: str) -> int:
    hours, minutes, remainder = timestamp.split(":")
    seconds, millis = remainder.split(",")
    return (((int(hours) * 60 + int(minutes)) * 60) + int(seconds)) * 1000 + int(millis)
