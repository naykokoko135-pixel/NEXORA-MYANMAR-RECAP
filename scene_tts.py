"""Scene-by-scene Burmese voice assignment for NEXORA.

Each [preset] heading starts a new independently generated scene track.
Presets alter delivery using the two currently available Burmese neural voices;
they do not create additional speaker identities.
"""
import re

from tts_builder import VOICE_PRESETS, MAX_TEXT_CHARS

MAX_SCENES = 8
HEADER_RE = re.compile(r"^\\[([a-zA-Z_-]+)\\]\\s*$")


def parse_scene_script(script: str) -> list[dict]:
    """Parse a script containing one [preset] header per scene."""
    scenes = []
    current_preset = None
    current_lines = []

    def flush():
        nonlocal current_lines
        text = "\\n".join(current_lines).strip()
        if text:
            scenes.append({"preset": current_preset, "text": text})
        current_lines = []

    for raw_line in (script or "").splitlines():
        line = raw_line.strip()
        match = HEADER_RE.fullmatch(line)
        if match:
            flush()
            current_preset = match.group(1).lower()
            if current_preset not in VOICE_PRESETS:
                raise ValueError(
                    f"အသံ Preset မသိပါ: {current_preset}။ /voices မှ ရွေးပါ။"
                )
            if len(scenes) >= MAX_SCENES:
                raise ValueError(f"ဇာတ်ဝင်ခန်း အများဆုံး {MAX_SCENES} ခန်းသာ ခွင့်ပြုပါတယ်။")
        elif line:
            if current_preset is None:
                raise ValueError("စာသားမရေးမီ [narrator] ကဲ့သို့ အသံခေါင်းစဉ်တပ်ပါ။")
            current_lines.append(line)

    flush()
    if not scenes:
        raise ValueError("ဇာတ်ဝင်ခန်းစာသား မတွေ့ပါ။")
    if len(scenes) > MAX_SCENES:
        raise ValueError(f"ဇာတ်ဝင်ခန်း အများဆုံး {MAX_SCENES} ခန်းသာ ခွင့်ပြုပါတယ်။")
    for index, scene in enumerate(scenes, start=1):
        if len(scene["text"]) > MAX_TEXT_CHARS:
            raise ValueError(f"အခန်း {index} စာသားသည် စာလုံး ၆,၀၀၀ ထက် ကျော်နေပါတယ်။")
    return scenes
