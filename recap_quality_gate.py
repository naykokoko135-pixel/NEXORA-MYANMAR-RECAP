"""Deterministic editorial preflight for creator-written recap scripts.

This module checks structure and disclosure signals only. It does not fact-check
plot claims, translate text, assess copyright legality, or predict performance.
"""
import re

ALLOWED_CATEGORIES = {
    "anime", "3d animation", "cartoon", "donghua", "international movies"
}
EXCLUDED_TITLES = {"motu patlu", "chhota bheem"}

SECTION_MARKERS = {
    "hook": ("hook", "မိတ်ဆက်", "အစပိုင်း", "စတင်"),
    "story": ("ဇာတ်လမ်း", "ဖြစ်ရပ်", "အခန်း", "story", "plot"),
    "turning_point": ("အလှည့်အပြောင်း", "turning point", "ပဋိပက္ခ"),
    "ending": ("အဆုံးသတ်", "climax", "ရလဒ်"),
    "commentary": ("သုံးသပ်", "ကိုယ်ပိုင်အမြင်", "သင်ခန်းစာ", "review"),
}
URL_RE = re.compile(r"https?://[^\\s<>]+", re.IGNORECASE)


def analyze_recap_script(category: str, title: str, script: str) -> dict:
    """Return a conservative QA report; never claims factual or legal verification."""
    category_key = " ".join((category or "").casefold().split())
    title_key = " ".join((title or "").casefold().split())
    body = (script or "").strip()
    issues = []
    passed = []

    if category_key not in ALLOWED_CATEGORIES:
        issues.append("အမျိုးအစားကို ခွင့်ပြုထားသော ၅ မျိုးထဲမှ တစ်မျိုးအဖြစ် တိတိကျကျ ရွေးပါ။")
    else:
        passed.append("အမျိုးအစား ၅ မျိုးထဲမှ တစ်မျိုးကို ရွေးထားသည်။")

    if title_key in EXCLUDED_TITLES:
        issues.append("ဤခေါင်းစဉ်ကို Project စည်းမျဉ်းအရ ဖယ်ထုတ်ထားသည်။")
    elif title_key:
        passed.append("ခေါင်းစဉ်သည် တားမြစ်စာရင်းထဲတွင် မပါဝင်ပါ။")
    else:
        issues.append("ဇာတ်ကား/ဇာတ်လမ်းအမည် မပါဝင်ပါ။")

    if len(body) < 250:
        issues.append("Script သည် အလွန်တိုနေသည်။ ဇာတ်လမ်းဖြစ်ရပ်နှင့် ကိုယ်ပိုင်သုံးသပ်ချက်ကို ပြည့်စုံအောင် ထည့်ပါ။")
    else:
        passed.append("Script အရှည် အခြေခံစစ်ဆေးမှု အောင်မြင်သည်။")

    lowered = body.casefold()
    missing = [
        label for label, terms in SECTION_MARKERS.items()
        if not any(term.casefold() in lowered for term in terms)
    ]
    if missing:
        labels = {
            "hook": "Opening Hook", "story": "ဇာတ်လမ်းဖြစ်ရပ်",
            "turning_point": "အလှည့်အပြောင်း/ပဋိပက္ခ",
            "ending": "Climax/အဆုံးသတ်", "commentary": "ကိုယ်ပိုင်သုံးသပ်ချက်",
        }
        issues.append("မတွေ့ရသေးသော အပိုင်းများ: " + "၊ ".join(labels[x] for x in missing))
    else:
        passed.append("Hook၊ ဇာတ်လမ်း၊ အလှည့်အပြောင်း၊ အဆုံးသတ်နှင့် သုံးသပ်ချက် အမှတ်အသားများ တွေ့ရှိသည်။")

    urls = URL_RE.findall(body)
    if not urls:
        issues.append("ရင်းမြစ် URL မတွေ့ပါ။ Plot facts အတွက် အတည်ပြုနိုင်သော source link များ ထည့်ပါ။")
    else:
        passed.append(f"ရင်းမြစ် URL {len(urls)} ခု တွေ့ရှိသည်။ အကြောင်းအရာကို ကိုယ်တိုင်ပြန်စစ်ရန် လိုသေးသည်။")

    paragraphs = [re.sub(r"\\s+", " ", p).strip().casefold()
                  for p in re.split(r"\\n\\s*\\n", body) if p.strip()]
    duplicates = len(paragraphs) - len(set(paragraphs))
    if duplicates:
        issues.append(f"တူညီသော paragraph {duplicates} ခု ထပ်နေသည်။")
    else:
        passed.append("Paragraph ထပ်နေမှု မတွေ့ပါ။")

    copyright_terms = ("လိုင်စင်", "ခွင့်ပြုချက်", "မူပိုင်ခွင့်", "licensed", "permission")
    if not any(term in lowered for term in copyright_terms):
        issues.append("Footage/music အတွက် ပိုင်ဆိုင်မှု သို့မဟုတ် အသုံးပြုခွင့်ကို စာတမ်းတွင် မဖော်ပြထားပါ။")
    else:
        passed.append("Media rights ဆိုင်ရာ မှတ်ချက်တစ်ခု ပါဝင်သည်။")

    status = "NOT READY" if any("ဖယ်ထုတ်ထားသည်" in item for item in issues) else ("REVIEW" if issues else "CHECK REQUIRED")
    return {
        "status": status,
        "category": category.strip(),
        "title": title.strip(),
        "characters": len(body),
        "source_urls": urls,
        "passed": passed,
        "issues": issues,
        "disclaimer": (
            "ဤစစ်ဆေးမှုသည် Script ဖွဲ့စည်းပုံကိုသာ စစ်သည်။ ဇာတ်လမ်းမှန်ကန်မှု၊ "
            "source ယုံကြည်စိတ်ချရမှု၊ မူပိုင်ခွင့်လိုက်နာမှု သို့မဟုတ် Views ကို အာမမခံပါ။ "
            "မထုတ်ဝေမီ လူကိုယ်တိုင် စစ်ဆေးပါ။"
        ),
    }


def format_recap_qa_report(report: dict) -> str:
    lines = [
        "🧪 NEXORA RECAP EDITORIAL QA",
        f"အခြေအနေ: {report['status']}",
        f"Category: {report['category']}",
        f"Title: {report['title']}",
        f"စာလုံးအရေအတွက်: {report['characters']} characters",
        "",
        "✅ စစ်ဆေးမှုများ",
    ]
    lines.extend(f"• {item}" for item in report["passed"])
    lines.extend(["", "⚠️ ပြင်ဆင်ရန်"])
    lines.extend(f"• {item}" for item in report["issues"])
    if not report["issues"]:
        lines.append("• ဖွဲ့စည်းပုံအရ ထင်ရှားသော ပြဿနာ မတွေ့ပါ။ သို့သော် လူကိုယ်တိုင် စစ်ဆေးရန် လိုသည်။")
    lines.extend(["", report["disclaimer"]])
    return "\\n".join(lines)
