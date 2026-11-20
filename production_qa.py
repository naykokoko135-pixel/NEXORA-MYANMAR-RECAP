"""Platform-aware script duration and SRT structural QA.

Duration estimates use the same approximate characters-per-second convention
as subtitle_builder; they are planning signals, not measured speech duration.
"""
import re


PLATFORM_TARGETS = {
    "youtube": {"parts": 3, "part_min": 15 * 60, "part_max": 20 * 60, "total_min": 46 * 60, "total_max": 60 * 60},
    "facebook": {"parts": 3, "part_min": 15 * 60, "part_max": 20 * 60, "total_min": 46 * 60, "total_max": 60 * 60},
    "tiktok": {"parts": 1, "part_min": 4 * 60, "part_max": 7 * 60, "total_min": 4 * 60, "total_max": 7 * 60},
}
PLATFORM_ALIASES = {"yt": "youtube", "fb": "facebook", "tt": "tiktok"}
PART_MARKER = re.compile(r"^\s*\[PART\s*(\d+)\]\s*$", re.IGNORECASE)
SRT_MARKER = re.compile(r"^\s*\[SRT\]\s*$", re.IGNORECASE)
TIME_LINE = re.compile(
    r"^(\d{2,}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2,}:\d{2}:\d{2},\d{3})$"
)
DEFAULT_CHARS_PER_SECOND = 12.0
MAX_CAPTION_CHARS = 42


def _seconds(timestamp):
    hours, minutes, rest = timestamp.split(":")
    seconds, millis = rest.split(",")
    h, m, s, ms = int(hours), int(minutes), int(seconds), int(millis)
    if m > 59 or s > 59 or ms > 999:
        raise ValueError("SRT timestamp တွင် မိနစ်/စက္ကန့် မမှန်ပါ။")
    return ((h * 60 + m) * 60 + s) + ms / 1000.0


def _format_duration(seconds):
    total = max(0, int(round(seconds)))
    minutes, sec = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def parse_production_package(package_text):
    """Parse [PART 1..3] and optional [SRT] blocks from the supplied text."""
    parts = {}
    srt_lines = []
    current = None
    in_srt = False
    for raw in str(package_text or "").replace("\r", "").splitlines():
        part_match = PART_MARKER.fullmatch(raw)
        if part_match:
            current = int(part_match.group(1))
            in_srt = False
            parts.setdefault(current, [])
            continue
        if SRT_MARKER.fullmatch(raw):
            current = None
            in_srt = True
            continue
        if in_srt:
            srt_lines.append(raw)
        elif current is not None:
            parts[current].append(raw)
    cleaned = {number: "\n".join(lines).strip() for number, lines in parts.items()}
    srt_text = "\n".join(srt_lines).strip()
    return cleaned, srt_text


def validate_srt(srt_text):
    """Check SRT numbering, timestamps, overlaps, and caption line length."""
    issues = []
    entries = []
    text = str(srt_text or "").lstrip("\ufeff").strip()
    if not text:
        return {"valid": False, "issues": ["SRT မထည့်ထားပါ။"], "entries": 0, "duration_seconds": None}
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    previous_end = None
    for index, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        if len(lines) < 3:
            issues.append(f"SRT block {index}: စာတန်းပုံစံ မပြည့်စုံပါ။")
            continue
        try:
            sequence = int(lines[0].strip())
        except ValueError:
            issues.append(f"SRT block {index}: sequence number မမှန်ပါ။")
            continue
        if sequence != index:
            issues.append(f"SRT block {index}: sequence သည် {index} ဖြစ်ရပါမည်။")
        match = TIME_LINE.fullmatch(lines[1].strip())
        if not match:
            issues.append(f"SRT block {index}: timestamp ပုံစံ မမှန်ပါ။")
            continue
        try:
            start = _seconds(match.group(1))
            end = _seconds(match.group(2))
        except (ValueError, TypeError):
            issues.append(f"SRT block {index}: timestamp တန်ဖိုး မမှန်ပါ။")
            continue
        if end <= start:
            issues.append(f"SRT block {index}: အဆုံးအချိန်သည် အစအချိန်ထက် နောက်ကျရပါမည်။")
        if previous_end is not None and start < previous_end:
            issues.append(f"SRT block {index}: ယခင်စာတန်းနှင့် အချိန်ထပ်နေသည်။")
        caption_lines = [line for line in lines[2:] if line.strip()]
        if not caption_lines:
            issues.append(f"SRT block {index}: စာတန်းဗလာဖြစ်နေသည်။")
        for caption_line in caption_lines:
            if len(caption_line) > MAX_CAPTION_CHARS:
                issues.append(f"SRT block {index}: စာတန်းတစ်ကြောင်းသည် {MAX_CAPTION_CHARS} characters ကျော်နေသည်။")
                break
        entries.append({"start": start, "end": end, "text": "\n".join(caption_lines)})
        previous_end = max(previous_end or 0, end)
    duration = max((entry["end"] for entry in entries), default=None)
    return {
        "valid": bool(entries) and not issues,
        "issues": issues,
        "entries": len(entries),
        "duration_seconds": duration,
    }


def analyze_production_package(platform, package_text, chars_per_second=DEFAULT_CHARS_PER_SECOND):
    """Check platform part count, approximate duration, and optional SRT structure."""
    platform_key = str(platform or "").strip().casefold()
    platform_key = PLATFORM_ALIASES.get(platform_key, platform_key)
    issues = []
    passed = []
    if platform_key not in PLATFORM_TARGETS:
        return {"status": "NOT READY", "platform": platform_key, "issues": ["Platform သည် youtube/facebook/tiktok ဖြစ်ရပါမည်။"], "passed": []}
    try:
        cps = float(chars_per_second)
    except (TypeError, ValueError):
        cps = DEFAULT_CHARS_PER_SECOND
    if not 4.0 <= cps <= 24.0:
        issues.append("ဖတ်နှုန်းသည် 4 မှ 24 characters/second အတွင်း ဖြစ်ရပါမည်။")
        cps = DEFAULT_CHARS_PER_SECOND

    targets = PLATFORM_TARGETS[platform_key]
    parts, srt_text = parse_production_package(package_text)
    expected_numbers = list(range(1, targets["parts"] + 1))
    if sorted(parts) != expected_numbers:
        issues.append(
            f"{platform_key} အတွက် [PART 1] မှ [PART {targets['parts']}] အထိ အပိုင်း {targets['parts']} ပိုင်းတိတိ လိုအပ်သည်။"
        )
    durations = {}
    for number in expected_numbers:
        script = parts.get(number, "")
        if not script:
            issues.append(f"Part {number} စာသား မရှိပါ။")
            continue
        duration = len(script) / cps
        durations[number] = duration
        if targets["part_min"] <= duration <= targets["part_max"]:
            passed.append(f"Part {number} ခန့်မှန်းကြာချိန် {_format_duration(duration)} သည် သတ်မှတ်အတွင်းရှိသည်။")
        else:
            issues.append(
                f"Part {number} ခန့်မှန်းကြာချိန် {_format_duration(duration)} — "
                f"{_format_duration(targets['part_min'])} မှ {_format_duration(targets['part_max'])} အတွင်း ပြင်ပါ။"
            )
    total_estimate = sum(durations.values())
    if targets["total_min"] <= total_estimate <= targets["total_max"]:
        passed.append("စုစုပေါင်း Script ခန့်မှန်းကြာချိန် " + _format_duration(total_estimate) + " သည် သတ်မှတ်အတွင်းရှိသည်။")
    else:
        issues.append(
            "စုစုပေါင်း Script ခန့်မှန်းကြာချိန် " + _format_duration(total_estimate) + " — "
            + _format_duration(targets["total_min"]) + " မှ " + _format_duration(targets["total_max"]) + " အတွင်း ပြင်ပါ။"
        )

    srt = validate_srt(srt_text)
    if not srt_text:
        issues.append("SRT block [SRT] မပါဝင်ပါ။ Subtitle QA မလုပ်နိုင်ပါ။")
    elif not srt["valid"]:
        issues.extend(srt["issues"])
    else:
        passed.append(f"SRT structure စစ်ဆေးမှု အောင်မြင်သည်။ Caption {srt['entries']} ခု။")
        srt_duration = srt.get("duration_seconds") or 0
        if not targets["total_min"] <= srt_duration <= targets["total_max"]:
            issues.append(
                "SRT နောက်ဆုံး timestamp " + _format_duration(srt_duration) + " သည် Platform စုစုပေါင်းကြာချိန် သတ်မှတ်ချက်နှင့် မကိုက်ပါ။"
            )
        else:
            passed.append("SRT နောက်ဆုံး timestamp " + _format_duration(srt_duration) + " သည် Platform စုစုပေါင်းအတွင်းရှိသည်။")
        if total_estimate > 0:
            difference = abs(srt_duration - total_estimate) / total_estimate
            if difference > 0.25:
                issues.append("SRT အဆုံးချိန်နှင့် Script ခန့်မှန်းကြာချိန် 25% ထက်ပိုကွာနေသည်။ အသံနှင့် ကိုက်ညီမှု ပြန်စစ်ပါ။")
            else:
                passed.append("SRT အဆုံးချိန်နှင့် Script ခန့်မှန်းကြာချိန် ကွာဟမှု 25% အတွင်းရှိသည်။")

    return {
        "status": "REVIEW" if issues else "READY FOR HUMAN REVIEW",
        "platform": platform_key,
        "parts": {str(number): {"characters": len(parts.get(number, "")), "estimated_seconds": durations.get(number)} for number in expected_numbers},
        "total_estimated_seconds": total_estimate,
        "srt": srt,
        "passed": passed,
        "issues": issues,
        "disclaimer": (
            "ကြာချိန်သည် script character count ÷ characters/second ဖြင့် ခန့်မှန်းထားခြင်းသာဖြစ်ပြီး "
            "တကယ့်အသံဖိုင်ကြာချိန် မဟုတ်ပါ။ SRT timestamp စစ်ဆေးမှုသည် ဖွဲ့စည်းပုံ/အချိန်အစဉ်ကိုသာ စစ်သည်။ "
            "အသံနှင့် subtitle ကို နားထောင်/ကြည့်ရှုပြီး လူကိုယ်တိုင် ထပ်စစ်ပါ။ ဇာတ်လမ်းမှန်ကန်မှု၊ မူပိုင်ခွင့်နှင့် platform policy ကို အာမမခံပါ။"
        ),
    }


def format_production_qa_report(report):
    lines = [
        "🧪 NEXORA — SCRIPT / DURATION / SUBTITLE QA",
        "အခြေအနေ: " + str(report.get("status") or "REVIEW"),
        "Platform: " + str(report.get("platform") or "မသိ"),
    ]
    total = report.get("total_estimated_seconds")
    if total is not None:
        lines.append("စုစုပေါင်း Script ခန့်မှန်းချိန်: " + _format_duration(total))
    srt = report.get("srt") or {}
    if srt.get("duration_seconds") is not None:
        lines.append("SRT နောက်ဆုံးအချိန်: " + _format_duration(srt["duration_seconds"]))
    lines.extend(["", "【အောင်မြင်သော စစ်ဆေးချက်များ】"])
    lines.extend("• " + item for item in report.get("passed") or [])
    lines.extend(["", "【ပြင်ဆင်ရန်】"])
    lines.extend("• " + item for item in report.get("issues") or [])
    if not report.get("issues"):
        lines.append("• ဖွဲ့စည်းပုံနှင့် ခန့်မှန်းကြာချိန်အရ ပြဿနာမတွေ့ပါ။ လူကိုယ်တိုင် နောက်ဆုံးစစ်ဆေးရန် လိုသည်။")
    lines.extend(["", str(report.get("disclaimer") or "")])
    return "\n".join(lines)
