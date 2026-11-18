"""Retrieve a plot section from the exact Burmese Wikipedia sitelink.

Only a section explicitly labelled as a plot/summary is accepted. This is
community-edited source material, not studio-verified canon.
"""
import re
from html.parser import HTMLParser
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

API_URL = "https://my.wikipedia.org/w/api.php"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0 (public-source plot research)"
PLOT_HEADINGS = {
    "ဇာတ်လမ်း", "ဇာတ်လမ်းအကျဉ်း", "ဇာတ်ကြောင်း", "အကြောင်းအရာ",
    "ဇာတ်လမ်းအကြောင်း", "ဇာတ်လမ်းအကျဉ်းချုပ်",
}


class PlotResearchError(Exception):
    """Raised when no exact, usable Burmese plot source is available."""


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "table", "sup"}:
            self.skip_depth += 1
        elif not self.skip_depth and tag in {"p", "br", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "table", "sup"} and self.skip_depth:
            self.skip_depth -= 1
        elif not self.skip_depth and tag in {"p", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)


def _api(params):
    request = Request(
        API_URL + "?" + urlencode(params),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _clean_html(value):
    parser = _TextExtractor()
    parser.feed(value or "")
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def fetch_burmese_plot_section(page_title):
    """Return a Burmese plot section and source URL, or fail closed."""
    title = " ".join(str(page_title or "").split()).strip()
    if not title or len(title) > 180:
        raise PlotResearchError("မြန်မာ Wikipedia ခေါင်းစဉ် မရရှိပါ။")

    try:
        sections_payload = _api({
            "action": "parse",
            "page": title,
            "prop": "sections",
            "format": "json",
        })
        parsed = sections_payload.get("parse", {})
        canonical_title = parsed.get("title", "")
        sections = parsed.get("sections", [])
        candidates = [
            section for section in sections
            if re.sub(r"\s+", "", str(section.get("line", ""))).casefold()
            in {re.sub(r"\s+", "", item).casefold() for item in PLOT_HEADINGS}
        ]
        if not candidates:
            raise PlotResearchError("မြန်မာ Wikipedia မှာ ဇာတ်လမ်းအကျဉ်း section မတွေ့ပါ။")
        # Prefer the first explicit plot section, not cast/production/trivia.
        section = candidates[0]
        content_payload = _api({
            "action": "parse",
            "page": canonical_title or title,
            "section": str(section.get("index", "")),
            "prop": "text",
            "format": "json",
        })
        html = content_payload.get("parse", {}).get("text", {}).get("*", "")
        summary = _clean_html(html)
        if len(summary) < 180:
            raise PlotResearchError("တွေ့ရှိသော ဇာတ်လမ်းအကျဉ်းသည် အသံဖန်တီးရန် မလုံလောက်ပါ။")
        summary = summary[:6000]
        page_url = "https://my.wikipedia.org/wiki/" + (canonical_title or title).replace(" ", "_")
        return {
            "found": True,
            "title": canonical_title or title,
            "plot_text": summary,
            "section": section.get("line", ""),
            "source": page_url,
            "source_notice": "မြန်မာ Wikipedia လူထုတည်းဖြတ်အကြောင်းအရာ",
        }
    except PlotResearchError:
        raise
    except Exception as exc:
        raise PlotResearchError("မြန်မာ Wikipedia ဇာတ်လမ်းရင်းမြစ်ကို ဖတ်မရပါ။") from exc
