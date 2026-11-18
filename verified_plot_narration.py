"""Prepare a short Burmese narration from a retrieved Burmese plot section.

The plot text is source-derived. This module does not invent scenes or events.
"""
import re


def generate_burmese_plot_narration(metadata: dict, plot: dict) -> str:
    if not isinstance(metadata, dict) or not metadata.get("found"):
        raise ValueError("ခေါင်းစဉ်အတည်ပြုထားသော Wikidata မှတ်တမ်း မရှိပါ။")
    if not isinstance(plot, dict) or not plot.get("found") or not plot.get("plot_text"):
        raise ValueError("မြန်မာ Wikipedia ဇာတ်လမ်းအကျဉ်း ရင်းမြစ် မရှိပါ။")

    countries = [str(x) for x in metadata.get("countries", [])]
    if any("india" in item.casefold() or "အိန္ဒိယ" in item for item in countries):
        raise ValueError("ဒီ Project မှာ အိန္ဒိယဇာတ်ကားများ မထည့်ထားပါ။")

    title = " ".join(str(metadata.get("title_my") or metadata.get("title") or plot.get("title") or "").split())
    source_text = re.sub(r"\s+", " ", str(plot["plot_text"])).strip()
    if len(source_text) < 180:
        raise ValueError("အတည်ပြုရင်းမြစ်မှ ဇာတ်လမ်းစာသား မလုံလောက်ပါ။")

    # Keep the first ~850 characters for a short, bounded preview.
    excerpt = source_text[:850]
    if len(source_text) > len(excerpt):
        boundary = max(excerpt.rfind("။"), excerpt.rfind("၊"))
        if boundary >= 500:
            excerpt = excerpt[:boundary + 1]
    return (
        f"ဒီနေ့ NEXORA မှာ {title} ရဲ့ ဇာတ်လမ်းအကျဉ်းကို မိတ်ဆက်ပေးပါမယ်။\n"
        f"{excerpt}\n"
        "အထက်ပါဇာတ်လမ်းအကျဉ်းကို မြန်မာ Wikipedia ရင်းမြစ်မှ ရယူထားခြင်းဖြစ်ပါတယ်။ "
        "Wikipedia သည် လူထုတည်းဖြတ်ရင်းမြစ်ဖြစ်သောကြောင့် မူရင်းထုတ်လုပ်သူ၏ အချက်အလက်နှင့် "
        "ထပ်မံတိုက်စစ်သင့်ပါတယ်။ ဒီ Preview ဟာ ရင်းမြစ်စာသားအပေါ် အခြေခံထားပြီး "
        "မဖော်ပြထားတဲ့ ဇာတ်ဝင်ခန်းတွေကို မခန့်မှန်းထားပါဘူး။"
    )
