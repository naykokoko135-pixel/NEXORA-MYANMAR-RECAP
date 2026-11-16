"""Turn creator-supplied research notes into a structured recap drafting worksheet.

This module does not invent plot details, browse the web, or generate a finished
narrative. It preserves the supplied notes and gives the creator a chapter plan.
"""

from script_writer import PLATFORM_NAMES, PLATFORM_DURATIONS, DEFAULT_DURATIONS, DURATION_PRESETS


def generate_draft_worksheet(topic: str, notes: str, platform: str = "youtube", duration: str = "15-20") -> str:
    title = " ".join((topic or "").split()).strip() or "[ဇာတ်ကားအမည်]"
    clean_notes = (notes or "").strip()
    if not clean_notes:
        raise ValueError("Research မှတ်စု မပါသေးပါ။ /draft Avatar ပြီးနောက် စာကြောင်းအသစ်မှ မှတ်စုများ ထည့်ပါ။")
    if len(clean_notes) > 10000:
        raise ValueError("မှတ်စုသည် ရှည်လွန်းနေပါသည်။ ၁၀,၀၀၀ အက္ခရာအောက် ခွဲပို့ပါ။")

    platform = platform if platform in PLATFORM_NAMES else "youtube"
    if duration not in PLATFORM_DURATIONS[platform]:
        duration = DEFAULT_DURATIONS[platform]

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

နောက်တစ်ဆင့်: အခန်းတစ်ခုစီကို ကိုယ်ပိုင်စကားဖြင့် ပြည့်စုံအောင် ရေးပြီး အချက်အလက်နှင့် subtitle ကို လူကိုယ်တိုင် ပြန်စစ်ဆေးပါ။
"""
