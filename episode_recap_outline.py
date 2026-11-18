"""Build a creator-facing recap outline from one verified TVMaze episode research lead.

This module does not write plot facts, translate provider summaries, or generate video.
It turns a short research lead into a structured worksheet for original narration.
"""

PLATFORM_DEFAULTS = {
    "youtube": ("15-20", ("8-10", "12-15", "15-20", "20-30", "30-45", "45-60")),
    "facebook": ("5-7", ("3-5", "5-7", "8-10", "10-15")),
    "tiktok": ("1-3", ("1-3", "3-5")),
}


def format_episode_recap_outline(research: dict, platform: str = "youtube", duration: str | None = None) -> str:
    """Format one top-rated animation episode as a Burmese creator worksheet."""
    if not isinstance(research, dict) or not research.get("found"):
        raise ValueError("အတည်ပြုထားသော TVmaze Episode research မရှိပါ။")
    title = str(research.get("title") or "").strip()
    country = str(research.get("country") or "").strip()
    episodes = research.get("episodes")
    if not title or not country or not isinstance(episodes, list) or not episodes:
        raise ValueError("Series title၊ နိုင်ငံနှင့် Episode အချက်အလက် မပြည့်စုံပါ။")
    if country.casefold() in {"india", "republic of india"}:
        raise ValueError("ဒီ Project မှာ အိန္ဒိယခေါင်းစဉ်များ မထည့်ထားပါ။")

    selected = episodes[0]
    episode_title = str(selected.get("title") or "").strip()
    source = str(selected.get("source") or research.get("provider_url") or "").strip()
    excerpt = str(selected.get("summary_excerpt") or "").strip()[:240]
    rating = selected.get("rating")
    if not episode_title or not source:
        raise ValueError("ရွေးချယ်ထားသော Episode ၏ အမည် သို့မဟုတ် Source URL မရရှိပါ။")
    if not isinstance(rating, (int, float)) or isinstance(rating, bool) or not 0 < rating <= 10:
        raise ValueError("မှန်ကန်သော TVmaze community rating မရှိပါ။")

    platform_key = str(platform or "youtube").strip().lower()
    if platform_key not in PLATFORM_DEFAULTS:
        platform_key = "youtube"
    default_duration, allowed = PLATFORM_DEFAULTS[platform_key]
    selected_duration = str(duration or default_duration).strip()
    if selected_duration not in allowed:
        selected_duration = default_duration

    season = selected.get("season") or "?"
    number = selected.get("number") or "?"
    airdate = selected.get("airdate") or "မဖော်ပြထား"
    platform_names = {"youtube": "YouTube", "facebook": "Facebook", "tiktok": "TikTok"}
    lines = [
        "📝 NEXORA — EPISODE RECAP OUTLINE WORKSHEET",
        f"Series: {title}",
        f"Country (TVmaze): {country}",
        f"ရွေးထားသော Episode: S{season} E{number} — {episode_title}",
        f"TVmaze community rating: {rating:.1f}/10 (View count မဟုတ်ပါ)",
        f"Air date: {airdate}",
        f"Platform: {platform_names[platform_key]} | ရည်မှန်းကြာချိန်: {selected_duration} မိနစ်",
        f"Episode source: {source}",
        "",
        "Research lead (အတိုချုံး — ဇာတ်လမ်းအချက်အလက်ကို မူရင်း Episode နှင့် ပြန်စစ်ပါ):",
        excerpt or "TVmaze မှ summary မရရှိပါ။ Episode ကို ကိုယ်တိုင်ကြည့်ရှုပြီး မှတ်စုရေးပါ။",
        "",
        "၁။ Opening Hook (ကိုယ်ပိုင်စကားဖြင့်)",
        "• ပထမ ၅–၁၅ စက္ကန့်အတွင်း စိတ်ဝင်စားစေမည့် မေးခွန်း သို့မဟုတ် အခြေအနေကို ရေးပါ။",
        "• အဆုံးရလဒ်ကို မကြိုတင်ဖော်ပြဘဲ အမှန်တကယ် Episode ထဲက အချက်ကိုသာ သုံးပါ။",
        "",
        "၂။ Setup နှင့် ဇာတ်ကောင်များ",
        "• Episode အစတွင် ဘယ်နေရာ၊ ဘယ်ဇာတ်ကောင်များ ပါဝင်သလဲ။",
        "• အဓိကရည်မှန်းချက် သို့မဟုတ် ပြဿနာက ဘာလဲ။",
        "",
        "၃။ အဓိကဖြစ်ရပ်များ (ကိုယ်တိုင်စစ်ဆေးထားသော အစဉ်လိုက်)",
        "• ဖြစ်ရပ် ၁ — ဘာဖြစ်သလဲ၊ ဘာကြောင့် အရေးကြီးသလဲ။",
        "• ဖြစ်ရပ် ၂ — ဇာတ်ကောင်၏ ဆုံးဖြတ်ချက်/တုံ့ပြန်မှု။",
        "• ဖြစ်ရပ် ၃ — အခြေအနေ ဘယ်လိုပြောင်းသွားသလဲ။",
        "",
        "၄။ Turning Point နှင့် Climax",
        "• အလှည့်အပြောင်းကို ဖြစ်စေသော အကြောင်းရင်း။",
        "• အဓိကတင်းမာမှု၏ ဖြေရှင်းပုံ (မူရင်း Episode နှင့် တိုက်စစ်ပါ)။",
        "",
        "၅။ Ending နှင့် ကိုယ်ပိုင်သုံးသပ်ချက်",
        "• ဒီ Episode အတွင်း အဆုံးသတ်သည့်အရာနှင့် ဆက်လက်ဖွင့်ထားသည့်အရာ။",
        "• ကိုယ်ပိုင်အမြင်၊ ဇာတ်ကောင်ဆုံးဖြတ်ချက်အပေါ် သုံးသပ်ချက်၊ ပရိသတ်ကို မေးခွန်း။",
        "",
        "၆။ ထုတ်လုပ်မှုစစ်ဆေးရန်",
        "• TVmaze summary ကို တိုက်ရိုက်ကူးမရေးဘဲ ကိုယ်ပိုင်စကားဖြင့် ပြန်ရေးပါ။",
        "• အချက်အလက်၊ အမည်၊ ဖြစ်ရပ်အစဉ်ကို မူရင်း Episode နှင့် ပြန်စစ်ပါ။",
        "• Footage/music ကို ကိုယ်ပိုင်ပိုင်ဆိုင်မှု သို့မဟုတ် ပြန်သုံးခွင့်ရှိသော လိုင်စင်ဖြင့်သာ သုံးပါ။",
        "• CC BY/CC BY-SA ဖြစ်ပါက Attribution နှင့် Share-Alike စည်းကမ်းကို လိုက်နာပါ။",
        "• TVmaze Animation genre တစ်ခုတည်းဖြင့် 3D Animation ဟု မသတ်မှတ်ပါနှင့်။",
        "",
        "နောက်တစ်ဆင့်: ကိုယ်တိုင်ဖြည့်ထားသော Script ကို /recapqa <category>|<title> ဖြင့် ဖွဲ့စည်းပုံစစ်ဆေးနိုင်သည်။",
        "သတိပြုရန်: ဤသည် Script worksheet သာဖြစ်ပြီး အလိုအလျောက် ဇာတ်လမ်းရေးသားခြင်း၊ TTS သို့မဟုတ် MP4 ထုတ်လုပ်ခြင်း မဟုတ်ပါ။",
        "TVmaze rating သည် community rating ဖြစ်ပြီး views/popularity မဟုတ်ပါ။ လူကိုယ်တိုင် အချက်အလက်နှင့် မီဒီယာအသုံးပြုခွင့်ကို စစ်ဆေးပါ။",
    ]
    return "\n".join(lines)
