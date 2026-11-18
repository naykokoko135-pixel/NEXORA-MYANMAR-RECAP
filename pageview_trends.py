"""Free Wikimedia article-pageview attention signals across NEXORA categories.

These are public English Wikipedia article views, not video plays or episode view counts.
"""
import json
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
USER_AGENT = "NEXORA-Myanmar-Recap/1.0 (https://github.com/naykokoko135-pixel/NEXORA-MYANMAR-RECAP)"
SAMPLE_PER_CATEGORY = 2
LOOKBACK_DAYS = 14
DATA_LAG_DAYS = 2


def _fetch_json(url):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _sample_titles(titles, day, count=SAMPLE_PER_CATEGORY):
    titles = list(titles or [])
    if not titles:
        return []
    start = day.toordinal() % len(titles)
    return [titles[(start + offset) % len(titles)] for offset in range(min(count, len(titles)))]


def fetch_category_pageviews(title_categories, as_of=None, samples_per_category=SAMPLE_PER_CATEGORY):
    """Compare recent 7-day pageviews with the previous 7 days for rotating title samples."""
    today = as_of or datetime.now(timezone.utc).date()
    end = today - timedelta(days=DATA_LAG_DAYS)
    start = end - timedelta(days=LOOKBACK_DAYS - 1)
    recent_start = end - timedelta(days=6)
    previous_end = recent_start - timedelta(days=1)
    result = {
        "ok": False,
        "source": "Wikimedia Pageviews API (English Wikipedia)",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "period_start": start.strftime("%Y%m%d"),
        "period_end": end.strftime("%Y%m%d"),
        "samples_per_category": max(0, int(samples_per_category)),
        "categories": {},
        "errors": 0,
    }

    for category, titles in (title_categories or {}).items():
        category_items = []
        sampled_titles = _sample_titles(titles, today, samples_per_category)
        for title in sampled_titles:
            article = quote(str(title).replace(" ", "_"), safe="")
            url = (
                f"{BASE_URL}/en.wikipedia/all-access/user/{article}/daily/"
                f"{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
            )
            try:
                payload = _fetch_json(url)
                points = payload.get("items", [])
                recent = sum(
                    int(point.get("views", 0))
                    for point in points
                    if str(point.get("timestamp", ""))[:8] >= recent_start.strftime("%Y%m%d")
                )
                previous = sum(
                    int(point.get("views", 0))
                    for point in points
                    if str(point.get("timestamp", ""))[:8] <= previous_end.strftime("%Y%m%d")
                )
                change = round((recent - previous) * 100 / previous, 1) if previous > 0 else None
                category_items.append({
                    "title": title,
                    "url": f"https://en.wikipedia.org/wiki/{article}",
                    "recent_views": recent,
                    "previous_views": previous,
                    "change_pct": change,
                    "verification_status": "လူကိုယ်တိုင် မူရင်းနှင့် ထပ်မံစစ်ဆေးရန်",
                })
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
                result["errors"] += 1

        # This order is only a comparison among today's sampled titles, not a category ranking.
        category_items.sort(key=lambda item: item["recent_views"], reverse=True)
        result["categories"][category] = category_items

    result["ok"] = any(result["categories"].values())
    return result


def format_category_pageviews(result):
    samples = result.get("samples_per_category", SAMPLE_PER_CATEGORY)
    lines = [
        "📊 NEXORA — English Wikipedia ဆောင်းပါး Pageviews အချက်ပြ",
        f"ရင်းမြစ်: {result.get('source', 'Wikimedia Pageviews API (English Wikipedia)')}",
        f"ကာလ: {result.get('period_start', '?')} မှ {result.get('period_end', '?')} (ရက် ၁၄)",
        f"စစ်ဆေးမှု: အမျိုးအစားတစ်ခုလျှင် နမူနာ {samples} ခုကို နေ့စဉ်လှည့်လည်ရွေးချယ်ခြင်း",
        "အောက်ပါအစီအစဉ်သည် ယနေ့နမူနာအတွင်း Pageviews အလိုက်သာ စီထားခြင်းဖြစ်ပြီး အမျိုးအစားတစ်ခုလုံး၏ Ranking မဟုတ်ပါ။",
    ]
    categories = result.get("categories", {})
    if not result.get("ok"):
        lines.extend(["Pageview အချက်အလက် မရရှိပါ။", "အဆင့်သတ်မှတ်ချက်ကို မခန့်မှန်းထားပါ။"])

    for category, items in categories.items():
        lines.append(f"\n{category} — နမူနာ {samples} ခုအနက် ဒေတာရရှိမှု {len(items)} ခု:")
        if not items:
            lines.append("ဒေတာမရရှိပါ။ လူကြိုက်များမှုအဖြစ် မခန့်မှန်းထားပါ။")
            continue
        for index, item in enumerate(items, start=1):
            change = (
                f"{item['change_pct']:+.1f}%"
                if item.get("change_pct") is not None else "ပြောင်းလဲမှု မတွက်နိုင်"
            )
            lines.append(
                f"{index}. {item['title']} — နောက်ဆုံး ၇ ရက် {item['recent_views']:,} "
                f"English Wikipedia article views | ယခင် ၇ ရက်နှင့် {change}"
            )
            lines.append(f"Wikipedia source: {item['url']}")
            lines.append(f"အတည်ပြုမှု: {item.get('verification_status', 'လူကိုယ်တိုင် မူရင်းနှင့် ထပ်မံစစ်ဆေးရန်')}")

    lines.extend([
        "\nအရေးကြီး: ဤကိန်းဂဏန်းများသည် English Wikipedia ဆောင်းပါး pageviews သာဖြစ်ပြီး YouTube/Facebook/TikTok ကြည့်ရှုမှု၊"
        " episode view count သို့မဟုတ် လူကြိုက်များမှုအပြည့်အစုံ မဟုတ်ပါ။",
        "ခေါင်းစဉ်နမူနာ ၂ ခုစီကို နေ့စဉ်လှည့်လည်စစ်ဆေးထားခြင်းဖြစ်၍ အမျိုးအစားတစ်ခုလုံး၏ အပြီးသတ် ranking မဟုတ်ပါ။",
        "မူရင်းစာမျက်နှာမကိုက်ညီနိုင်သော ခေါင်းစဉ်များကို source link ဖြင့် လူက ထပ်မံစစ်ဆေးပါ။",
        "YouTube/Facebook/TikTok platform metrics: ဤအစီရင်ခံစာတွင် မရရှိသေးပါ — Wikipedia data ဖြင့် အစားမထိုးပါ။",
    ])
    if result.get("errors"):
        lines.append(f"API မှ ဒေတာမရယူနိုင်သော ခေါင်းစဉ်: {result['errors']} ခု")
    return "\n".join(lines)
