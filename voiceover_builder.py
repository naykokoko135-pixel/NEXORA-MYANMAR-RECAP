"""Build a voice-over draft using only creator-supplied, checked facts.

This is a deterministic formatter, not an AI writer or fact checker.
"""


def generate_voiceover_draft(title: str, notes: str) -> str:
    safe_title = " ".join((title or "").split()).strip()
    raw_notes = (notes or "").strip()
    if not safe_title:
        raise ValueError("ဇာတ်ကားအမည် ထည့်ပါ။")
    if not raw_notes:
        raise ValueError("အသုံးပြုပုံ: /voiceover Avatar ပြီးနောက် စစ်ဆေးထားသော ဖြစ်ရပ်များကို စာကြောင်းတစ်ကြောင်းစီ ထည့်ပါ။")
    if len(raw_notes) > 9000:
        raise ValueError("Research Notes သည် စာလုံး ၉,၀၀၀ ထက် မကျော်ရပါ။")

    lines = []
    for line in raw_notes.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        for prefix in ("- ", "* ", "• ", "✓ ", "1. ", "2. ", "3. "):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
        if cleaned:
            lines.append(cleaned)

    if not lines:
        raise ValueError("စစ်ဆေးထားသော Research Notes မတွေ့ပါ။")

    paragraphs = []
    for index, line in enumerate(lines):
        if line.startswith(("PART 1", "PART 2", "PART 3", "အပိုင်း ၁", "အပိုင်း ၂", "အပိုင်း ၃")):
            paragraphs.append(f"\n{line}")
        else:
            paragraphs.append(line)

    body = "\n\n".join(paragraphs)
    return (
        f"🎙️ NEXORA — Voice-over Script Draft\n"
        f"ခေါင်းစဉ်: {safe_title}\n\n"
        "⚠️ မူကြမ်းမှတ်ချက်: အောက်ပါစာသားသည် သင်ထည့်သွင်းထားသော Notes ကို "
        "အသံဖတ်ရန် စီစဉ်ထားခြင်းသာ ဖြစ်သည်။ NEXORA က ဇာတ်ကွက်အသစ်၊ "
        "ဇာတ်ကောင်ရလဒ် သို့မဟုတ် မသေချာသောအချက်များကို မဖြည့်စွက်ပါ။\n\n"
        f"မိတ်ဆက်\nဒီနေ့မှာတော့ {safe_title} ဇာတ်ကားရဲ့ အကြောင်းအရာကို "
        "အစဉ်လိုက် ပြန်လည်တင်ပြသွားပါမယ်။\n\n"
        f"ဇာတ်လမ်းပြောပြချက်\n{body}\n\n"
        "နိဂုံးချုပ်\nဒီဇာတ်ကားနဲ့ပတ်သက်ပြီး သင့်ရဲ့အမြင်ကိုလည်း "
        "ကိုယ်ပိုင်စကားနဲ့ ထည့်သွင်းသုံးသပ်နိုင်ပါတယ်။\n\n"
        "မထုတ်ဝေမီ စစ်ဆေးရန်\n"
        "- ဖြစ်ရပ်တိုင်းကို ဇာတ်ကားနှင့် ယုံကြည်ရသော Source များဖြင့် ပြန်စစ်ပါ။\n"
        "- ကိုယ်ပိုင်သုံးသပ်ချက်ကို သီးခြားထည့်ပါ။\n"
        "- အသုံးပြုမည့် ရုပ်ပုံ၊ ဗီဒီယိုနှင့် အသံများအတွက် လိုအပ်သော ခွင့်ပြုချက် ရှိစေပါ။\n"
    )
