"""Collect episode-level plot research from free public animation catalogues.

Provider records remain separate: episode numbers and descriptions are not
merged or treated as cross-source corroboration. Missing plot text is never
generated. Kitsu and Bangumi are queried only after an independent non-Indian
country signal is found in AniList or Wikidata.
"""
from concurrent.futures import ThreadPoolExecutor


def _safe(fetcher, title, limit):
    try:
        result = fetcher(title, limit)
        if isinstance(result, dict):
            return result
        return {"found": False, "status": "ရင်းမြစ်မှ မမှန်ကန်သော တုံ့ပြန်မှု ရရှိပါသည်။"}
    except Exception:
        return {"found": False, "status": "ရင်းမြစ်ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}


def collect_episode_plots(title, limit_per_source=10):
    """Collect exact-title episode plot excerpts while preserving provider boundaries."""
    requested = " ".join(str(title or "").split()).strip()
    if not requested or len(requested) > 120:
        return {"found": False, "title": requested, "status": "Series ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    try:
        count = max(1, min(int(limit_per_source), 20))
    except (TypeError, ValueError):
        count = 10

    from tvmaze_synopsis import fetch_tvmaze_episode_summaries
    from kitsu_anime_research import fetch_kitsu_episode_summaries
    from bangumi_episode_research import fetch_bangumi_episode_summaries
    from multi_source_research import research_anime_sources

    # Independent country checks are required before using the anime-only fallback catalogues.
    with ThreadPoolExecutor(max_workers=2) as pool:
        tvmaze_future = pool.submit(_safe, fetch_tvmaze_episode_summaries, requested, count)
        verification_future = pool.submit(research_anime_sources, requested)
        tvmaze = tvmaze_future.result()
        try:
            verification = verification_future.result()
        except Exception:
            verification = {}

    anime = verification.get("anilist") or {}
    wikidata = verification.get("wikidata") or {}
    countries = wikidata.get("countries") or []
    country_code = str(anime.get("country") or "").upper() if anime.get("found") else ""
    country_text = " ".join(str(value) for value in countries).casefold()
    india = bool(verification.get("india_excluded")) or country_code == "IN" or "india" in country_text or "အိန္ဒိယ" in country_text
    country_verified = bool(countries or country_code) and not india
    country_label = ", ".join(str(value) for value in countries) if countries else country_code

    sources = {"TVmaze": tvmaze}
    skipped = {}
    if india:
        skipped["Kitsu"] = "အိန္ဒိယမူရင်းဖြစ်ကြောင်း တွေ့ရှိသဖြင့် ပယ်ချထားသည်။"
        skipped["Bangumi"] = skipped["Kitsu"]
    elif country_verified:
        with ThreadPoolExecutor(max_workers=2) as pool:
            kitsu_future = pool.submit(_safe, fetch_kitsu_episode_summaries, requested, count)
            bangumi_future = pool.submit(_safe, fetch_bangumi_episode_summaries, requested, count)
            sources["Kitsu"] = kitsu_future.result()
            sources["Bangumi"] = bangumi_future.result()
        for name in ("Kitsu", "Bangumi"):
            if sources[name].get("found"):
                sources[name]["country"] = country_label
    else:
        skipped["Kitsu"] = "AniList/Wikidata မှ သီးခြားမူရင်းနိုင်ငံ အတည်ပြုချက် မရသေးပါ။"
        skipped["Bangumi"] = skipped["Kitsu"]

    found = any(
        isinstance(result, dict) and result.get("found") and result.get("episodes")
        for result in sources.values()
    )
    return {
        "found": found,
        "title": requested,
        "country_verified": country_verified,
        "country": country_label,
        "india_excluded": india,
        "sources": sources,
        "skipped": skipped,
        "limit_per_source": count,
        "scope": "separate_provider_episode_plot_research",
    }


def format_episode_plot_collection(report):
    """Format a source-separated episode plot collection without fabricating gaps."""
    if not isinstance(report, dict) or not report.get("title"):
        return "Episode Plot Collection အတွက် ခေါင်းစဉ် မရရှိပါ။"
    lines = [
        "📚 NEXORA — EPISODE PLOT COLLECTION",
        "Series: " + str(report.get("title")),
        "ရင်းမြစ်တစ်ခုချင်းစီ၏ Episode အချက်အလက်ကို သီးခြားဖော်ပြထားသည်။",
        "အပိုင်းနံပါတ်/ဇာတ်ကွက် မတူနိုင်သဖြင့် ရင်းမြစ်များကို အလိုအလျောက် မပေါင်းစပ်ထားပါ။",
        "",
    ]
    if report.get("india_excluded"):
        lines.append("စစ်ဆေးချက်: အိန္ဒိယမူရင်းဖြစ်ကြောင်း တွေ့ရှိသဖြင့် Anime-only catalogue fallback များကို ပယ်ချထားသည်။")
    elif report.get("country_verified"):
        lines.append("သီးခြားနိုင်ငံစစ်ဆေးချက်: " + str(report.get("country") or "ရရှိသည်"))
    else:
        lines.append("သီးခြားနိုင်ငံစစ်ဆေးချက်: မရရှိသေးပါ။ Kitsu/Bangumi ကို မခေါ်ထားပါ။")
    lines.append("")

    for provider in ("TVmaze", "Kitsu", "Bangumi"):
        result = (report.get("sources") or {}).get(provider)
        lines.append("【" + provider + "】")
        if not isinstance(result, dict) or not result.get("found"):
            status = (result or {}).get("status") or (report.get("skipped") or {}).get(provider) or "Episode plot မရရှိပါ။"
            lines.append(str(status))
            lines.append("")
            continue
        lines.append("Series: " + str(result.get("title") or report.get("title")))
        lines.append("အပိုင်းရရှိမှု: " + str(len(result.get("episodes") or [])))
        if result.get("provider_url"):
            lines.append("Catalogue: " + str(result["provider_url"]))
        for episode in result.get("episodes") or []:
            season = episode.get("season")
            number = episode.get("number")
            episode_id = ("S" + str(season) + " " if season is not None else "")
            episode_id += "E" + str(number) if number is not None else "Episode နံပါတ်မရှိ"
            lines.append(
                episode_id + " — " + str(episode.get("title") or "ခေါင်းစဉ်မရှိ")
                + " (" + str(episode.get("airdate") or "ရက်စွဲမရှိ") + ")"
            )
            summary = str(episode.get("summary_excerpt") or "").strip()
            if summary:
                lines.append("Plot lead: " + summary[:240])
            else:
                lines.append("Plot: ဒီရင်းမြစ်တွင် Episode ဇာတ်ကွက်စာသား မဖော်ပြထားပါ။")
            if episode.get("source"):
                lines.append("Source: " + str(episode["source"]))
        lines.append("")

    lines.extend([
        "အသုံးပြုရန် သတိပြုချက်:",
        "• ဤစာများသည် public catalogue များမှ Episode-level research leads သာဖြစ်သည်။ Studio အတည်ပြုဇာတ်ညွှန်း သို့မဟုတ် scene transcript မဟုတ်ပါ။",
        "• မတူညီသော provider များ၏ Episode နံပါတ်နှင့် အမည်များကို လူကိုယ်တိုင် တိုက်စစ်ပါ။",
        "• Plot မရရှိသောအပိုင်းကို မခန့်မှန်း၊ မဖြည့်စွက်ထားပါ။",
        "• Footage/music အသုံးပြုခွင့်ကို ဤ research က မပေးပါ။ License နှင့် attribution ကို သီးခြားစစ်ဆေးပါ။",
    ])
    return "\n".join(lines)
