"""Build an original Burmese recap brief from factual movie metadata and public trend signals.

Foreign recap videos are used only to observe broad presentation patterns and public
metadata (channel, title, views, publication date). Their scripts, narration, edits,
transcripts, thumbnails, and footage are never copied or extracted.
"""
from __future__ import annotations


def build_original_recap_notes(movie_report: dict, recap_examples: list[dict]) -> str:
    title = str(movie_report.get("title") or "Unknown title")
    tmdb = movie_report.get("tmdb") or {}
    wikidata = movie_report.get("wikidata") or {}
    gemini = movie_report.get("gemini") or {}
    if movie_report.get("india_excluded"):
        raise ValueError("အိန္ဒိယမူရင်း/ထုတ်လုပ်မှုပါဝင်သည့် ရုပ်ရှင်ကို NEXORA စည်းမျဉ်းအရ ပယ်ချထားသည်။")
    if not tmdb.get("found") and not wikidata.get("found") and not gemini.get("found"):
        # Show safe provider statuses so operators can distinguish missing
        # credentials from exact-match or upstream network failures.
        diagnostics = []
        for provider, result in (("TMDB", tmdb), ("Wikidata", wikidata), ("Gemini Google Search", gemini)):
            status = str(result.get("status") or "အကြောင်းရင်း မသိရှိပါ။").strip()
            diagnostics.append(f"{provider}: {status}")
        detail = "\n".join(diagnostics)
        raise ValueError(
            "TMDB/Wikidata/Gemini မှ အတည်ပြုနိုင်သော ရုပ်ရှင်အချက်အလက် မရရှိပါ။ "
            "မခန့်မှန်းဘဲ ရပ်ထားသည်။\n\nရင်းမြစ်စစ်ဆေးချက်:\n" + detail +
            "\n\nGemini Search မရပါက Render Environment တွင် GEMINI_API_KEY နှင့် "
            "GEMINI_RESEARCH_MODEL ကို စစ်ဆေးပါ။ TMDB သည် optional ဖြစ်သည်။ "
            "Token တန်ဖိုးကို Chat ထဲ မပို့ပါနှင့်။"
        )
    lines = [
        "NEXORA ORIGINAL RECAP PRODUCTION BRIEF",
        "Movie: " + title,
        "",
        "VERIFIED CATALOGUE FACTS (use only what is present; do not invent missing plot events):",
    ]
    if tmdb.get("found"):
        lines.extend([
            "TMDB title: " + str(tmdb.get("title") or ""),
            "Original title: " + str(tmdb.get("original_title") or ""),
            "Release year: " + str(tmdb.get("year") or ""),
            "Original language: " + str(tmdb.get("original_language") or ""),
            "Production countries: " + ", ".join(tmdb.get("countries") or []),
            "Official catalogue overview: " + str(tmdb.get("overview") or "Not supplied"),
            "TMDB source: " + str(tmdb.get("provider_url") or ""),
        ])
    if wikidata.get("found"):
        lines.extend([
            "Wikidata countries: " + ", ".join(wikidata.get("countries") or []),
            "Wikidata year: " + str(wikidata.get("year") or ""),
            "Wikidata genres: " + ", ".join(wikidata.get("genres") or []),
            "Wikidata source: " + str(wikidata.get("source") or ""),
        ])
    if gemini.get("found"):
        lines.extend([
            "Gemini grounded title: " + str(gemini.get("title") or ""),
            "Gemini release year: " + str(gemini.get("year") or ""),
            "Gemini production countries: " + ", ".join(gemini.get("countries") or []),
            "Gemini overview: " + str(gemini.get("overview") or "Not supplied"),
            "Gemini source URLs: " + " | ".join(item.get("url", "") for item in gemini.get("sources", [])[:8]),
        ])
    lines.extend([
        "",
        "FOREIGN RECAP MARKET RESEARCH — metadata only, not source material:",
    ])
    if recap_examples:
        for index, item in enumerate(recap_examples[:8], 1):
            lines.append(
                f"{index}. {item.get('channel', 'Unknown channel')} | "
                f"{item.get('title', 'Untitled')} | "
                f"views={int(item.get('views', 0)):,} | "
                f"published={item.get('published_at', 'unknown')} | "
                f"url={item.get('url', '')}"
            )
    else:
        lines.append("No relevant foreign recap examples were found.")
    lines.extend([
        "",
        "ORIGINALITY AND RIGHTS REQUIREMENTS:",
        "- Use foreign recap results only to understand broad market positioning, pacing expectations, and title/topic demand.",
        "- Never translate, paraphrase closely, summarize, imitate the sequence of, or reproduce any foreign recap video's script, transcript, narration, thumbnail, edit, or footage.",
        "- Create a fresh Burmese editorial structure and original commentary from verified movie facts only.",
        "- The catalogue overview is only a short synopsis. Do not fabricate scenes, character names, dialogue, twists, or an ending that is not supported by verified notes.",
        "- If a full plot is required but reliable plot notes are missing, clearly mark the draft as an outline/preview and request more verified plot research instead of inventing.",
        "- For final video visuals, use only user-owned, licensed, public-domain, or otherwise specifically authorized assets. A YouTube CC BY search label is not proof that the uploader owns every embedded asset.",
        "- Add original analysis, context, and Burmese narration; avoid a near-substitute for the original movie or another recap.",
        "",
        "EDITORIAL GOAL:",
        "Produce a distinctly original Burmese-language recap concept informed by market metadata, not by copying competitor creative expression. Separate verified facts from analysis and uncertainty.",
    ])
    return "\n".join(lines)
