"""Build a cautious production brief from TVMaze episode research and Commons metadata."""
def format_animated_episode_pack(research: dict, clip_source: dict | None = None) -> str:
    if not isinstance(research, dict) or not research.get("found"):
        raise ValueError("အတည်ပြုထားသော Animation episode research မရှိပါ။")
    title = str(research.get("title") or "").strip()
    country = str(research.get("country") or "").strip()
    episodes = research.get("episodes")
    if not title or not country or not isinstance(episodes, list) or not episodes:
        raise ValueError("Series title၊ မူရင်းနိုင်ငံနှင့် Episode research မပြည့်စုံပါ။")
    lines = [
        "🎬 NEXORA — ANIMATED EPISODE PRODUCTION PACK",
        f"Series: {title}",
        f"Country (TVmaze): {country}",
        "",
        "၁။ Episode ရွေးချယ်မှု (TVmaze community rating အလိုက်)",
    ]
    for index, episode in enumerate(episodes[:5], 1):
        rating = episode.get("rating")
        if not isinstance(rating, (int, float)) or isinstance(rating, bool) or not 0 < rating <= 10:
            continue
        season = episode.get("season") or "?"
        number = episode.get("number") or "?"
        lines.extend([
            f"{index}. S{season} E{number} — {episode.get('title') or 'Untitled'} | Rating {rating:.1f}/10",
            f"   Air date: {episode.get('airdate') or 'မဖော်ပြထား'}",
            f"   Research lead: {str(episode.get('summary_excerpt') or '')[:240]}",
            f"   TVmaze: {episode.get('source') or research.get('provider_url') or 'မရရှိပါ'}",
        ])
    if clip_source:
        lines.extend([
            "",
            "၂။ ဖြစ်နိုင်သော Reusable Footage Candidate",
            f"ဖိုင်: {clip_source.get('title') or 'မဖော်ပြထား'}",
            f"လိုင်စင်: {clip_source.get('license') or 'မဖော်ပြထား'}",
            f"ဖန်တီးသူ: {clip_source.get('artist') or 'မဖော်ပြထား'}",
            f"Commons စာမျက်နှာ: {clip_source.get('source_page') or 'မရရှိပါ'}",
            f"အသုံးပြုမှုစည်းကမ်း: {clip_source.get('usage_terms') or 'မဖော်ပြထား'}",
        ])
    else:
        lines.extend(["", "၂။ Footage", "Episode နဲ့ ခိုင်မာစွာကိုက်ညီသော ခွင့်ပြုထားသည့် Commons video မတွေ့ပါ။"])
    lines.extend([
        "",
        "၃။ ထုတ်လုပ်မှုမတိုင်မီ လုပ်ရန်",
        "• TVmaze summary ကို မူရင်း Episode နှင့် ထပ်မံတိုက်စစ်ပါ။",
        "• Episode အချက်အလက်ကို ကိုယ်ပိုင်စကားဖြင့် ပြန်ရေးပြီး ဇာတ်ဝင်ခန်းအစဉ်လိုက် စစ်ပါ။",
        "• Commons ဖိုင်ကို မကြည့်ဘဲ ဇာတ်ဝင်ခန်းမှန်သည်ဟု မယူဆပါနှင့်။",
        "• CC BY/CC BY-SA ဖြစ်ပါက သတ်မှတ်ထားသော Attribution နှင့် Share-Alike စည်းကမ်းများကို လိုက်နာပါ။",
        "• 3D Animation ဟု TVmaze Animation genre တစ်ခုတည်းဖြင့် မသတ်မှတ်ပါနှင့်။",
        "",
        "သတိပြုရန်: TVmaze rating သည် community rating ဖြစ်ပြီး views/popularity မဟုတ်ပါ။",
        "ဤ Pack သည် research/production brief သာဖြစ်ပြီး အလိုအလျောက် recap script သို့မဟုတ် MP4 မဟုတ်ပါ။",
        "Commons metadata title match သည် video ထဲရှိ အမှန်တကယ် scene ကို အတည်မပြုပါ။ လူကိုယ်တိုင် ကြည့်ရှုစစ်ဆေးရန် လိုအပ်သည်။",
    ])
    return "\n".join(lines)
