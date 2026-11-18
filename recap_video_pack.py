"""Input and metadata guards for longer licensed recap preview generation."""
MAX_RECAP_SCRIPT_CHARS = 6000
INDIAN_COUNTRY_NAMES = {"india", "republic of india"}

def parse_recap_video_request(message_text: str, available_presets) -> tuple[str, str, str]:
    if not isinstance(message_text, str):
        raise ValueError("Command စာသားကို မဖတ်နိုင်ပါ။")
    first_line, separator, body = message_text.partition("\n")
    parts = first_line.strip().split(maxsplit=1)
    title = parts[1].strip() if len(parts) > 1 else ""
    if not title or len(title) > 120:
        raise ValueError("အသုံးပြုပုံ: /recapvideo <ခေါင်းစဉ်> ပြီးနောက် narration ထည့်ပါ။")
    lines = body.strip().splitlines() if separator else []
    preset = "narrator"
    if lines and lines[0].strip().lower() in available_presets:
        preset = lines.pop(0).strip().lower()
    narration = "\n".join(lines).strip()
    if not narration:
        raise ValueError("အသုံးပြုပုံ: /recapvideo <ခေါင်းစဉ်>\nnarrator\nကိုယ်တိုင်ရေးထားသော မြန်မာ narration...")
    if len(narration) > MAX_RECAP_SCRIPT_CHARS:
        raise ValueError("Narration သည် စာလုံး ၆,၀၀၀ ထက် မကျော်ရပါ။ အပိုင်းခွဲပါ။")
    return title, preset, narration

def validate_non_indian_wikidata_metadata(metadata: dict) -> list[str]:
    if not isinstance(metadata, dict) or not metadata.get("found"):
        raise ValueError((metadata or {}).get("status", "Wikidata အတည်ပြုချက် မရရှိပါ။"))
    countries = metadata.get("countries")
    if not isinstance(countries, list):
        raise ValueError("Wikidata မူရင်းနိုင်ငံ မရရှိပါ။ မခန့်မှန်းထားပါ။")
    normalized = [str(country).strip() for country in countries if str(country).strip()]
    if not normalized:
        raise ValueError("Wikidata မူရင်းနိုင်ငံ မရရှိပါ။ မခန့်မှန်းထားပါ။")
    if any(country.casefold() in INDIAN_COUNTRY_NAMES for country in normalized):
        raise ValueError("အိန္ဒိယ သို့မဟုတ် အိန္ဒိယပူးတွဲထုတ်လုပ်မှုကို ဒီ Project မှာ မထည့်ပါ။")
    return normalized
