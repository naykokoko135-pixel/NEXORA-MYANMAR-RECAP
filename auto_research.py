"""Free public-source discovery using the MediaWiki API.

Returns short article excerpts and links as research leads. It does not verify
facts or generate a plot summary. No API key or third-party package is needed.
"""
import json
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0 (public research lookup)"
MAX_RESULTS = 3
MAX_EXCERPT_CHARS = 650


class ResearchLookupError(Exception):
    """Raised when the public source lookup cannot be completed."""


def search_movie_sources(topic: str) -> str:
    title = " ".join((topic or "").split()).strip()
    if not title:
        raise ResearchLookupError("ဇာတ်ကားအမည် ထည့်ပေးပါ။")
    if len(title) > 120:
        raise ResearchLookupError("ရှာဖွေမည့်အမည်သည် စာလုံး ၁၂၀ ထက် မရှည်ရပါ။")

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": title + " film movie",
        "gsrnamespace": 0,
        "gsrlimit": MAX_RESULTS,
        "prop": "extracts|info",
        "exintro": 1,
        "explaintext": 1,
        "inprop": "url",
        "format": "json",
        "formatversion": 2,
    }
    request = Request(
        API_URL + "?" + urlencode(params),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise ResearchLookupError(
            "အများပြည်သူသုံး ရင်းမြစ်ကို လောလောဆယ် မရယူနိုင်ပါ။ ခဏနေမှ ပြန်စမ်းပါ။"
        ) from exc

    pages = payload.get("query", {}).get("pages", [])
    if not pages:
        return (
            f"🔎 NEXORA Auto Research — {title}\n\n"
            "ကိုက်ညီသော Wikipedia ဆောင်းပါး မတွေ့ပါ။ အမည်စာလုံးပေါင်းကို စစ်ပါ။"
        )

    lines = [
        f"🔎 NEXORA Auto Research — {title}",
        "",
        "အောက်ပါအချက်များသည် Wikipedia ရှာဖွေမှုမှ ရရှိသော တိုတောင်းသည့် အစိတ်အပိုင်းများသာ ဖြစ်သည်။",
        "အတည်ပြုထားသော ဇာတ်လမ်းအကျဉ်း မဟုတ်ပါ။",
        "",
    ]
    for index, page in enumerate(pages[:MAX_RESULTS], start=1):
        page_title = str(page.get("title", "Untitled"))
        extract = " ".join(str(page.get("extract", "")).split())
        if len(extract) > MAX_EXCERPT_CHARS:
            extract = extract[:MAX_EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"
        url = page.get("fullurl") or (
            "https://en.wikipedia.org/wiki/" + page_title.replace(" ", "_")
        )
        lines.extend([
            f"{index}. {page_title}",
            extract or "အကျဉ်းချုပ် မရရှိပါ။",
            f"Source: {url}",
            "",
        ])

    lines.extend([
        "နောက်တစ်ဆင့် — Source link များကို ဖွင့်ပြီး ရုပ်ရှင်နှင့် ကိုက်ညီမှုကို စစ်ပါ။",
        "Wikipedia သည် လူထုတည်းဖြတ်သည့် ရင်းမြစ်ဖြစ်သောကြောင့် official source သို့မဟုတ် "
        "ရုပ်ရှင်ကိုယ်တိုင်နှင့် ထပ်မံတိုက်စစ်ပါ။",
        "ဤ command သည် ChatGPT ကို မချိတ်ဆက်ပါ၊ ဇာတ်ညွှန်းအပြည့်လည်း မရေးပေးပါ။",
    ])
    return "\n".join(lines)
