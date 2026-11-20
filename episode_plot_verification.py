"""Conservative cross-catalogue episode alignment and plot-text comparison.

This module reports possible correspondences and numbering/title discrepancies.
It never labels a plot as fact-verified: catalogue descriptions are community
research leads and may be translated, abridged, or inconsistent.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from itertools import combinations


PROVIDERS = ("TVmaze", "Kitsu", "Bangumi")


def _norm(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def _number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
        if number < 0:
            return None
        return str(int(number)) if number.is_integer() else str(number)
    except (TypeError, ValueError, OverflowError):
        return None


def _same_slot(left, right):
    left_number = _number(left.get("number"))
    right_number = _number(right.get("number"))
    if left_number is None or right_number is None or left_number != right_number:
        return False
    left_season = _number(left.get("season"))
    right_season = _number(right.get("season"))
    return left_season is None or right_season is None or left_season == right_season


def _text_similarity(left, right):
    a = _norm(left)
    b = _norm(right)
    if not a or not b:
        return None
    return round(SequenceMatcher(None, a, b).ratio(), 3)


def verify_episode_plot_sources(collection):
    """Align only exact episode-title/number candidates and report same-slot conflicts."""
    if not isinstance(collection, dict) or not collection.get("title"):
        return {"found": False, "status": "Episode Plot Collection မရရှိပါ။"}
    sources = collection.get("sources") or {}
    available = {
        provider: (sources.get(provider) or {}).get("episodes") or []
        for provider in PROVIDERS
        if (sources.get(provider) or {}).get("found")
    }
    if len(available) < 2:
        return {
            "found": False,
            "title": collection.get("title"),
            "status": "Episode plot အချက်အလက်ပါသော သီးခြား Catalogue ရင်းမြစ် အနည်းဆုံး ၂ ခု မရရှိပါ။",
            "available_providers": list(available),
            "matches": [],
            "slot_conflicts": [],
        }

    matches = []
    conflicts = []
    compared_pairs = []
    for provider_a, provider_b in combinations(available, 2):
        compared_pairs.append((provider_a, provider_b))
        for episode_a in available[provider_a]:
            for episode_b in available[provider_b]:
                if not _same_slot(episode_a, episode_b):
                    continue
                title_a = _norm(episode_a.get("title"))
                title_b = _norm(episode_b.get("title"))
                record = {
                    "providers": [provider_a, provider_b],
                    "season": episode_a.get("season") if episode_a.get("season") is not None else episode_b.get("season"),
                    "number": episode_a.get("number"),
                    "titles": [
                        str(episode_a.get("title") or "မရှိ"),
                        str(episode_b.get("title") or "မရှိ"),
                    ],
                    "sources": [episode_a.get("source") or "", episode_b.get("source") or ""],
                }
                if title_a and title_a == title_b:
                    similarity = _text_similarity(
                        episode_a.get("summary_excerpt"), episode_b.get("summary_excerpt")
                    )
                    record["text_similarity"] = similarity
                    record["status"] = "တူညီနိုင်သော Episode — လူကိုယ်တိုင် ဇာတ်ကွက်စစ်ဆေးရန်"
                    matches.append(record)
                else:
                    record["status"] = "Episode နံပါတ်တူသော်လည်း ခေါင်းစဉ်မတူ — numbering/translation discrepancy စစ်ရန်"
                    conflicts.append(record)

    return {
        "found": True,
        "title": collection.get("title"),
        "providers": list(available),
        "compared_provider_pairs": [list(pair) for pair in compared_pairs],
        "matches": matches,
        "slot_conflicts": conflicts,
        "scope": "candidate_alignment_not_factual_verification",
    }


def format_episode_plot_verification(report):
    if not isinstance(report, dict) or not report.get("title"):
        return "Episode Plot Verification အတွက် ခေါင်းစဉ် မရရှိပါ။"
    lines = [
        "🔍 NEXORA — EPISODE PLOT CROSS-SOURCE CHECK",
        "Series: " + str(report.get("title")),
    ]
    if not report.get("found"):
        lines.extend([
            str(report.get("status") or "Cross-source comparison မရရှိပါ။"),
            "ဇာတ်ကွက်အမှန်ဖြစ်ကြောင်း အလိုအလျောက် အတည်မပြုထားပါ။",
        ])
        return "\n".join(lines)

    lines.extend([
        "ရင်းမြစ်များ: " + ", ".join(report.get("providers") or []),
        "နှိုင်းယှဉ်မှု: Episode နံပါတ် + ခေါင်းစဉ် တိတိကျကျ ကိုက်ညီမှုကိုသာ candidate အဖြစ် စစ်ထားသည်။",
        "",
        "【POTENTIAL EPISODE MATCHES】",
    ])
    matches = report.get("matches") or []
    if not matches:
        lines.append("နံပါတ်နှင့် ခေါင်းစဉ် တိတိကျကျ ကိုက်ညီသော Episode မတွေ့ပါ။")
    for item in matches:
        season = item.get("season")
        number = item.get("number")
        label = (f"S{season} " if season is not None else "") + (f"E{number}" if number is not None else "Episode")
        lines.append(
            f"{label}: {item['providers'][0]} “{item['titles'][0]}” ↔ "
            f"{item['providers'][1]} “{item['titles'][1]}”"
        )
        similarity = item.get("text_similarity")
        if similarity is not None:
            lines.append(f"စာသားတူညီမှုအချက်ပြ: {similarity:.3f} (အချက်အလက်မှန်ကန်မှု score မဟုတ်ပါ)")
        lines.append(item.get("status") or "")
        for source in item.get("sources") or []:
            if source:
                lines.append("Source: " + source)

    lines.extend(["", "【NUMBERING / TITLE DISCREPANCIES】"])
    conflicts = report.get("slot_conflicts") or []
    if not conflicts:
        lines.append("တူညီသော Episode slot တွင် ခေါင်းစဉ်မတူသည့် မှတ်တမ်း မတွေ့ပါ။")
    for item in conflicts:
        season = item.get("season")
        number = item.get("number")
        label = (f"S{season} " if season is not None else "") + f"E{number}"
        lines.append(
            f"{label}: {item['providers'][0]} “{item['titles'][0]}” ↔ "
            f"{item['providers'][1]} “{item['titles'][1]}”"
        )
        lines.append(item.get("status") or "")
        for source in item.get("sources") or []:
            if source:
                lines.append("Source: " + source)

    lines.extend([
        "",
        "အရေးကြီး:",
        "• တူညီသော Episode ခေါင်းစဉ်/နံပါတ်သည် ဇာတ်ကွက်အမှန်ဖြစ်ကြောင်း သက်သေမဟုတ်ပါ။",
        "• စာသားတူညီမှုသည် ဘာသာပြန်၊ အကျဉ်းချုံ့မှုနှင့် wording ကွာခြားမှုကြောင့် ပြောင်းလဲနိုင်ပြီး fact-check score မဟုတ်ပါ။",
        "• ဇာတ်ကွက်ဖြစ်ရပ်တိုင်းကို မူရင်း Episode နှင့် ယုံကြည်စိတ်ချရသော ရင်းမြစ်ဖြင့် လူကိုယ်တိုင် စစ်ဆေးပါ။",
        "• ဒီ report သည် script, transcript, footage license သို့မဟုတ် publishing permission မဟုတ်ပါ။",
    ])
    return "\n".join(lines)
