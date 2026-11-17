PLATFORM_NAMES = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "facebook": "Facebook",
}

DURATION_PRESETS = {
    "1-3": "၁–၃", "3-5": "၃–၅", "5-7": "၅–၇",
    "8-10": "၈–၁၀", "10-15": "၁၀–၁၅", "12-15": "၁၂–၁၅",
    "15-20": "၁၅–၂၀", "20-30": "၂၀–၃၀",
    "30-45": "၃၀–၄၅", "45-60": "၄၅–၆၀",
}

PLATFORM_DURATIONS = {
    "youtube": ("8-10", "12-15", "15-20", "20-30", "30-45", "45-60"),
    "tiktok": ("1-3", "3-5"),
    "facebook": ("3-5", "5-7", "8-10", "10-15"),
}

DEFAULT_DURATIONS = {"youtube": "15-20", "tiktok": "1-3", "facebook": "5-7"}

PLATFORM_GUIDES = {
    "youtube": "YouTube Long-form ပုံစံဖြင့် ဇာတ်လမ်းကို အစဉ်လိုက်၊ အကြောင်းရင်းနှင့် အကျိုးဆက်ကို ရှင်းပြပါ။ အပိုင်းတစ်ခုစီအဆုံးတွင် နောက်တစ်ဆင့်ကို စိတ်ဝင်စားစေမည့် ဆက်စပ်ချက်ထားပါ။",
    "tiktok": "ပထမစက္ကန့်များတွင် Hook ကို တိုတိုထိထိထားပါ။ အဓိကအချက်တစ်ခုကိုသာ အာရုံစိုက်ပြီး စာတန်းဖတ်ရလွယ်စေပါ။",
    "facebook": "အစပိုင်းတွင် စိတ်ဝင်စားဖွယ်မေးခွန်းထည့်ပါ။ အကြောင်းအရာကို အပိုင်းတိုများခွဲပြီး Comment မေးခွန်းဖြင့် အဆုံးသတ်ပါ။",
}


def _duration_plan(duration: str) -> str:
    if duration in {"8-10", "12-15"}:
        return """အချိန်ခွဲဝေမှု အကြံပြုချက်
- Hook နှင့် မိတ်ဆက်: ၅–၁၀%
- ဇာတ်ကောင်/နောက်ခံ: ၁၀–၁၅%
- အဓိကဖြစ်ရပ်များ: ၅၀–၅၅%
- Climax နှင့် အဆုံးသတ်: ၁၅–၂၀%
- သုံးသပ်ချက်/Outro: ကျန်အချိန်"""
    if duration in {"15-20", "20-30"}:
        return """အခန်းလိုက် တည်ဆောက်ရန်
- အခန်း ၁: Hook၊ ဇာတ်လမ်းနောက်ခံနှင့် အဓိကဇာတ်ကောင်
- အခန်း ၂: ပြဿနာစတင်ပေါ်ပေါက်လာပုံ
- အခန်း ၃: အရေးကြီးဖြစ်ရပ်များနှင့် ဇာတ်ကောင်ဆုံးဖြတ်ချက်များ
- အခန်း ၄: အလှည့်အပြောင်းနှင့် ပဋိပက္ခမြင့်တက်လာပုံ
- အခန်း ၅: Climax၊ အဆုံးသတ်နှင့် သုံးသပ်ချက်
အခန်းတိုင်းတွင် ဖြစ်ရပ်၊ အကြောင်းရင်း၊ အကျိုးဆက်နှင့် ဇာတ်ကောင်တုံ့ပြန်မှုကို ထည့်ပါ။"""
    if duration in {"30-45", "45-60"}:
        return """အခန်းလိုက် အသေးစိတ် Long-form အစီအစဉ်
- အခန်း ၁: Hook နှင့် ဇာတ်လမ်း၏ အဓိကမေးခွန်း
- အခန်း ၂: ကမ္ဘာတည်ဆောက်မှု၊ အချိန်ကာလ၊ နေရာနှင့် ဇာတ်ကောင်နောက်ခံ
- အခန်း ၃: ဇာတ်လမ်းစတင်သည့် အကြောင်းရင်းနှင့် ပထမဆုံးပဋိပက္ခ
- အခန်း ၄: အရေးကြီးဖြစ်ရပ်များ၊ ဆက်စပ်ဇာတ်ကောင်များနှင့် ဆုံးဖြတ်ချက်များ
- အခန်း ၅: အလယ်ပိုင်းအလှည့်အပြောင်းနှင့် အကျိုးဆက်များ
- အခန်း ၆: ပဋိပက္ခမြင့်တက်လာပုံ၊ သဲလွန်စများနှင့် ဇာတ်ကောင်ပြောင်းလဲမှု
- အခန်း ၇: Climax နှင့် အဓိကပြဿနာဖြေရှင်းပုံ
- အခန်း ၈: အဆုံးသတ်နှင့် ကိုယ်ပိုင်သုံးသပ်ချက်
အခန်းတစ်ခုချင်းစီကို ထပ်ခါထပ်ခါမပြောပါနှင့်။ ဇာတ်လမ်းအချက်အလက်မှန်ကန်မှုကို ဦးစားပေးပါ။"""
    return "Hook၊ အဓိကဖြစ်ရပ်များ၊ အလှည့်အပြောင်းနှင့် အဆုံးသတ်ကို ရှင်းလင်းစွာ ထည့်ပါ။"


def generate_recap_outline(topic: str, platform: str = "youtube", duration: str = "15-20") -> str:
    """Create a Burmese recap worksheet without inventing plot facts."""
    safe_topic = " ".join((topic or "").split()).strip() or "[ဇာတ်ကား/ဇာတ်လမ်းအမည်]"
    platform = platform if platform in PLATFORM_NAMES else "youtube"
    if duration not in PLATFORM_DURATIONS[platform]:
        duration = DEFAULT_DURATIONS[platform]
    longform = platform == "youtube"
    return f"""🎬 NEXORA Myanmar Recap — Free Script Builder

ခေါင်းစဉ်: {safe_topic}
Platform: {PLATFORM_NAMES[platform]}
ပုံစံ: {"Detailed Cinematic Long-form Recap" if longform else "Short-form Cinematic Recap"}
ရည်မှန်းချိန်: {DURATION_PRESETS[duration]} မိနစ်

━━━━━━━━━━━━━━━━━━
⚠️ SPOILER WARNING
ဤဗီဒီယိုတွင် ဇာတ်လမ်းအကြောင်းအရာနှင့် spoiler များ ပါဝင်နိုင်ပါသည်။

၁။ OPENING HOOK
[အသံနေအသံထား: စိတ်ဝင်စားဖွယ်၊ တည်ငြိမ်ပြီး ဆွဲဆောင်မှုရှိစွာ]
ဒီဇာတ်လမ်းမှာ ထူးခြားတာက ဘာလဲ။
ကြည့်ရှုသူကို ဆက်ကြည့်ချင်လာစေမယ့် မေးခွန်း:
“[မေးခွန်း/စိတ်ဝင်စားဖွယ်အချက်]”

၂။ ဇာတ်လမ်းနောက်ခံနှင့် ဇာတ်ကောင်များ
- နေရာနှင့် အချိန်ကာလ:
- အဓိကဇာတ်ကောင်:
- ဇာတ်ကောင်၏ ရည်ရွယ်ချက်:
- အစပိုင်းပြဿနာ:
- အခြားအရေးကြီးဇာတ်ကောင်များ:

၃။ {"အသေးစိတ်ဇာတ်လမ်းအခန်းများ" if longform else "အဓိကဇာတ်လမ်း"}
[ဖြစ်ရပ်များကို အစဉ်လိုက်၊ ကိုယ်ပိုင်စကားဖြင့် ရှင်းပြပါ]
- အစပြုဖြစ်ရပ်နှင့် အကြောင်းရင်း:
- အရေးကြီးဖြစ်ရပ်များ:
- ဇာတ်ကောင်၏ ဆုံးဖြတ်ချက်များ:
- ဖြစ်ရပ်တစ်ခုမှ နောက်တစ်ခုသို့ ဆက်စပ်ပုံ:
- အခြေအနေပြောင်းလဲသွားသည့်အချိန်:
- ကြည့်ရှုသူနားလည်ရန် လိုအပ်သော နောက်ခံအချက်များ:

၄။ CLIMAX / အလှည့်အပြောင်း
- အဓိကပဋိပက္ခ:
- ဇာတ်ကောင်ရင်ဆိုင်ရသည့် ရွေးချယ်မှု:
- အလှည့်အပြောင်းဖြစ်စေသည့် အချက်:
- အကျိုးဆက်နှင့် ဖြေရှင်းပုံ:

၅။ ဇာတ်ကောင်နှင့် အဓိပ္ပာယ်ဖော်ထုတ်ချက်
- ဇာတ်ကောင် ဘယ်လိုပြောင်းလဲသွားသလဲ:
- ဇာတ်လမ်း၏ အဓိကအယူအဆ:
- အားကောင်းသော ဇာတ်ဝင်ခန်း/အကြောင်းအရာ:
- ကိုယ်ပိုင်သုံးသပ်ချက်:

၆။ အဆုံးသတ် / REVIEW
- ဇာတ်လမ်း၏ အားသာချက်:
- တိုးတက်နိုင်သည့်အချက်:
- ကြည့်ရှုသူကို စဉ်းစားစေမည့် နောက်ဆုံးအမြင်:

၇။ OUTRO / CTA
“ဒီဇာတ်လမ်းအပေါ် သင့်အမြင်ကို Comment မှာ မျှဝေပေးပါ။
နောက်ထပ် Recap တွေအတွက် Follow လုပ်ထားနိုင်ပါတယ်။”

━━━━━━━━━━━━━━━━━━
⏱️ ရည်မှန်းကြာချိန်အလိုက် အစီအစဉ်
{_duration_plan(duration)}

📱 PLATFORM အလိုက် အကြံပြုချက်
{PLATFORM_GUIDES[platform]}

🎞️ VISUAL & EDITING PLAN
- အခန်းတစ်ခုစီအတွက် ကိုယ်ပိုင်ဖန်တီးထားသော ခေါင်းစဉ်/အခန်းခွဲ
- ခွင့်ပြုချက်ရှိသော ပုံ၊ ဗီဒီယိုနှင့် တေးဂီတကိုသာ အသုံးပြုရန်
- အရေးကြီးအချက်များကို ကိုယ်ပိုင်စာတန်းဖြင့် ဖော်ပြရန်
- အသံနှင့် တည်းဖြတ်မှုကို သဘာဝကျစွာ ထိန်းရန်
- အခန်းကူးပြောင်းမှုများကို ရှင်းလင်းစွာထားရန်

✅ PUBLISH မလုပ်မီ စစ်ဆေးရန်
[ ] ဇာတ်လမ်းအချက်အလက်များကို ယုံကြည်ရသော source ဖြင့် စစ်ဆေးပြီးပြီ။
[ ] မသေချာသော ဇာတ်ကွက်အသေးစိတ်ကို မခန့်မှန်းထားပါ။
[ ] Script ကို ကိုယ်ပိုင်စကားဖြင့် ရေးထားသည်။
[ ] မူရင်း dialogue၊ script သို့မဟုတ် အခြားသူ၏ recap ကို မကူးထားပါ။
[ ] အသုံးပြုမည့် footage၊ music နှင့် ပုံများအတွက် ခွင့်ပြုချက်/လိုင်စင် ရှိသည်။
[ ] တင်မည့် platform ၏ မူပိုင်ခွင့်စည်းမျဉ်းများကို စစ်ဆေးပြီးပြီ။

မှတ်ချက်: ဤ Free Builder သည် ဇာတ်လမ်းအချက်အလက်ကို အလိုအလျောက် ရှာဖွေခြင်း သို့မဟုတ် AI ဖြင့် အတည်ပြုခြင်း မလုပ်ပါ။ ဖြည့်စွက်ရန်နေရာများကို စစ်ဆေးထားသော အချက်အလက်နှင့် ကိုယ်ပိုင်သုံးသပ်ချက်ဖြင့် ဖြည့်ပါ။

━━━━━━━━━━━━━━━━━━
🌍 ENGLISH SUBTITLE WORKSHEET
အသံ: မြန်မာဘာသာ | စာတန်းထိုး: English
အလိုအလျောက် ဘာသာပြန်ခြင်း မပါဝင်ပါ။ စစ်ဆေးပြီးသော English ဘာသာပြန်ကို ဖြည့်ပါ။

Subtitle အပိုင်း ၁
အချိန်: 00:00:00,000 --> 00:00:05,000
မြန်မာအသံစာသား: [မြန်မာစာကြောင်း]
English Subtitle: [English translation]

SRT FORMAT နမူနာ
1
00:00:00,000 --> 00:00:05,000
[English subtitle text]

စာတန်းထိုးစစ်ဆေးရန်
[ ] English စာကြောင်းသည် မြန်မာအသံနှင့် အဓိပ္ပာယ်တူသည်။
[ ] စာတန်းဖတ်ရလွယ်သော အရှည်ဖြစ်သည်။
[ ] အချိန်အမှတ်များသည် အသံနှင့် ကိုက်ညီသည်။
[ ] အမည်များ၊ နေရာများနှင့် ဇာတ်လမ်းအချက်အလက်များကို စစ်ဆေးပြီးပြီ။
"""


# Known title metadata is intentionally conservative. Unknown titles are never
# assigned a genre from their name alone.
TITLE_CLASSIFICATIONS = {
    "pororo": ("3D Animation / Children's Series", "South Korea"),
    "pororo the little penguin": ("3D Animation / Children's Series", "South Korea"),
    "larva": ("3D Animation / Comedy Series", "South Korea"),
    "pucca": ("Animated Comedy Series", "South Korea"),
    "the haunted house: the secret of the ghost ball": ("3D Animation / Fantasy Series", "South Korea"),
    "leafie, a hen into the wild": ("2D Animated Film", "South Korea"),
    "miraculous: tales of ladybug & cat noir": ("3D CGI Animated Series", "France"),
    "shaun the sheep": ("Stop-motion Animated Series", "United Kingdom"),
    "klaus": ("2D Animated Film", "Spain"),
    "motu patlu": ("3D Animation / Comedy Series", "India"),
    "chhota bheem": ("2D Animated Children's Series", "India"),
    "the king's avatar": ("Donghua", "China"),
    "soul land": ("Donghua / 3D Animation", "China"),
    "the daily life of the immortal king": ("Donghua", "China"),
    "battle through the heavens": ("Donghua / 3D Animation", "China"),
    "perfect world": ("Donghua / 3D Animation", "China"),
    "link click": ("Donghua", "China"),
    "heaven official's blessing": ("Donghua", "China"),
    "fog hill of five elements": ("Donghua", "China"),
}


def classify_recap_title(topic: str) -> tuple[str, str]:
    """Return verified known category/region or an explicit verification label."""
    key = " ".join((topic or "").casefold().split()).strip()
    return TITLE_CLASSIFICATIONS.get(
        key, ("အမျိုးအစားကို ရင်းမြစ်ဖြင့် အတည်ပြုရန်", "နိုင်ငံ/ဒေသကို ရင်းမြစ်ဖြင့် အတည်ပြုရန်")
    )


def generate_all_platform_plan(topic: str) -> str:
    """Create explicit three-part duration plans for YouTube, Facebook, and TikTok."""
    safe_topic = " ".join((topic or "").split()).strip() or "[ဇာတ်လမ်းအမည်]"
    category, region = classify_recap_title(safe_topic)
    return f"""🎬 NEXORA — PLATFORM သုံးခုလုံးအတွက် Recap အစီအစဉ်

ခေါင်းစဉ်: {safe_topic}
အမျိုးအစား: {category}
နိုင်ငံ/ဒေသ: {region}

━━━━━━━━━━━━━━━━━━
1) YOUTUBE — Long-form Recap
စုစုပေါင်း: ၃ ပိုင်း | တစ်ပိုင်းလျှင် ၈–၁၀ မိနစ် | စုစုပေါင်း ၂၄–၃၀ မိနစ်
- Part 1 (၈–၁၀ မိနစ်): Hook၊ ဇာတ်လမ်းကမ္ဘာ/နောက်ခံ၊ ဇာတ်ကောင်မိတ်ဆက်၊ အစပြုဖြစ်ရပ်။
- Part 2 (၈–၁၀ မိနစ်): အဓိကပြဿနာ၊ ဇာတ်ကောင်ဆုံးဖြတ်ချက်များ၊ turning points နှင့် အကျိုးဆက်။
- Part 3 (၈–၁၀ မိနစ်): Climax၊ ဖြေရှင်းပုံ၊ အဆုံးသတ် (သတ်မှတ်ထားသော season/film အတွင်းသာ) နှင့် ကိုယ်ပိုင်သုံးသပ်ချက်။

2) FACEBOOK — Mid-form Recap
စုစုပေါင်း: ၃ ပိုင်း | တစ်ပိုင်းလျှင် ၃–၅ မိနစ် | စုစုပေါင်း ၉–၁၅ မိနစ်
- Part 1 (၃–၅ မိနစ်): စိတ်ဝင်စားဖွယ် Hook၊ နောက်ခံနှင့် အဓိကဇာတ်ကောင်။
- Part 2 (၃–၅ မိနစ်): အဓိကပဋိပက္ခ၊ အရေးကြီးဖြစ်ရပ်နှင့် အလှည့်အပြောင်း။
- Part 3 (၃–၅ မိနစ်): အကျိုးဆက်၊ climax/အဆုံးသတ်အကျဉ်းနှင့် သုံးသပ်ချက်။

3) TIKTOK — Short-form Recap
စုစုပေါင်း: ၃ ပိုင်း | တစ်ပိုင်းလျှင် ၁–၃ မိနစ် | စုစုပေါင်း ၃–၉ မိနစ်
- Part 1 (၁–၃ မိနစ်): အားကောင်းသော Hook၊ ဇာတ်ကောင်နှင့် စတင်ဖြစ်ရပ်။
- Part 2 (၁–၃ မိနစ်): အဓိကပြဿနာနှင့် အရေးကြီး turning point တစ်ခု။
- Part 3 (၁–၃ မိနစ်): ရလဒ်/အဆုံးသတ်အကျဉ်းနှင့် ကိုယ်ပိုင်အမြင်။

━━━━━━━━━━━━━━━━━━
ထုတ်လုပ်မှုစည်းမျဉ်း
- Platform တစ်ခုစီအတွက် သီးခြား edit၊ aspect ratio၊ caption၊ title နှင့် thumbnail/cover ပြင်ဆင်ရန်။
- ဇာတ်လမ်းတစ်ခု၏ Part 1/2/3 အကြောင်းအရာကို platform အလိုက် အတို/အရှည် ပြန်လည်တည်းဖြတ်ပါ။ တူညီသောဖိုင်ကို အားလုံးသို့ တိုက်ရိုက်တင်ခြင်း မလုပ်ပါနှင့်။
- Anime episode/season၊ 3D film၊ cartoon series၊ donghua arc တို့၏ အပိုင်းအကန့်အသတ်ကို အစတွင် ရှင်းလင်းဖော်ပြပါ။
- ဖြစ်ရပ်အချက်အလက်၊ ဇာတ်ကောင်အမည်နှင့် အစဉ်လိုက်ကို ရင်းမြစ်နှင့် ပြန်စစ်ပါ။ မသိသောအချက်ကို မခန့်မှန်းပါနှင့်။
- ကိုယ်ပိုင်သုံးသပ်ချက်နှင့် အဓိပ္ပာယ်ဖော်ပြချက် ထည့်ပါ။ မူရင်း dialogue/script သို့မဟုတ် အခြားသူ၏ recap ကို မကူးပါနှင့်။
- ကိုယ်ပိုင်၊ လိုင်စင်ရ သို့မဟုတ် အသုံးပြုခွင့်ရှိသော visual/audio ကိုသာ အသုံးပြုပါ။

မှတ်ချက်: ဤ command သည် ကြာချိန်နှင့် အပိုင်းခွဲ worksheet ကိုသာ ထုတ်ပေးသည်။ ဗီဒီယိုဖိုင်ဖန်တီးခြင်း၊ AI voice၊ platform များသို့ အလိုအလျောက် upload လုပ်ခြင်း မပါဝင်သေးပါ။
""";
