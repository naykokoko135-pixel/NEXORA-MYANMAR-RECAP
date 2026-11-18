"""Retrieve an explicitly labelled plot section from an exact English Wikipedia sitelink.

This is community-edited research material, not studio-verified canon. The
function deliberately rejects articles without a plot section.
"""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0 (public-source plot research)"
PLOT_HEADINGS = {
    "plot", "synopsis", "story", "plot summary", "premise and plot",
}


class EnglishPlotError(Exception):
    pass


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


def fetch_english_plot_section(page_title):
    title = " ".join(str(page_title or "").split()).strip()
    if not title or len(title) > 180:
        raise EnglishPlotError("English Wikipedia ခေါင်းစဉ် မရရှိပါ။")
    try:
        sections_payload = _api({
            "action": "parse", "page": title, "prop": "sections", "format": "json",
        })
        parsed = sections_payload.get("parse", {})
        canonical_title = parsed.get("title", "")
        sections = parsed.get("sections", [])
        candidates = [
            section for section in sections
            if re.sub(r"\s+", " ", str(section.get("line", "")).casefold()).strip()
            in PLOT_HEADINGS
        ]
        if not candidates:
            raise EnglishPlotError("English Wikipedia မှာ သီးခြား Plot/Synopsis section မတွေ့ပါ။")
        section = candidates[0]
        content_payload = _api({
            "action": "parse", "page": canonical_title or title,
            "section": str(section.get("index", "")), "prop": "text", "format": "json",
        })
        html = content_payload.get("parse", {}).get("text", {}).get("*", "")
        summary = _clean_html(html)
        if len(summary) < 250:
            raise EnglishPlotError("တွေ့ရှိသော Plot section သည် research အတွက် မလုံလောက်ပါ။")
        summary = summary[:8000]
        page_url = "https://en.wikipedia.org/wiki/" + (canonical_title or title).replace(" ", "_")
        return {
            "found": True, "title": canonical_title or title,
            "plot_text": summary, "section": section.get("line", ""),
            "source": page_url,
            "source_notice": "English Wikipedia community-edited plot section",
        }
    except EnglishPlotError:
        raise
    except Exception as exc:
        raise EnglishPlotError("English Wikipedia Plot ရင်းမြစ်ကို ဖတ်မရပါ။") from exc
