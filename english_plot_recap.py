"""Create a Burmese recap draft from an exact English Wikipedia plot source.

The source is community-edited and must not be presented as studio-verified canon.
"""
from urllib.parse import urlparse

from openai_script_provider import generate_burmese_recap_script

MAX_SOURCE_NOTES_CHARS = 3300
MIN_SOURCE_NOTES_CHARS = 80


def generate_burmese_recap_from_english_plot(
    topic: str, plot: dict, platform: str = "youtube"
) -> tuple[str, str]:
    """Translate/adapt a title-linked English plot section into Burmese narration."""
    if not isinstance(plot, dict) or not plot.get("found"):
        raise ValueError("English Wikipedia မှ အတည်ပြုထားသော Plot section မရှိပါ။")
    source_url = str(plot.get("source") or "").strip()
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.hostname != "en.wikipedia.org" or not parsed.path.startswith("/wiki/"):
        raise ValueError("English Plot ရင်းမြစ်လိပ်စာကို အတည်မပြုနိုင်ပါ။")
    source_text = " ".join(str(plot.get("plot_text") or "").split()).strip()
    if len(source_text) < MIN_SOURCE_NOTES_CHARS:
        raise ValueError("English Plot ရင်းမြစ်စာသား မလုံလောက်ပါ။")
    notes = (
        "English Wikipedia ၏ title-linked Plot section ဖြစ်သည်။ လူထုတည်းဖြတ်ရင်းမြစ်ဖြစ်၍ "
        "studio-verified canon ဟု မဆိုရ။ မသေချာသောအချက်များကို [အချက်အလက် ထပ်စစ်ရန်] ဟု မှတ်သားပါ။\n"
        + source_text[:MAX_SOURCE_NOTES_CHARS]
        + "\nSource: " + source_url
    )
    script = generate_burmese_recap_script(
        topic, notes, platform=platform, duration="3-5"
    )
    if not script.strip():
        raise ValueError("Burmese recap narration မရရှိပါ။")
    return script.strip(), source_url
