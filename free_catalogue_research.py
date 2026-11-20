"""Free cross-category discovery through Wikimedia public REST search."""
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/page"
USER_AGENT = "NEXORA-Myanmar-Recap/2.0 (free public catalogue discovery)"


def _tokens(value):
    stop = {"the", "and", "for", "with", "from", "into", "of", "a", "an", "movie", "series"}
    return {w for w in re.findall(r"[a-z0-9]+", str(value or "").casefold()) if len(w) > 2 and w not in stop}


def search_free_catalogue(title, limit=5):
    """Return exact or meaningfully related public search leads, never plot facts."""
    requested = " ".join(str(title or "").split()).strip()
    if not requested or len(requested) > 120:
        return {"found": False, "items": [], "status": "ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    request = Request(SEARCH_URL + "?" + urlencode({"q": requested, "limit": max(1, min(int(limit), 5))}),
                      headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        target = _tokens(requested)
        items = []
        for page in payload.get("pages", []) if isinstance(payload, dict) else []:
            name = str(page.get("title") or "").strip()
            tokens = _tokens(name)
            exact = " ".join(re.findall(r"[a-z0-9]+", name.casefold())) == " ".join(re.findall(r"[a-z0-9]+", requested.casefold()))
            if exact or (target and len(target.intersection(tokens)) >= min(2, len(target))):
                key = str(page.get("key") or name.replace(" ", "_"))
                items.append({"title": name, "excerpt": re.sub(r"\s+", " ", str(page.get("excerpt") or ""))[:700],
                              "url": "https://en.wikipedia.org/wiki/" + key, "exact_title": exact})
        return {"found": bool(items), "provider": "Wikimedia public REST search", "items": items[:5],
                "status": "" if items else "Wikimedia တွင် ခေါင်းစဉ်နှင့် သက်ဆိုင်သော ရလဒ် မတွေ့ပါ။",
                "notice": "Discovery lead only; verify against official sources and the work itself."}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError):
        return {"found": False, "items": [], "status": "Wikimedia public catalogue ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။"}
