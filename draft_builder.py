"""Turn creator-supplied research notes into structured recap worksheets.

These helpers do not invent plot details, browse the web, or generate a finished
narrative. They preserve supplied notes and provide chapter prompts.
"""

from script_writer import PLATFORM_NAMES, PLATFORM_DURATIONS, DEFAULT_DURATIONS, DURATION_PRESETS


def _clean_inputs(topic: str, notes: str) -> tuple[str, str]:
    title = " ".join((topic or "").split()).strip() or "[ဇာတ်ကားအမည်]"
    clean_notes = (notes or "").strip()
    if not clean_notes:
        raise ValueError("Research မှတ်စု မပါသေးပါ။ /draft Avatar ပြီးနောက် စာကြောင်းအသစ်မှ မှတ်စုများ ထည့်ပါ။")
    if len(clean_notes) > 10000:
        raise ValueError("မှတ်စုသည် ရှည်လွန်းနေပါသည်။ ၁၀,၀၀၀ အက္ခရာအောက် ခွဲပို့ပါ။")
    return title, clean_notes


def _selected_preset(platform: str, duration: str) -> tuple[str, str]:
    platform = platform if platform in PLATFORM_NAMES else "youtube"
    if duration not in PLATFORM_DURATIONS[platform]:
        duration = DEFAULT_DURATIONS[platform]
    return platform, duration


def generate_draft_worksheet(topic: str, notes: str, platform: str = "youtube", duration: str = "15-20") -> str:
    title, clean_notes = _clean_inputs(topic, notes)
    platform, duration = _selected_preset(platform, duration)

    if platform == "youtube":
        chapters = [
            ("အခန်း ၁ — Hook နှင့် ဇာတ်လမ်းနောက်ခံ", "ဇာတ်လမ်း၏ အဓိကမေးခွန်း၊ နေရာ/အချိန်နှင့် ဇာတ်ကောင်ရည်ရွယ်ချက်ကို မိတ်ဆက်ပါ။"),
            ("အခန်း ၂ — ပြဿနာ စတင်ပေါ်ပေါက်လာပုံ", "အစပြုဖြစ်ရပ်၊ အကြောင်းရင်းနှင့် ပထမဆုံးအကျိုးဆက်ကို ဆက်စပ်ရှင်းပြပါ။"),
            ("အခန်း ၃ — အရေးကြီးဖြစ်ရပ်များ", "ဇာတ်ကောင်ဆုံးဖြတ်ချက်များနှင့် ဖြစ်ရပ်တစ်ခုမှ နောက်တစ်ခုသို့ ဆက်စပ်ပုံကို ရှင်းပြပါ။"),
            ("အခန်း ၄ — အလှည့်အပြောင်းနှင့် ပဋိပက္ခ", "အခြေအနေပြောင်းလဲသည့်အချက်၊ ပဋိပက္ခမြင့်တက်လာပုံနှင့် ဇာတ်ကောင်တုံ့ပြန်မှုကို ဖော်ပြပါ။"),
            ("အခန်း ၅ — Climax၊ အဆုံးသတ်နှင့် သုံးသပ်ချက်", "အဓိကပဋိပက္ခ၏ ဖြေရှင်းပုံ၊ ဇာတ်ကောင်ပြောင်းလဲမှုနှင့် ကိုယ်ပိုင်အမြင်ကို ထည့်ပါ။"),
        ]
    else:
        chapters = [
            ("အပိုင်း ၁ — Hook နှင့် မိတ်ဆက်", "စိတ်ဝင်စားဖွယ်မေးခွန်းနှင့် ဇာတ်လမ်းနောက်ခံကို တိုတိုရှင်းရှင်း ဖော်ပြပါ။"),
            ("အပိုင်း ၂ — အဓိကပြဿနာ", "ပြဿနာစတင်ပုံနှင့် ဇာတ်ကောင်၏ ရည်ရွယ်ချက်ကို ရှင်းပြပါ။"),
            ("အပိုင်း ၃ — အလှည့်အပြောင်းနှင့် အဆုံးသတ်", "အရေးကြီးဖြစ်ရပ်၊ အကျိုးဆက်နှင့် ကိုယ်ပိုင်သုံးသပ်ချက်ကို ချိတ်ဆက်ပါ။"),
        ]

    chapter_text = "\n\n".join(
        f"{heading}\n- ရေးရန်: {prompt}\n- မှတ်စုမှ အသုံးပြုမည့် အချက်: [သက်ဆိုင်ရာမှတ်စုကို ရွေးပါ]\n- ကိုယ်ပိုင်ရှင်းပြချက်/သုံးသပ်ချက်: [ထည့်ရန်]\n- နောက်အပိုင်းသို့ ဆက်စပ်ချက်: [ထည့်ရန်]"
        for heading, prompt in chapters
    )

    return f"""📝 NEXORA — Research Notes မှ Recap Draft Worksheet

ခေါင်းစဉ်: {title}
Platform: {PLATFORM_NAMES[platform]}
ရည်မှန်းချိန်: {DURATION_PRESETS[duration]} မိနစ်

အရေးကြီးမှတ်ချက်: အောက်ပါမှတ်စုများကို သင်ပေးထားသည့်အတိုင်းသာ ထည့်သွင်းထားသည်။ NEXORA က ဇာတ်လမ်းအချက်အလက်များကို သီးခြားအတည်မပြုထားသလို အချက်အလက်အသစ်များကိုလည်း မဖန်တီးပါ။

━━━━━━━━━━━━━━━━━━
၁။ သင်ပေးထားသော Research Notes

{clean_notes}

━━━━━━━━━━━━━━━━━━
၂။ အခန်းလိုက် Recap Draft တည်ဆောက်ရန်

{chapter_text}

━━━━━━━━━━━━━━━━━━
၃။ မရေးမီ ပြန်စစ်ရန်
[ ] အခန်းတိုင်းရှိ အချက်အလက်ကို source နှင့် ပြန်တိုက်စစ်ပြီးပြီ။
[ ] အကြောင်းရင်း၊ ဖြစ်ရပ်နှင့် အကျိုးဆက် ဆက်စပ်မှု မှန်ကန်သည်။
[ ] ကိုယ်ပိုင်ရှင်းပြချက်နှင့် သုံးသပ်ချက် ပါဝင်သည်။
[ ] မူရင်း dialogue၊ screenplay သို့မဟုတ် အခြားသူ၏ recap ကို မကူးထားပါ။
[ ] အသုံးပြုမည့် ပုံ၊ footage နှင့် music အတွက် အသုံးပြုခွင့်ရှိသည်။

နောက်တစ်ဆင့်: အခန်းတစ်ခုစီကို ကိုယ်ပိုင်စကားဖြင့် ပြည့်စုံအောင် ရေးပြီး အချက်အလက်နှင့် subtitle ကို လူကိုယ်တိုင် ပြန်စစ်ဆေးပါ。
"""


def generate_three_part_draft_worksheets(topic: str, notes: str, duration: str = "15-20") -> str:
    """Create three distinct YouTube planning worksheets from creator-checked notes."""
    title, clean_notes = _clean_inputs(topic, notes)
    total_minutes = DURATION_PRESETS[duration] if duration in PLATFORM_DURATIONS["youtube"] else DURATION_PRESETS[DEFAULT_DURATIONS["youtube"]]
    part_minutes = max(1, round(total_minutes / 3))
    sections = [
        (
            "PART 1 — မိတ်ဆက်၊ နောက်ခံနှင့် ဇာတ်ကောင်များ",
            "ဇာတ်လမ်းစတင်ရာ နေရာ/အချိန်၊ အဓိကဇာတ်ကောင်များ၊ သူတို့၏ ရည်ရွယ်ချက်နှင့် အစပြုအခြေအနေကို ကိုယ်ပိုင်စကားဖြင့် မိတ်ဆက်ပါ။",
            "ဇာတ်လမ်းနောက်ခံ၊ ဇာတ်ကောင်အမည်/ရည်ရွယ်ချက်၊ အစပြုဖြစ်ရပ်",
        ),
        (
            "PART 2 — အဓိကပြဿနာနှင့် ပဋိပက္ခ",
            "အဓိကပြဿနာ ဘယ်လိုဖြစ်လာသည်၊ ဇာတ်ကောင်များ၏ ဆုံးဖြတ်ချက်များနှင့် အကျိုးဆက်များကို အကြောင်းရင်း-အကျိုးဆက်အလိုက် ဆက်စပ်ရေးပါ။",
            "အတည်ပြုထားသော ဖြစ်ရပ်များ၊ ပဋိပက္ခ၊ အလှည့်အပြောင်းများ",
        ),
        (
            "PART 3 — Climax၊ အဆုံးသတ်နှင့် ကိုယ်ပိုင်သုံးသပ်ချက်",
            "နောက်ဆုံးပဋိပက္ခ၏ ဖြေရှင်းပုံ၊ ဇာတ်ကောင်များ၏ ပြောင်းလဲမှုနှင့် ကိုယ်ပိုင်သုံးသပ်ချက်ကို ရေးပါ။ မသေချာသည့်အချက်ကို မခန့်မှန်းပါနှင့်။",
            "Climax၊ အဆုံးသတ်၊ ဇာတ်ကောင်ရလဒ်နှင့် သုံးသပ်ချက်",
        ),
    ]
    parts = []
    for index, (heading, prompt, focus) in enumerate(sections, start=1):
        parts.append(
            f"━━━━━━━━━━━━━━━━━━\n🎬 {heading}\n"
            f"ရည်မှန်းချိန်: ခန့်မှန်း {part_minutes} မိနစ် (စုစုပေါင်း {total_minutes} မိနစ် worksheet)\n"
            f"ရေးရန်: {prompt}\n"
            f"အဓိကထားရန်: {focus}\n"
            "- Source မှ အတည်ပြုထားသောအချက်: [ထည့်ရန်]\n"
            "- ကိုယ်ပိုင်ရှင်းပြချက်/သုံးသပ်ချက်: [ထည့်ရန်]\n"
            "- နောက် Part သို့ ဆက်စပ်ချက်: [ထည့်ရန်]\n"
            "- မသေချာသောအချက်နှင့် စစ်ဆေးရမည့် Source: [ထည့်ရန်]"
        )
    return (
        f"📝 NEXORA — YouTube သုံးပိုင်းခွဲ Draft Worksheets\n"
        f"ခေါင်းစဉ်: {title}\nစုစုပေါင်းရည်မှန်းချိန်: {total_minutes} မိနစ်\n\n"
        "မှတ်ချက်: အောက်ပါသည် ဇာတ်ညွှန်းအပြည့်မဟုတ်ဘဲ သီးခြားဖြည့်စွက်ရန် Worksheet သုံးခုဖြစ်သည်။ "
        "သင်ပေးထားသော Research Notes ကိုသာ အခြေခံပြီး NEXORA က ဇာတ်လမ်းအသစ် မဖန်တီးပါ။\n\n"
        "၁။ မျှဝေထားသော Research Notes\n" + clean_notes + "\n\n"
        + "\n\n".join(parts)
        + "\n\nမထုတ်ဝေမီ ဇာတ်ကားနှင့် Source များကို ပြန်စစ်ပြီး ကိုယ်ပိုင်ဝေဖန်သုံးသပ်ချက် ထည့်ပါ။"
    )
