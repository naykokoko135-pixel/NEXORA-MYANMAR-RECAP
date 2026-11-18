"""Free public-source discovery using Wikimedia's free search APIs.

Returns short article excerpts and links as research leads. It does not verify
facts or generate a plot summary. No API key or third-party package is needed.
"""
import json
import re
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

API_URL = "https://en.wikipedia.org/w/api.php"
REST_SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/page"
USER_AGENT = "NEXORA-Myanmar-Recap/1.1 (free public research lookup)"
MAX_RESULTS = 3
SEARCH_LIMIT = 8
MAX_EXCERPT_CHARS = 650


class ResearchLookupError(Exception):
    """Raised when the public source lookup cannot be completed."""


def _request_json(url: str) -> dict:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _search_mediawiki(title: str) -> list:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f'"{title}"',
        "gsrnamespace": 0,
        "gsrlimit": SEARCH_LIMIT,
        "prop": "extracts|info",
        "exintro": 1,
        "explaintext": 1,
        "inprop": "url",
        "format": "json",
        "formatversion": 2,
    }
    payload = _request_json(API_URL + "?" + urlencode(params))
    return payload.get("query", {}).get("pages", [])


def _search_rest(title: str) -> list:
    """Fallback to Wikimedia's REST search when the Action API is unavailable."""
    params = urlencode({"q": title, "limit": SEARCH_LIMIT})
    payload = _request_json(REST_SEARCH_URL + "?" + params)
    pages = []
    for item in payload.get("pages", []):
        page_key = str(item.get("key", ""))
        page_title = str(item.get("title", "Untitled"))
        excerpt = re.sub(r"<[^>]+>", "", str(item.get("excerpt", "")))
        pages.append({
            "title": page_title,
            "extract": excerpt,
            "fullurl": "https://en.wikipedia.org/wiki/" + quote(page_key or page_title.replace(" ", "_"), safe="()_"),
        })
    return pages


def _title_tokens(value: str) -> set:
    """Return meaningful title words for a conservative relevance check."""
    stop_words = {"the", "and", "for", "with", "from", "into", "of", "a", "an"}
    words = re.findall(r"[a-z0-9]+", (value or "").casefold())
    return {word for word in words if len(word) >= 3 and word not in stop_words}


def search_movie_sources(topic: str) -> str:
    title = " ".join((topic or "").split()).strip()
    if not title:
        raise ResearchLookupError("ဇာတ်ကားအမည် ထည့်ပေးပါ။")
    if len(title) > 120:
        raise ResearchLookupError("ရှာဖွေမည့်အမည်သည် စာလုံး ၁၂၀ ထက် မရှည်ရပါ။")

    errors = []
    pages = []
    for search_function in (_search_mediawiki, _search_rest):
        try:
            pages = search_function(title)
            if pages:
                break
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
            errors.append(type(exc).__name__)

    if not pages and len(errors) == 2:
        raise ResearchLookupError(
            "Wikipedia ရှာဖွေရေးလမ်းကြောင်း ၂ ခုလုံးကို မချိတ်ဆက်နိုင်ပါ။ "
            "Render Logs ကို စစ်ဆေးရန် လိုအပ်ပါသည်။"
        )

    if not pages:
        return (
            f"🔎 NEXORA Auto Research — {title}\n\n"
            "ကိုက်ညီသော Wikipedia ဆောင်းပါး မတွေ့ပါ။ အမည်စာလုံးပေါင်းကို စစ်ပါ။"
        )

    def normalized(value: str) -> str:
        value = value.casefold().strip()
        if " (" in value:
            value = value.split(" (", 1)[0]
        return " ".join(value.split())

    target_tokens = _title_tokens(title)
    # Never present merely popular anime/voice-actor search hits as related
    # sources for a different title. A shared meaningful title word is the
    # minimum bar; exact title matches are always retained.
    relevant_pages = []
    for page in pages:
        page_title = str(page.get("title", ""))
        is_exact = normalized(page_title) == normalized(title)
        page_tokens = _title_tokens(page_title)
        if is_exact or (target_tokens and target_tokens.intersection(page_tokens)):
            relevant_pages.append(page)
    pages = sorted(
        relevant_pages,
        key=lambda page: (
            normalized(str(page.get("title", ""))) != normalized(title),
            str(page.get("title", "")).casefold(),
        ),
    )
    if not pages:
        return (
            f"🔎 NEXORA Auto Research — {title}\n\n"
            "ခေါင်းစဉ်နှင့် ကိုက်ညီမှုရှိသော Wikipedia ဆောင်းပါး မတွေ့ပါ။ "
            "မသက်ဆိုင်သော ရလဒ်များကို ဖယ်ထားသည်။ Official source ဖြင့် ထပ်မံရှာဖွေပါ။"
        )

    exact_pages = [
        page for page in pages
        if normalized(str(page.get("title", ""))) == normalized(title)
    ]
    related_pages = [page for page in pages if page not in exact_pages]
    selected_pages = exact_pages[:1] + related_pages[:MAX_RESULTS - min(1, len(exact_pages))]

    lines = [
        f"🔎 NEXORA Auto Research — {title}",
        "",
        "အောက်ပါအချက်များသည် Wikipedia ရှာဖွေမှုမှ ရရှိသော တိုတောင်းသည့် အစိတ်အပိုင်းများသာ ဖြစ်သည်။",
        "အတည်ပြုထားသော ဇာတ်လမ်းအကျဉ်း မဟုတ်ပါ။",
        "",
    ]
    for index, page in enumerate(selected_pages, start=1):
        page_title = str(page.get("title", "Untitled"))
        extract = " ".join(str(page.get("extract", "")).split())
        if len(extract) > MAX_EXCERPT_CHARS:
            extract = extract[:MAX_EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"
        url = page.get("fullurl") or (
            "https://en.wikipedia.org/wiki/" + page_title.replace(" ", "_")
        )
        match_label = "အမည်ကိုက်ညီသော ရလဒ်" if page in exact_pages else "ဆက်စပ်ရလဒ် — အမည်/ဇာတ်ကားကို ပြန်စစ်ပါ"
        lines.extend([
            f"{index}. {page_title} ({match_label})",
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
