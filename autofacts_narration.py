"""Build a short Burmese factual introduction from exact Wikidata metadata.

This deliberately does not invent or summarize plot events. It only speaks
fields present in Wikidata, preferring Burmese labels where available.
"""


def generate_burmese_facts_narration(metadata: dict) -> str:
    if not isinstance(metadata, dict) or not metadata.get("found"):
        raise ValueError("အမည်တိတိကျကျ ကိုက်ညီသော Wikidata မှတ်တမ်း မရှိပါ။")

    title = " ".join(str(metadata.get("title_my") or metadata.get("title") or "").split()).strip()
    if not title:
        raise ValueError("ဇာတ်ကားအမည် မရရှိပါ။")

    countries = metadata.get("countries_my") or []
    directors = metadata.get("directors_my") or []
    genres = metadata.get("genres_my") or []
    languages = metadata.get("languages_my") or []
    year = str(metadata.get("year") or "").strip()

    # Do not produce content for Indian titles; this project excludes them.
    country_text = " ".join(str(item) for item in (metadata.get("countries") or [])).casefold()
    if "india" in country_text or any("အိန္ဒိယ" in str(item) for item in countries):
        raise ValueError("ဒီ Project မှာ အိန္ဒိယဇာတ်ကားများ မထည့်ထားပါ။")

    lines = [f"ဒီနေ့ NEXORA မှာ {title} အကြောင်း အခြေခံအချက်အလက်တွေကို မိတ်ဆက်ပေးပါမယ်။"]
    if year:
        lines.append(f"ဒီဇာတ်ကားရဲ့ ထွက်ရှိသည့်နှစ်ကို {year} ခုနှစ်အဖြစ် Wikidata မှာ ဖော်ပြထားပါတယ်။")
    if countries:
        lines.append("မူရင်းနိုင်ငံ သို့မဟုတ် ဒေသအဖြစ် " + "၊ ".join(str(x) for x in countries[:3]) + " ကို ဖော်ပြထားပါတယ်။")
    if genres:
        lines.append("အမျိုးအစားအချက်အလက်မှာ " + "၊ ".join(str(x) for x in genres[:3]) + " လို့ ဖော်ပြထားပါတယ်။")
    if directors:
        lines.append("ဒါရိုက်တာအဖြစ် " + "၊ ".join(str(x) for x in directors[:2]) + " ကို ဖော်ပြထားပါတယ်။")
    if languages:
        lines.append("မူရင်းဘာသာစကားအချက်အလက်မှာ " + "၊ ".join(str(x) for x in languages[:3]) + " ဖြစ်ပါတယ်။")

    if len(lines) == 1:
        raise ValueError("မြန်မာလို အသံဖန်တီးရန် လုံလောက်သော အတည်ပြု metadata မရှိပါ။")

    lines.append(
        "ဒီဗီဒီယိုဟာ အခြေခံအချက်အလက် မိတ်ဆက်ချက်သာ ဖြစ်ပြီး ဇာတ်ကွက်အသေးစိတ်ကို "
        "မခန့်မှန်းထားပါဘူး။ အချက်အလက်တွေကို မူရင်းထုတ်လုပ်သူရင်းမြစ်နဲ့ ထပ်မံစစ်ဆေးပါ။"
    )
    lines.append("ရင်းမြစ်ကို ဗီဒီယိုဖော်ပြချက်မှာ ထည့်ပေးထားပါတယ်။")
    return "\n".join(lines)
