"""Measure actual audio duration with the repository's bundled FFmpeg runtime."""
import os
import re
import subprocess

DURATION_RE = re.compile(r"Duration:\s*(\d{2,}):(\d{2}):(\d{2}(?:\.\d+)?)")
AUDIO_STREAM_RE = re.compile(r"\bAudio:\s*([\w, ]+)", re.IGNORECASE)
PLATFORM_LIMITS = {
    "youtube": (46 * 60, 60 * 60),
    "facebook": (46 * 60, 60 * 60),
    "tiktok": (4 * 60, 7 * 60),
}
ALIASES = {"yt": "youtube", "fb": "facebook", "tt": "tiktok"}
MAX_AUDIO_BYTES = 20 * 1024 * 1024


def parse_ffmpeg_audio_metadata(stderr_text):
    """Extract container duration and presence of an audio stream from FFmpeg output."""
    text = str(stderr_text or "")
    duration_match = DURATION_RE.search(text)
    audio_match = AUDIO_STREAM_RE.search(text)
    if not duration_match:
        raise ValueError("Audio file ၏ ကြာချိန်ကို ဖတ်မရပါ။")
    if not audio_match:
        raise ValueError("Audio stream မတွေ့ပါ။ Audio ဖိုင်ကိုသာ reply လုပ်ပါ။")
    hours, minutes, seconds = duration_match.groups()
    if int(minutes) > 59 or float(seconds) >= 60:
        raise ValueError("Audio duration metadata မမှန်ပါ။")
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if duration <= 0:
        raise ValueError("Audio duration သည် သုညထက် ကြီးရပါမည်။")
    return {
        "duration_seconds": round(duration, 3),
        "audio_stream": audio_match.group(1).strip(),
    }


def inspect_audio_file(path, timeout_seconds=90):
    """Decode the audio stream to FFmpeg's null sink and return measured container duration."""
    if not path or not os.path.isfile(path):
        raise ValueError("Audio file မတွေ့ပါ။")
    size = os.path.getsize(path)
    if size <= 0 or size > MAX_AUDIO_BYTES:
        raise ValueError("Audio file သည် ဗလာဖြစ်နေသည် သို့မဟုတ် 20 MB ထက် ကျော်နေသည်။")
    try:
        import imageio_ffmpeg
        executable = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("Bundled FFmpeg မရရှိပါ။") from exc
    try:
        result = subprocess.run(
            [executable, "-hide_banner", "-i", path, "-map", "0:a:0", "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=max(5, min(int(timeout_seconds), 120)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Audio decode စစ်ဆေးမှု အချိန်ကျော်သွားသည်။") from exc
    combined = (result.stderr or "") + "\n" + (result.stdout or "")
    metadata = parse_ffmpeg_audio_metadata(combined)
    if result.returncode != 0:
        raise ValueError("Audio decode စစ်ဆေးမှု မအောင်မြင်ပါ။ ဖိုင်ပျက်နေခြင်း သို့မဟုတ် format မထောက်ပံ့ခြင်း ဖြစ်နိုင်သည်။")
    metadata["file_size_bytes"] = size
    metadata["decode_ok"] = True
    return metadata


def evaluate_audio_duration(platform, duration_seconds):
    """Compare measured audio duration with NEXORA's current platform targets."""
    key = ALIASES.get(str(platform or "").strip().casefold(), str(platform or "").strip().casefold())
    if key not in PLATFORM_LIMITS:
        return {"status": "NOT READY", "platform": key, "issues": ["youtube/facebook/tiktok ကို ရွေးပါ။"]}
    try:
        duration = float(duration_seconds)
    except (TypeError, ValueError):
        return {"status": "NOT READY", "platform": key, "issues": ["Audio duration မမှန်ပါ။"]}
    minimum, maximum = PLATFORM_LIMITS[key]
    if duration < minimum:
        status = "TOO SHORT"
        issues = [f"Audio သည် သတ်မှတ်အနည်းဆုံး {_clock(minimum)} ထက် တိုနေသည်။"]
    elif duration > maximum:
        status = "TOO LONG"
        issues = [f"Audio သည် သတ်မှတ်အများဆုံး {_clock(maximum)} ထက် ရှည်နေသည်။"]
    else:
        status = "DURATION PASS"
        issues = []
    return {
        "status": status,
        "platform": key,
        "duration_seconds": round(duration, 3),
        "minimum_seconds": minimum,
        "maximum_seconds": maximum,
        "issues": issues,
    }


def _clock(seconds):
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, sec = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def format_audio_qa_report(platform, metadata, evaluation):
    duration = metadata.get("duration_seconds")
    lines = [
        "🎧 NEXORA — MEASURED AUDIO DURATION QA",
        "Platform: " + str(evaluation.get("platform") or platform),
        "အခြေအနေ: " + str(evaluation.get("status") or "REVIEW"),
    ]
    if duration is not None:
        lines.append("FFmpeg ဖြင့် တိုင်းတာထားသော Audio ကြာချိန်: " + _clock(duration))
    if metadata.get("audio_stream"):
        lines.append("Audio stream: " + metadata["audio_stream"])
    if metadata.get("decode_ok"):
        lines.append("Audio decode: အောင်မြင်သည်။")
    lines.extend(["", "【စစ်ဆေးချက်】"])
    lines.extend("• " + item for item in evaluation.get("issues") or [])
    if not evaluation.get("issues"):
        lines.append("• Platform ကြာချိန်သတ်မှတ်ချက်အတွင်း ရှိသည်။")
    lines.extend([
        "",
        "မှတ်ချက်:",
        "• ဤစစ်ဆေးမှုသည် တင်ပေးထားသော audio file ၏ container duration နှင့် decode ကိုသာ စစ်သည်။",
        "• Script ပြည့်စုံမှု၊ အသံထွက်အရည်အသွေး၊ SRT နှင့် စကားလုံးတစ်လုံးချင်း sync၊ plot facts၊ မူပိုင်ခွင့်ကို မစစ်နိုင်ပါ။",
        "• Publish မလုပ်မီ အသံကို နားထောင်ပြီး SRT နှင့် ကိုက်ညီမှုကို လူကိုယ်တိုင် စစ်ပါ။",
    ])
    return "\n".join(lines)



def evaluate_audio_parts(platform, durations):
    """Validate measured, separate final-deliverable audio parts.

    YouTube/Facebook require exactly three 15–20 minute parts and a
    46–60 minute combined duration. TikTok requires one 4–7 minute part.
    Durations must come from decoded audio measurements, not script estimates.
    """
    import math

    key = ALIASES.get(str(platform or "").strip().casefold(), str(platform or "").strip().casefold())
    if key not in PLATFORM_LIMITS:
        return {"status": "NOT READY", "platform": key, "parts": [], "issues": ["youtube/facebook/tiktok ကို ရွေးပါ။"]}
    expected_count = 1 if key == "tiktok" else 3
    part_min, part_max = ((4 * 60, 7 * 60) if key == "tiktok" else (15 * 60, 20 * 60))
    total_min, total_max = PLATFORM_LIMITS[key]
    if not isinstance(durations, (list, tuple)) or len(durations) != expected_count:
        actual = len(durations) if isinstance(durations, (list, tuple)) else 0
        return {
            "status": "NOT READY",
            "platform": key,
            "parts": [],
            "issues": [f"{key} အတွက် Audio အပိုင်း {expected_count} ပိုင်းတိတိ လိုအပ်သည်။ ရရှိသည်: {actual} ပိုင်း။"],
        }

    measured = []
    issues = []
    for index, value in enumerate(durations, start=1):
        if isinstance(value, bool):
            number = float("nan")
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                number = float("nan")
        if not math.isfinite(number) or number <= 0:
            issues.append(f"Part {index}: တိုင်းတာထားသော Audio duration မမှန်ပါ။")
            measured.append(None)
            continue
        measured.append(round(number, 3))
        if not part_min <= number <= part_max:
            issues.append(
                f"Part {index}: {_clock(number)} — {_clock(part_min)} မှ {_clock(part_max)} အတွင်း ဖြစ်ရပါမည်။"
            )

    total = sum(value for value in measured if value is not None)
    if any(value is None for value in measured):
        issues.append("အပိုင်းအားလုံး၏ Audio ကြာချိန်ကို အောင်မြင်စွာ မတိုင်းတာနိုင်သေးပါ။")
    elif not total_min <= total <= total_max:
        issues.append(f"စုစုပေါင်း {_clock(total)} — {_clock(total_min)} မှ {_clock(total_max)} အတွင်း ဖြစ်ရပါမည်။")

    return {
        "status": "DURATION PASS" if not issues else "DURATION FAIL",
        "platform": key,
        "parts": [{"part": index, "duration_seconds": value} for index, value in enumerate(measured, start=1)],
        "total_duration_seconds": round(total, 3),
        "part_minimum_seconds": part_min,
        "part_maximum_seconds": part_max,
        "total_minimum_seconds": total_min,
        "total_maximum_seconds": total_max,
        "issues": issues,
    }
