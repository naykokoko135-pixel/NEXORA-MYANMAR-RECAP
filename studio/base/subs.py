import re
import textwrap


def ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def wrap(text, width):
    lines = textwrap.wrap(text, width) or [""]
    return "\n".join(lines[:2] if len(lines) <= 2 else [lines[0], " ".join(lines[1:])])


def write_srt(timeline, path, field="en", width=42):
    out = []
    for i, e in enumerate(timeline, 1):
        w = width if field == "en" else 30
        out.append(f"{i}\n{ts(e['start'])} --> {ts(max(e['end'], e['start'] + 0.3))}\n{wrap(e[field], w)}\n")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    return validate_srt(path)


def _sec(s):
    h, m, r = s.split(":")
    sec, ms = r.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


def validate_srt(path):
    data = open(path, encoding="utf-8").read()  # raises if not UTF-8
    blocks = [b for b in data.strip().split("\n\n") if b.strip()]
    prev_end, issues = 0.0, []
    for b in blocks:
        ls = b.split("\n")
        m = re.match(r"(\d+:\d\d:\d\d,\d{3}) --> (\d+:\d\d:\d\d,\d{3})", ls[1])
        if not m:
            issues.append(f"bad timing block {ls[0]}")
            continue
        a, z = _sec(m.group(1)), _sec(m.group(2))
        if z <= a:
            issues.append(f"non-positive duration {ls[0]}")
        if a < prev_end - 0.001:
            issues.append(f"overlap at {ls[0]}")
        prev_end = z
    return dict(cues=len(blocks), issues=issues, ok=not issues and len(blocks) > 0)
