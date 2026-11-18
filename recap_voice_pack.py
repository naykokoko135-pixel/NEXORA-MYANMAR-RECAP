"""Input parsing for a creator-written Burmese recap voice pack."""
MAX_RECAP_SCRIPT_CHARS = 6000

def parse_recap_voice_request(message_text: str, available_presets) -> tuple[str, str]:
    if not isinstance(message_text, str):
        raise ValueError("Command စာသားကို မဖတ်နိုင်ပါ။")
    first_line, separator, script = message_text.partition("\n")
    parts = first_line.strip().split(maxsplit=1)
    preset = parts[1].strip().lower() if len(parts) > 1 else "narrator"
    narration = script.strip() if separator else ""
    if not narration:
        raise ValueError(
            "အသုံးပြုပုံ: /recapvoice [preset] ပြီးနောက် စာကြောင်းအသစ်မှ ကိုယ်တိုင်ရေးထားသော မြန်မာ narration ထည့်ပါ။\n"
            "ဥပမာ: /recapvoice narrator\nဒီနေ့ ဇာတ်လမ်းရဲ့ အဓိကဖြစ်ရပ်ကို ပြောပြပါမယ်။"
        )
    if len(narration) > MAX_RECAP_SCRIPT_CHARS:
        raise ValueError("Narration စာသားသည် စာလုံး ၆,၀၀၀ ထက် မကျော်ရပါ။ အပိုင်းခွဲပြီး ထုတ်ပါ။")
    if preset not in available_presets:
        raise ValueError("Voice preset မမှန်ပါ။ /voices ဖြင့် ရရှိနိုင်သော preset များကို ကြည့်ပါ။")
    return preset, narration
