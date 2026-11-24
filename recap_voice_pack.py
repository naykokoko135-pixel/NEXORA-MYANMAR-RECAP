"""Input parsing for a creator-written Burmese recap voice pack."""
MAX_RECAP_SCRIPT_CHARS = 80000

def parse_recap_voice_request(message_text: str, available_presets) -> tuple[str, str]:
    if not isinstance(message_text, str):
        raise ValueError("Command စာသားကို မဖတ်နိုင်ပါ။")
    first_line, separator, script = message_text.partition("\n")
    parts = first_line.strip().split(maxsplit=2)
    preset = parts[1].strip().lower() if len(parts) > 1 else "narrator"
    # "myvoice" may be followed by a saved profile name; the profile is
    # resolved by the Telegram handler, while this parser validates the mode.
    if preset.startswith("myvoice "):
        preset = "myvoice"
    narration = script.strip() if separator else ""
    if not narration:
        raise ValueError(
            "အသုံးပြုပုံ: /recapvoice [preset] ပြီးနောက် စာကြောင်းအသစ်မှ ကိုယ်တိုင်ရေးထားသော မြန်မာ narration ထည့်ပါ။\n"
            "ဥပမာ: /recapvoice narrator\nဒီနေ့ ဇာတ်လမ်းရဲ့ အဓိကဖြစ်ရပ်ကို ပြောပြပါမယ်။"
        )
    if len(narration) > MAX_RECAP_SCRIPT_CHARS:
        raise ValueError("Narration စာသားသည် စာလုံး ၈၀,၀၀၀ ထက် မကျော်ရပါ။ အပိုင်းခွဲပြီး ထုတ်ပါ။")
    if preset != "myvoice" and preset not in available_presets:
        raise ValueError("Voice preset မမှန်ပါ။ /voices ဖြင့် ရရှိနိုင်သော preset များကို ကြည့်ပါ။")
    return preset, narration


def parse_recap_voice_parts_request(message_text: str, available_presets):
    """Parse three creator-written long-form parts for YouTube/Facebook TTS."""
    import re

    if not isinstance(message_text, str):
        raise ValueError("Command စာသားကို မဖတ်နိုင်ပါ။")
    first_line, separator, package = message_text.partition("\n")
    command = first_line.strip().split(maxsplit=1)
    preset = command[1].strip().lower() if len(command) > 1 else "narrator"
    if preset != "myvoice" and preset not in available_presets:
        raise ValueError("Voice preset မမှန်ပါ။ /voices ဖြင့် ရရှိနိုင်သော preset များကို ကြည့်ပါ။")
    if not separator or not package.strip():
        raise ValueError(
            "အသုံးပြုပုံ: /recapvoice3 [preset] ပြီးနောက် [PART 1], [PART 2], [PART 3] ဖြင့် "
            "ခွဲထားသော Script ကို ထည့်ပါ။"
        )

    parts = {}
    current = None
    for raw in package.replace("\r", "").splitlines():
        match = re.fullmatch(r"\s*\[PART\s*(\d+)\]\s*", raw, re.IGNORECASE)
        if match:
            number = int(match.group(1))
            if number in parts:
                raise ValueError(f"[PART {number}] ကို နှစ်ကြိမ်ထပ်ထည့်ထားသည်။")
            parts[number] = []
            current = number
        elif current is not None:
            parts[current].append(raw)
        elif raw.strip():
            raise ValueError("Script စာသားမတိုင်မီ [PART 1] marker ကို ထည့်ပါ။")

    if set(parts) != {1, 2, 3}:
        raise ValueError("YouTube/Facebook အတွက် [PART 1], [PART 2], [PART 3] သုံးပိုင်းတိတိ လိုအပ်သည်။")
    cleaned = {number: "\n".join(lines).strip() for number, lines in parts.items()}
    if any(not text for text in cleaned.values()):
        raise ValueError("Part 1 မှ Part 3 အထိ Script တစ်ပိုင်းစီတွင် စာသားပါဝင်ရပါမည်။")
    if sum(len(text) for text in cleaned.values()) > MAX_RECAP_SCRIPT_CHARS:
        raise ValueError("Part အားလုံးပေါင်း Script သည် စာလုံး ၈၀,၀၀၀ ထက် မကျော်ရပါ။")
    return preset, cleaned
