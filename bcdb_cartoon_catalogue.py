"""BCDB popular-cartoon catalogue reader.

BCDB explicitly disallows automated access to /search. This module reads only
its robots-allowed /most-popular page, caches it for an hour, and enforces its
five-second crawl delay. It never fetches poster or artwork URLs.
"""
import re
import threading
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse

BASE_URL = "https://www.bcdb.com"
POPULAR_URL = BASE_URL + "/most-popular"
USER_AGENT = "NEXORA-Myanmar-Recap/2.0 (respectful BCDB catalogue reader)"
CACHE_SECONDS = 3600
CRAWL_DELAY_SECONDS = 5.0

_CACHE = []
_CACHE_AT = 0.0
_LAST_FETCH_AT = 0.0
_LOCK = threading.Lock()


def _norm(value):
    value = re.sub(r"\s*\(\d{4}\)\s*$", "", str(value or "").casefold())
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


class _PopularPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.section = "all_time"
        self.in_heading = False
        self.heading = []
        self.current = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h2":
            self.in_heading = True
            self.heading = []
        elif tag == "a":
            href = urljoin(BASE_URL, str(attrs.get("href") or ""))
            path = urlparse(href).path
            match = re.match(r"^/cartoon/(\d+)(?:-[^/?#]+)?/?$", path)
            if match:
                self.current = {
                    "id": match.group(1),
                    "url": BASE_URL + href,
                    "parts": [],
                    "period": self.section,
                }

    def handle_data(self, data):
        if self.in_heading:
            self.heading.append(data)
        if self.current is not None:
            self.current["parts"].append(data)

    def handle_endtag(self, tag):
        if tag == "h2" and self.in_heading:
            heading = " ".join(" ".join(self.heading).split()).casefold()
            if "this month" in heading:
                self.section = "this_month"
            elif "all time" in heading:
                self.section = "all_time"
            self.in_heading = False
            self.heading = []
        elif tag == "a" and self.current is not None:
            title = " ".join(" ".join(self.current.pop("parts")).split())
            if title:
                self.current["title"] = title
                self.items.append(self.current)
            self.current = None


def _fetch_popular_catalogue():
    global _CACHE, _CACHE_AT, _LAST_FETCH_AT
    now = time.monotonic()
    if _CACHE and now - _CACHE_AT < CACHE_SECONDS:
        return list(_CACHE)
    with _LOCK:
        now = time.monotonic()
        if _CACHE and now - _CACHE_AT < CACHE_SECONDS:
            return list(_CACHE)
        wait = CRAWL_DELAY_SECONDS - (now - _LAST_FETCH_AT)
        if _LAST_FETCH_AT and wait > 0:
            time.sleep(wait)
        request = Request(
            POPULAR_URL,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        )
        try:
            with urlopen(request, timeout=20) as response:
                html = response.read().decode("utf-8", errors="replace")
            parser = _PopularPageParser()
            parser.feed(html)
            _CACHE = parser.items
            _CACHE_AT = time.monotonic()
            _LAST_FETCH_AT = _CACHE_AT
            return list(_CACHE)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            _LAST_FETCH_AT = time.monotonic()
            return []


def fetch_bcdb_popular_cartoon(title):
    """Find an exact title in BCDB's permitted most-viewed lists."""
    requested = " ".join(str(title or "").split()).strip()
    if not requested or len(requested) > 120:
        return {"found": False, "status": "BCDB ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    try:
        target = _norm(requested)
        matches = [
            item for item in _fetch_popular_catalogue()
            if _norm(item.get("title")) == target
        ]
        unique = {str(item.get("id")): item for item in matches}
        if len(unique) != 1:
            return {
                "found": False,
                "status": (
                    "BCDB ရဲ့ ခွင့်ပြုထားသော Popular စာရင်းတွင် အမည်တိတိကျကျ "
                    "ကိုက်ညီသော မှတ်တမ်းတစ်ခုတည်း မတွေ့ပါ။"
                ),
            }
        item = next(iter(unique.values()))
        return {
            "found": True,
            "provider": "The Big Cartoon DataBase (BCDB)",
            "media_id": item["id"],
            "title": item["title"],
            "provider_url": item["url"],
            "period": item.get("period") or "popular",
            "catalogue_url": POPULAR_URL,
            "license": "CC BY 4.0 for BCDB facts and compilation; artwork excluded",
            "notice": (
                "BCDB Popular စာရင်းသည် BCDB ကို ဝင်ကြည့်သူများ၏ page views အပေါ် "
                "အခြေခံသည်။ YouTube/Facebook/TikTok trend သို့မဟုတ် footage license မဟုတ်ပါ။"
            ),
        }
    except Exception:
        return {"found": False, "status": "BCDB ရင်းမြစ်ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}
