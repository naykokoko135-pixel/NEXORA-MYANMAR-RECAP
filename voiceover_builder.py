"""Build a structured voice-over draft from creator-supplied, checked facts.

This is a deterministic organizer, not an AI writer, translator, or fact checker.
"""
import re

MIN_FACT_LINES = 6
PLACEHOLDER_MARKERS = (
    "[ထည့်ရန်]", "[ထည့်ပါ]", "[ဇာတ်ကားနဲ့ ပြန်စစ်ထားတဲ့ ဖြစ်ရပ်တွေ ထည့်ပါ]",
    "[add ", "[insert ", "[placeholder", "todo", "tbd",
)


def _clean_notes(notes: str) -> list[str]:
    lines = []
    for raw in (notes or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if any(line.lower().startswith(marker.lower()) for marker in PLACEHOLDER_MARKERS):
            continue
        line = re.sub(r"^(?:[-*•✓]|\d+[.)])\s*", "", line).strip()
        if line:
            lines.append(line)
    return lines


def _split_three_parts(lines: list[str]) -> list[list[str]]:
    """Split ordered notes into three balanced groups without changing their text."""
    parts = [[], [], []]
    for index, line in enumerate(lines):
        parts[min(index * 3 // len(lines), 2)].append(line)
    return parts


def generate_voiceover_draft(title: str, notes: str) -> str:
    safe_title = " ".join((title or "").split()).strip()
    if not safe_title:
        raise ValueError("ဇာတ်ကားအမည် ထည့်ပါ။")
    if not (notes or "").strip():
        raise ValueError("စစ်ဆေးထားသော Research Notes ထည့်ပါ။")
    if len(notes) > 12000:
        raise ValueError("Research Notes သည် စာလုံး ၁၂,၀၀၀ ထက် မကျော်ရပါ။")

    lines = _clean_notes(notes)
    if len(lines) < MIN_FACT_LINES:
        raise ValueError(
            "မှတ်စု မလုံလောက်သေးပါ။ ဇာတ်ကားနဲ့ ပြန်စစ်ထားတဲ့ အချက်အလက် "
            "အနည်းဆုံး ၆ ကြောင်း ထည့်ပါ။ Part 1 (နောက်ခံ/ဇာတ်ကောင်), "
            "Part 2 (ပဋိပက္ခ/အလှည့်အပြောင်း), Part 3 (Climax/အဆုံးသတ်) "
            "အလိုက် အစဉ်လိုက်ရေးပါ။ Wikipedia ရလဒ်တိုများသာ မလုံလောက်ပါ။"
        )

    parts = _split_three_parts(lines)
    labels = (
        ("PART 1 — မိတ်ဆက်၊ နောက်ခံနှင့် ဇာတ်ကောင်များ",
         "အရင်ဆုံး ဇာတ်လမ်းရဲ့ နောက်ခံနဲ့ အဓိကဇာတ်ကောင်တွေကို ကြည့်ကြရအောင်။"),
        ("PART 2 — အဓိကပြဿနာနှင့် ပဋိပက္ခ",
         "ဒီအခြေအနေကနေ ဇာတ်လမ်းရဲ့ အဓိကပြဿနာနဲ့ ပဋိပက္ခတွေ ဆက်လက်ဖြစ်ပေါ်လာပါတယ်။"),
        ("PART 3 — Climax၊ အဆုံးသတ်နှင့် သုံးသပ်ချက်",
         "နောက်ဆုံးမှာတော့ ဇာတ်လမ်းရဲ့ အရေးကြီးဆုံးအလှည့်အပြောင်းနဲ့ အဆုံးသတ်ကို ရောက်လာပါတယ်။"),
    )

    sections = []
    for (heading, transition), part_lines in zip(labels, parts):
        sections.append(
            f"{heading}\n{transition}\n\n" + "\n\n".join(part_lines)
        )

    return (
        f"🎙️ NEXORA — Structured Voice-over Draft\n"
        f"ခေါင်းစဉ်: {safe_title}\n"
        f"အချက်အလက်: Creator ထည့်သွင်းပြီး စစ်ဆေးထားသော Notes {len(lines)} ကြောင်း\n\n"
        "⚠️ အရေးကြီး: ဒီဖိုင်သည် AI ဇာတ်ညွှန်းရေးသားမှု၊ ဘာသာပြန်မှု သို့မဟုတ် "
        "Fact-check မဟုတ်ပါ။ သင်ပေးထားသော Notes စာသားကိုသာ အစဉ်လိုက် "
        "သုံးပိုင်းခွဲထားပြီး ချိတ်ဆက်စကား အနည်းငယ် ထည့်ထားခြင်းဖြစ်သည်။ "
        "အချက်အလက်အသစ် မဖန်တီးပါ။ ၁၅–၂၀ မိနစ်ကြာမည်ဟုလည်း အာမမခံပါ။\n\n"
        "မိတ်ဆက်\nဒီနေ့မှာတော့ " + safe_title +
        " ဇာတ်ကားရဲ့ အကြောင်းအရာကို အပိုင်းသုံးပိုင်းခွဲပြီး ပြန်လည်တင်ပြသွားပါမယ်။\n\n"
        + "\n\n━━━━━━━━━━━━━━━━━━\n\n".join(sections)
        + "\n\nနိဂုံးချုပ်\nဒီဇာတ်ကားရဲ့ အဆုံးသတ်နဲ့ ဇာတ်ကောင်တွေရဲ့ ရလဒ်ကို "
        "သုံးသပ်ပြီးပါပြီ။ ဒီဇာတ်ကားအပေါ် သင့်ရဲ့ ကိုယ်ပိုင်အမြင်ကိုလည်း "
        "စစ်ဆေးထားတဲ့ ဖြစ်ရပ်တွေနဲ့ ခွဲခြားပြီး ထည့်သွင်းပြောနိုင်ပါတယ်။\n\n"
        "မထုတ်ဝေမီ စစ်ဆေးရန်\n"
        "- အချက်အလက်တိုင်းကို ဇာတ်ကားနှင့် ယုံကြည်ရသော Source များဖြင့် ပြန်စစ်ပါ။\n"
        "- မသေချာသောအချက်ကို အမှန်ဟု မပြောပါနှင့်။\n"
        "- ကိုယ်ပိုင်သုံးသပ်ချက်ကို ဇာတ်လမ်းအချက်အလက်မှ ခွဲခြားပါ။\n"
        "- အသုံးပြုမည့် ရုပ်ပုံ၊ ဗီဒီယိုနှင့် အသံများအတွက် လိုအပ်သော ခွင့်ပြုချက် ရှိစေပါ။\n"
    )



def generate_voiceover_part_files(title: str, notes: str) -> list[str]:
    """Return three separate text drafts, preserving all supplied notes."""
    combined = generate_voiceover_draft(title, notes)
    safe_title = " ".join((title or "").split()).strip()
    divider = "\\n\\n━━━━━━━━━━━━━━━━━━\\n\\n"
    sections = combined.split(divider)
    if len(sections) != 3:
        raise ValueError("Voice-over အပိုင်း ၃ ပိုင်း ခွဲမရပါ။ Notes ကို ပြန်စစ်ပါ။")
    warning = (
        "မှတ်ချက်: စစ်ဆေးထားသော Notes ကိုသာ စီစဉ်ထားခြင်းဖြစ်ပြီး "
        "AI ရေးသားမှု သို့မဟုတ် Fact-check မဟုတ်ပါ။\\n\\n"
    )
    return [
        f"NEXORA — {safe_title} — PART {index}/3\\n\\n{warning}{section.strip()}\\n"
        for index, section in enumerate(sections, start=1)
    ]
