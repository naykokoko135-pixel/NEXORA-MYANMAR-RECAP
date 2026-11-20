"""Scene-by-scene Burmese voice assignment for NEXORA.

Scene headers may use a delivery preset or a character-role alias. Aliases map
onto the existing Nilar/Thiha voice presets; they are not new speaker identities.
"""
import re

from tts_builder import VOICE_PRESETS, MAX_TEXT_CHARS
from voxcpm_voice_design import VOICE_DESIGNS

MAX_SCENES = 8
HEADER_RE = re.compile(r"^\[([^\[\]\r\n]+)\]\s*$")

ROLE_PRESETS = {
    "narrator": "narrator",
    "protagonist": "hero",
    "male_lead": "hero",
    "heroine": "female",
    "female_lead": "female",
    "antagonist": "villain",
    "supporting": "calm",
    "elder": "elder",
    "child": "youth",
    "comic": "comedy",
    "suspense": "mystery",
    "action": "energetic",
    "ဇာတ်ကြောင်း": "narrator",
    "မိတ်ဆက်": "narrator",
    "မင်းသား": "hero",
    "သူရဲကောင်း": "hero",
    "မင်းသမီး": "female",
    "အမျိုးသမီး": "female",
    "ဗီလိန်": "villain",
    "လူကြီး": "elder",
    "ကလေး": "youth",
    "ဟာသ": "comedy",
    "လျှို့ဝှက်": "mystery",
    "အက်ရှင်": "energetic",
}


def parse_scene_script(script: str) -> list[dict]:
    """Parse one [preset-or-role] header per scene."""
    scenes = []
    current_role = None
    current_preset = None
    current_lines = []

    def flush():
        nonlocal current_lines
        text = "\n".join(current_lines).strip()
        if text:
            scenes.append({
                "role": current_role,
                "preset": current_preset,
                "text": text,
            })
        current_lines = []

    for raw_line in (script or "").splitlines():
        line = raw_line.strip()
        match = HEADER_RE.fullmatch(line)
        if match:
            flush()
            current_role = match.group(1).lower()
            current_preset = ROLE_PRESETS.get(current_role, current_role)
            if current_preset not in VOICE_PRESETS:
                raise ValueError(
                    f"အသံ Role/Preset မသိပါ: {current_role}။ /voices မှ ရွေးပါ။"
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
            raise ValueError(f"အခန်း {index} စာသားသည် စာလုံး ၈၀,၀၀၀ ထက် ကျော်နေပါတယ်။")
    return scenes



def parse_voice_design_scene_script(script: str) -> list[dict]:
    """Parse [ai:voice_name] headers for fictional VoxCPM2 scene voices."""
    scenes = []
    current_voice = None
    current_lines = []
    total_chars = 0
    max_scenes = 4
    max_scene_chars = 1500
    max_total_chars = 6000

    def flush():
        nonlocal current_lines, total_chars
        text = "\n".join(current_lines).strip()
        if text:
            scenes.append({
                "voice": current_voice,
                "text": text,
            })
            total_chars += len(text)
        current_lines = []

    for raw_line in (script or "").splitlines():
        line = raw_line.strip()
        match = HEADER_RE.fullmatch(line)
        if match:
            flush()
            header = match.group(1).strip().lower()
            if not header.startswith("ai:"):
                raise ValueError("AI အသံအတွက် [ai:story_female] ပုံစံ ခေါင်းစဉ်သုံးပါ။")
            current_voice = header[3:].strip()
            if current_voice not in VOICE_DESIGNS:
                raise ValueError(f"AI Voice မသိပါ: {current_voice}။ /voices မှ ရွေးပါ။")
            if len(scenes) >= max_scenes:
                raise ValueError("AI ဇာတ်ဝင်ခန်း အများဆုံး ၄ ခန်းသာ ခွင့်ပြုပါတယ်။")
        elif line:
            if current_voice is None:
                raise ValueError("စာသားမရေးမီ [ai:story_female] ကဲ့သို့ AI အသံခေါင်းစဉ်တပ်ပါ။")
            current_lines.append(line)

    flush()
    if not scenes:
        raise ValueError("AI ဇာတ်ဝင်ခန်းစာသား မတွေ့ပါ။")
    if len(scenes) > max_scenes:
        raise ValueError("AI ဇာတ်ဝင်ခန်း အများဆုံး ၄ ခန်းသာ ခွင့်ပြုပါတယ်။")
    if total_chars > max_total_chars:
        raise ValueError("AI ဇာတ်ဝင်ခန်းအားလုံးပေါင်း စာလုံး ၆,၀၀၀ ထက် မကျော်ရပါ။")
    for index, scene in enumerate(scenes, start=1):
        if len(scene["text"]) > max_scene_chars:
            raise ValueError(f"AI အခန်း {index} စာသားသည် စာလုံး ၁,၅၀၀ ထက် မကျော်ရပါ။")
    return scenes
