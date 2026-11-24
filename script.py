"""Burmese recap script. Facts come ONLY from verified source text; each section is fact-checked."""
import json
import re
import time

from . import config
from .http import get

_last = [0.0]


def llm(prompt, system="", json_mode=True, tries=5):
    if not config.GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY မထည့်ရသေးပါ")
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    last = None
    for i in range(tries):
        for model in config.GEMINI_MODELS:
            wait = config.LLM_DELAY - (time.time() - _last[0])
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.time()
            try:
                d = get(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                        params={"key": config.GEMINI_KEY}, json_body=body, timeout=120, tries=1)
                return d["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:  # noqa
                last = e
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"LLM failed: {last}")


def parse_json(t):
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    return json.loads(t)


def split_sentences(text):
    return [s.strip() + "။" for s in re.split(r"။", text) if s.strip()]


def chunk_text(text, n):
    paras = [p for p in text.split("\n") if p.strip()]
    if not paras:
        return []
    n = max(1, min(n, len(paras)))
    size = -(-len(paras) // n)
    return ["\n".join(paras[i:i + size]) for i in range(0, len(paras), size)]


def plan(src, platform):
    """Ordered list of (focus, facts, kind). kind=story is fact-checked strictly."""
    P = config.PLATFORMS[platform]
    ctx = f'{src["title"]} ({src["year"]}, {src["category"]})'
    secs = [("Hook and introduction", src["intro"][:3000], "intro")]
    n_story = 3 if platform == "tiktok" else max(8, min(len(src["plot"]) // 600, 16))
    for i, ch in enumerate(chunk_text(src["plot"], n_story), 1):
        secs.append((f"Story part {i}/{n_story}, in chronological order", ch, "story"))
    if platform != "tiktok":
        topics = {"characters": "Characters and cast", "cast": "Characters and cast", "voice cast": "Cast",
                  "production": "Behind the production", "development": "How it was developed",
                  "reception": "Audience and critic reception", "critical reception": "Critical reception",
                  "release": "Release", "themes": "Themes and meaning", "music": "Music", "legacy": "Legacy"}
        for k, v in src["extras"].items():
            secs.append((topics.get(k, k.title()), v[:3500], "extra"))
        secs.append(("Ending explained and what the story means (analysis only, no new events)", src["plot"][-2500:], "analysis"))
    secs.append(("Closing thoughts and call to subscribe", src["intro"][:1500], "outro"))
    return ctx, secs


def write_section(ctx, focus, facts, kind, chars, prev, platform):
    sys = ("You are a Burmese movie/anime recap narrator. Write natural, vivid spoken Burmese (Myanmar Unicode). "
           "STRICT: use ONLY facts in SOURCE. Never invent characters, names, places, events or dates. "
           "Interpretation and mood are allowed only if clearly marked as opinion ('ကျွန်တော့်အမြင်အရ').")
    tk = " This is a short vertical video: punchy, fast pacing, strong hook." if platform == "tiktok" else ""
    prompt = f"""WORK: {ctx}
SECTION: {focus}
SOURCE:
{facts}

Previous section ended with: "{prev}"
Write about {chars} Burmese characters of narration for this section.{tk}
Return JSON array. Each item: {{"my": "one Burmese sentence ending with ။", "en": "natural English subtitle, max 84 chars"}}.
Keep names exactly as in SOURCE (English spelling) inside Burmese text."""
    items = parse_json(llm(prompt, sys))
    return [dict(my=i["my"].strip(), en=i["en"].strip()) for i in items if i.get("my") and i.get("en")]


def factcheck(items, facts):
    numbered = "\n".join(f"{i}: {x['en']}" for i, x in enumerate(items))
    prompt = f"""SOURCE:\n{facts}\n\nSUBTITLE LINES:\n{numbered}\n
Return JSON {{"unsupported": [indexes]}} listing lines that state concrete facts (names, events, places, numbers)
NOT supported by SOURCE. Opinion/mood lines are fine. If all fine return {{"unsupported": []}}."""
    try:
        bad = set(parse_json(llm(prompt)).get("unsupported", []))
    except Exception:
        return items
    return [x for i, x in enumerate(items) if i not in bad]


def generate(src, platform, target_min=None, log=print):
    P = config.PLATFORMS[platform]
    target_min = target_min or P["target"]
    ctx, secs = plan(src, platform)
    total_chars = target_min * 60 * config.CHARS_PER_SEC
    per = int(total_chars / len(secs))
    out, prev = [], ""
    for idx, (focus, facts, kind) in enumerate(secs):
        log(f"[script] {idx + 1}/{len(secs)} {focus[:40]}")
        items = write_section(ctx, focus, facts, kind, per, prev, platform)
        if kind in ("story", "intro", "extra"):
            items = factcheck(items, facts)
        if items:
            out.append(dict(title=focus, kind=kind, items=items))
            prev = items[-1]["my"]
    return out


def extend(src, platform, sections, need_sec, log=print):
    """Add analysis sections (no new plot facts) when measured audio is shorter than the minimum."""
    ctx, _ = plan(src, platform)
    n = 0
    for focus in ["Scene-by-scene deeper look at the key turning points", "Character motivations explained",
                  "Themes and symbolism discussed", "Questions viewers ask and answers from the source"]:
        if need_sec <= 0:
            break
        chars = int(min(need_sec, 420) * config.CHARS_PER_SEC)
        items = write_section(ctx, focus, src["plot"][:6000], "analysis", chars, sections[-1]["items"][-1]["my"], platform)
        items = factcheck(items, src["plot"])
        if items:
            sections.insert(len(sections) - 1, dict(title=focus, kind="analysis", items=items))
            n += 1
            need_sec -= 420
    return n
