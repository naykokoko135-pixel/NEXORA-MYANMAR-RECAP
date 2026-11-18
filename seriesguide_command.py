"""Telegram series-guide command logic kept independent of the web app runtime."""
import asyncio

from tvmaze_series import fetch_series_episode_guide, format_series_episode_guide
from wikidata_metadata import fetch_wikidata_metadata, format_wikidata_episode_guide


async def series_guide_cmd(update, context):
    """Look up a series guide using TVmaze first and Wikidata total counts as fallback."""
    if not update.message:
        return
    title = " ".join(context.args).strip()
    if not title:
        await update.message.reply_text("အသုံးပြုပုံ: /seriesguide Frieren: Beyond Journey's End")
        return

    await update.message.reply_text("Season / Episode အချက်အလက်ကို အခမဲ့ရင်းမြစ်များမှ စစ်ဆေးနေပါတယ်...")
    tvmaze_result = await asyncio.to_thread(fetch_series_episode_guide, title)
    if tvmaze_result.get("found"):
        report = format_series_episode_guide(tvmaze_result)
    else:
        wikidata_result = await asyncio.to_thread(fetch_wikidata_metadata, title)
        report = (
            "TVmaze စစ်ဆေးမှု: " + tvmaze_result.get("status", "မှတ်တမ်းမရရှိပါ။")
            + "\n\n" + format_wikidata_episode_guide(wikidata_result)
        )

    for start_at in range(0, len(report), 3900):
        await update.message.reply_text(report[start_at:start_at + 3900])
