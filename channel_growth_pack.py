"""Create an ethical, source-aware channel publishing pack for NEXORA.

This module improves packaging and production QA; it does not promise reach or
invent plot facts, trend rankings, views, ratings, or audience reactions.
"""

CATEGORIES = {
    "anime": "Anime",
    "3d animation": "3D Animation",
    "cartoon": "Cartoon",
    "donghua": "Donghua",
    "international movies": "International Movies (Live-action)",
}
PLATFORMS = {"youtube": "YouTube", "facebook": "Facebook", "tiktok": "TikTok"}
MAX_TITLE = 140
MAX_SUMMARY = 1000


def _clean(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def generate_growth_pack(title: str, category: str, platform: str = "youtube", summary: str = "") -> str:
    """Build accurate title/description/thumbnail/hook and QA suggestions."""
    title = _clean(title)
    category_key = _clean(category).casefold()
    platform_key = _clean(platform).casefold()
    summary = _clean(summary)

    if not title or len(title) > MAX_TITLE:
        raise ValueError("ခေါင်းစဉ်ကို ၁ မှ ၁၄၀ စာလုံးအတွင်း ထည့်ပါ။")
    if category_key not in CATEGORIES:
        raise ValueError("Category ကို Anime, 3D Animation, Cartoon, Donghua, International Movies ထဲမှ ရွေးပါ။")
    if platform_key not in PLATFORMS:
        raise ValueError("Platform ကို youtube, facebook, tiktok ထဲမှ ရွေးပါ။")
    if len(summary) > MAX_SUMMARY:
        raise ValueError("ဇာတ်လမ်းအကျဉ်းသည် စာလုံး ၁၀၀၀ ထက် မကျော်ရပါ။")

    category_name = CATEGORIES[category_key]
    platform_name = PLATFORMS[platform_key]
    short = platform_key == "tiktok"
    if short:
        pacing = (
            "0–2 sec: အဓိက Hook\n2–8 sec: ဇာတ်လမ်းအခြေအနေ\n"
            "8–35 sec: အတည်ပြုထားသော အရေးကြီးအချက် ၂–၃ ခု\n"
            "နောက်ဆုံး: အဖြေ/အလှည့်အပြောင်းနှင့် တိုတောင်းသော CTA"
        )
        title_options = [
            f"{title} — ဇာတ်လမ်းအကျဉ်း",
            f"{title} ကို မိနစ်တိုအတွင်း နားလည်ရအောင်",
            f"{title} | မြန်မာ Recap",
        ]
    elif platform_key == "facebook":
        pacing = (
            "အစ ၃–၅ sec: အကြောင်းအရာကို တိတိကျကျပြောသော Hook\n"
            "နောက်ပိုင်း: အပိုဒ်တိုများ၊ ဖတ်ရလွယ်သော စာတန်းများ၊ အရေးကြီးအချက်များကို အစဉ်လိုက်\n"
            "အဆုံး: အကျဉ်းချုပ်နှင့် ဆွေးနွေးရန် မေးခွန်း"
        )
        title_options = [
            f"{title} — မြန်မာလို ဇာတ်လမ်းအကျဉ်း",
            f"{title} | အဓိကဇာတ်လမ်းကို ရှင်းပြမယ်",
            f"{title} Recap — အစမှ အဆုံး",
        ]
    else:
        pacing = (
            "0–15 sec: ခေါင်းစဉ်/Thumbnail ကတိပေးထားသည့်အကြောင်းအရာကို တန်းပြောပါ\n"
            "15–60 sec: ဇာတ်လမ်းနောက်ခံနှင့် အဓိကမေးခွန်း\n"
            "အလယ်ပိုင်း: အကြောင်းရင်း → ဖြစ်ရပ် → အကျိုးဆက် အစဉ်လိုက်\n"
            "အဆုံးပိုင်း: အဆုံးသတ်၊ ကိုယ်ပိုင်သုံးသပ်ချက်၊ နောက်ဗီဒီယိုသို့ ချိတ်ဆက်မှု"
        )
        title_options = [
            f"{title} ဇာတ်လမ်းအကျဉ်း | မြန်မာ Recap",
            f"{title} — အစမှ အဆုံး ဇာတ်လမ်းရှင်းပြချက်",
            f"{title} ကို မြန်မာလို နားလည်လွယ်အောင် Recap",
        ]

    if summary:
        description_summary = summary
        hook = f"ဒီ Recap မှာ {title} ရဲ့ အတည်ပြုထားတဲ့ ဇာတ်လမ်းအချက်အလက်တွေကို မြန်မာလို အစဉ်လိုက် ရှင်းပြထားပါတယ်။"
    else:
        description_summary = "[အတည်ပြုပြီးသော ဇာတ်လမ်းအကျဉ်းကို ဤနေရာတွင် ကိုယ်ပိုင်စကားဖြင့် ထည့်ပါ။]"
        hook = f"{title} ရဲ့ အဓိကဇာတ်လမ်းက ဘာလဲဆိုတာ ဒီ Recap မှာ အစဉ်လိုက် ရှင်းပြပါမယ်။ [အတည်ပြုထားသော ထူးခြားချက်တစ်ခု ထည့်ပါ။]"

    category_tags = {
        "anime": "#AnimeRecap #AnimeMyanmar",
        "3d animation": "#3DAnimation #AnimationRecap",
        "cartoon": "#CartoonRecap #CartoonMyanmar",
        "donghua": "#DonghuaRecap #DonghuaMyanmar",
        "international movies": "#MovieRecap #InternationalMovies",
    }[category_key]
    tags = f"#NEXORAMyanmarRecap {category_tags} #မြန်မာRecap"
    if platform_key == "youtube":
        tags += " #MyanmarSubtitle"
    description = (
        f"{title} ကို မြန်မာဘာသာဖြင့် အကျဉ်းချုပ်တင်ဆက်ထားသော {category_name} Recap ဖြစ်ပါတယ်။\n\n"
        f"{description_summary}\n\n"
        "ဤဗီဒီယိုတွင် ကိုယ်ပိုင်ရှင်းလင်းချက်နှင့် သုံးသပ်ချက်များ ပါဝင်သည်။ "
        "ဇာတ်လမ်းအချက်အလက်နှင့် အသုံးပြုထားသော မီဒီယာရင်းမြစ်/လိုင်စင်ကို မထုတ်ဝေမီ စစ်ဆေးပါ။\n\n"
        f"{tags}"
    )
    return f"""🚀 NEXORA — {platform_name} CHANNEL GROWTH PACK

ခေါင်းစဉ်: {title}
Category: {category_name}
Platform: {platform_name}

၁။ ခေါင်းစဉ်ရွေးချယ်စရာ (အကြောင်းအရာနှင့် ကိုက်ညီသည့်တစ်ခုကို ရွေးပါ)
""" + "\n".join(f"{i}. {value}" for i, value in enumerate(title_options, 1)) + f"""

၂။ Opening Hook
{hook}

၃။ Description (အသင့်ပြင်ဆင်ရန်)
{description}

၄။ Thumbnail / Cover အကြံပြုချက်
- အဓိကအကြောင်းအရာတစ်ခုတည်းကို ရှင်းလင်းစွာပြပါ။
- စာသား ၂–၅ လုံးခန့်သာထားပြီး ဖုန်းမျက်နှာပြင်သေးသေးတွင် ဖတ်လို့ရစေပါ။
- ကိုယ်ပိုင်ဖန်တီးထားသော သို့မဟုတ် အသုံးပြုခွင့်ရှိသော ပုံကိုသာ သုံးပါ။
- အကြောင်းအရာကို မမှန်မကန်ဖော်ပြသော ပုံ၊ မရှိသောဇာတ်ကွက်ကို အရိပ်အမြွက်ပေးသောပုံ မသုံးပါနှင့်။
- အရောင်၊ ဖောင့်နှင့် NEXORA အမှတ်တံဆိပ်ကို ဗီဒီယိုတိုင်းတွင် တစ်သမတ်တည်းထားပါ။

၅။ ကြည့်ရှုသူဆက်လက်ကြည့်စေမည့် တင်ဆက်ပုံ
{pacing}
- အကြောင်းအရာအသစ်တစ်ခုစီတွင် သက်ဆိုင်သော အချက်အလက်/ရှင်းလင်းချက် ထည့်ပါ။
- မလိုအပ်သော Intro၊ ထပ်ခါထပ်ခါပြောခြင်းနှင့် အချိန်ဆွဲခြင်းကို ဖယ်ပါ။
- Hook ကတိပေးထားသည့်အရာကို ဗီဒီယိုအတွင်း အမှန်တကယ်ဖြည့်ဆည်းပါ။

၆။ Comment မေးခွန်း
“ဒီဇာတ်လမ်းထဲက ဘယ်အချက်ကို စိတ်ဝင်စားဆုံးလဲ။ ကိုယ့်အမြင်ကို မျှဝေပေးပါ။”

၇။ Upload မတိုင်မီ အရည်အသွေးစစ်ဆေးရန်
[ ] ခေါင်းစဉ်နှင့် Thumbnail သည် ဗီဒီယိုအကြောင်းအရာကို မှန်ကန်စွာ ကိုယ်စားပြုသည်။
[ ] ပထမပိုင်းတွင် အဓိကအကြောင်းအရာကို မြန်မြန်ရောက်သည်။
[ ] ဇာတ်လမ်းအချက်အလက်၊ အမည်၊ အစဉ်လိုက်နှင့် Ending ကို ရင်းမြစ်ဖြင့် ပြန်စစ်ပြီးပြီ။
[ ] မြန်မာအသံနှင့် စာတန်းထိုး အချိန်ကိုက်သည်။
[ ] အသုံးပြုထားသော Video/Image/Music အားလုံးတွင် ခွင့်ပြုချက် သို့မဟုတ် သင့်လျော်သော လိုင်စင်ရှိသည်။
[ ] မူရင်းဇာတ်ညွှန်း၊ Dialogue သို့မဟုတ် အခြား Creator ၏ Recap ကို မကူးထားပါ။
[ ] ဗီဒီယိုကို အစမှအဆုံး ပြန်ကြည့်ပြီး အသံ/ပုံ/စာတန်းကို စစ်ပြီးပြီ။

၈။ ထုတ်ဝေပြီးနောက် စောင့်ကြည့်ရန်
- Impressions နှင့် CTR: ခေါင်းစဉ်/Thumbnail ဆွဲဆောင်မှုကို နားလည်ရန်
- ပထမ ၃၀ စက္ကန့် Audience Retention: အစပိုင်း Hook အလုပ်လုပ်/မလုပ် စစ်ရန်
- Average View Duration နှင့် Retention Graph: ဘယ်နေရာတွင် ကြည့်ရှုသူထွက်သွားသလဲ စစ်ရန်
- Comments နှင့် Returning Viewers: ပရိသတ်နှစ်သက်သည့်အကြောင်းအရာကို သိရန်
- ရလဒ်မကောင်းပါက အကြောင်းရင်းကို စမ်းသပ်ပြီး ပြင်ဆင်ပါ။ Views/Like ကို အတုလုပ်ခြင်း မလုပ်ပါနှင့်။

မှတ်ချက်: ဤ Pack သည် ထုတ်ဝေမှုအတွက် အကြံပြုချက်နှင့် Template ဖြစ်သည်။ Live trend, အမှန်တကယ် view count, like count သို့မဟုတ် အောင်မြင်မှုကို မခန့်မှန်းပါ။ ပရိသတ်ရလဒ်ကို အာမမခံပါ။
"""
