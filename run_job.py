"""One pipeline run: research -> script -> TTS -> SRT -> render -> QC -> deliver. Stages: research|script|voice|full."""
import argparse
import datetime as dt
import json
import shutil
import traceback
from pathlib import Path

from . import config, publish, qc, research, script, social, state, subs, tts, render


def free_gb(p="."):
    return shutil.disk_usage(p).free / 1e9


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", required=True, choices=list(config.PLATFORMS))
    ap.add_argument("--title", default="")
    ap.add_argument("--stage", default="full", choices=["research", "script", "voice", "full"])
    ap.add_argument("--voice", default="story_female")
    ap.add_argument("--profile", default="")
    ap.add_argument("--chat", default="")
    ap.add_argument("--minutes", type=float, default=0)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--from-daily", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    chat = a.chat or None
    say = lambda m: (print(m), publish.tg(m, chat))  # noqa
    key = f"{a.date}:{a.platform}:{a.stage}:{a.title or 'auto'}"
    if not a.force and state.job_done(key):
        say(f"⏭ {key} ပြီးသားဖြစ်လို့ ကျော်လိုက်ပါတယ် (idempotent)")
        return 0
    wd = config.WORK_DIR / f"{a.date}_{a.platform}"
    shutil.rmtree(wd, ignore_errors=True)
    wd.mkdir(parents=True)
    try:
        if free_gb() < 5:
            raise RuntimeError(f"disk မလုံလောက်ပါ ({free_gb():.1f} GB free)")
        # 1. RESEARCH
        say(f"🔎 [{a.platform}] Research စတင်ပါပြီ")
        if a.from_daily:
            daily = state.load_daily(a.date)
            if not daily or a.platform not in daily:
                raise RuntimeError("daily picks မတွေ့ပါ")
            src = daily[a.platform]
        elif a.title:
            src = research.resolve_title(a.title, a.platform, say)
        else:
            src = research.pick(a.platform, log=say)
            state.mark_used(src["title"], a.platform, a.date, src["category"])
        say(f"✅ Title: {src['title']} ({src['year']}) • {src['category']}\nSources: {', '.join(src['sources'])}\nWikipedia views(30d): {src['views']}\n{src['wiki_url']}")
        if a.stage == "research":
            state.mark_job(key, status="done")
            return 0
        # 2. SCRIPT
        sections = script.generate(src, a.platform, a.minutes or None, say)
        sf = config.OUT_DIR / f"{a.platform}_script.json"
        sf.write_text(json.dumps(sections, ensure_ascii=False, indent=1), "utf-8")
        txt = config.OUT_DIR / f"{a.platform}_script_my.txt"
        txt.write_text("\n\n".join(s["title"] + "\n" + " ".join(i["my"] for i in s["items"]) for s in sections), "utf-8")
        n = sum(len(s["items"]) for s in sections)
        say(f"📝 Script ပြီးပါပြီ: {len(sections)} sections / {n} sentences")
        if a.stage == "script":
            publish.tg_file(txt, "Burmese script", chat)
            state.mark_job(key, status="done")
            return 0
        # 3. VOICE + SRT
        profile = None
        if a.profile:
            from .voices import get_profile
            profile = get_profile(a.profile)
        P = config.PLATFORMS[a.platform]
        mp3 = config.OUT_DIR / f"{a.platform}_narration.mp3"
        say("🎙 အသံထုတ်နေပါပြီ...")
        timeline, dur = tts.build_audio(sections, a.voice, profile, wd / "tts", mp3, say)
        for _ in range(3):  # measured duration too short -> add analysis sections, never fake padding
            if dur >= P["min"] * 60 + 20:
                break
            say(f"⏱ Audio {dur / 60:.1f} min < {P['min']} min — analysis section ထပ်ထည့်ပါမယ်")
            if not script.extend(src, a.platform, sections, P["min"] * 60 + 40 - dur, say):
                break
            timeline, dur = tts.build_audio(sections, a.voice, profile, wd / "tts", mp3, say)
        if dur > P["max"] * 60:
            while dur > P["max"] * 60 and len(sections) > 3:
                sections.pop(-2)
                timeline, dur = tts.build_audio(sections, a.voice, profile, wd / "tts", mp3, say)
        if not (P["min"] * 60 <= dur <= P["max"] * 60):
            raise RuntimeError(f"Audio {dur / 60:.1f} min သည် {P['min']}–{P['max']} min အပြင်ဖြစ်နေသည် — source ထိုက်တန်စွာမရှိ။ အခြား title ဖြင့် retry လုပ်ပါ")
        en, my = config.OUT_DIR / f"{a.platform}_en.srt", config.OUT_DIR / f"{a.platform}_my.srt"
        r1, r2 = subs.write_srt(timeline, en, "en"), subs.write_srt(timeline, my, "my")
        if not (r1["ok"] and r2["ok"]):
            raise RuntimeError(f"SRT issues: {r1['issues'][:3]} {r2['issues'][:3]}")
        say(f"🔊 MP3 {dur / 60:.1f} min • SRT {r1['cues']} cues ✔")
        if a.stage == "voice":
            for f in (mp3, en, my, txt):
                publish.tg_file(f, f.name, chat)
            state.mark_job(key, status="done")
            return 0
        # 4. RENDER + QC
        say("🎬 Video render စတင်ပါပြီ (အချိန်အနည်းငယ်ကြာမယ်)")
        shutil.copy(en, wd / "en.srt")
        out = config.OUT_DIR / f"{a.platform}_{state.norm(src['title'])[:30]}_{a.date}.mp4"
        render.render(timeline, mp3, wd / "en.srt", a.platform, src["title"], wd / "r", out, say)
        q = qc.check_mp4(out, a.platform)
        if not q["ok"]:
            raise RuntimeError("QC failed: " + "; ".join(q["issues"]))
        meta = social.metadata(src, a.platform)
        (config.OUT_DIR / f"{a.platform}_metadata.txt").write_text(f"{meta['title']}\n\n{meta['description']}", "utf-8")
        up = social.auto_upload(a.platform, out, meta, say)
        cap = f"✅ {meta['title']}\n{q['duration_min']} min • {q['size_mb']} MB • QC passed\n\n{meta['cta']}\n\nUpload: {up}"
        how = publish.deliver(out, [en, my, mp3, config.OUT_DIR / f"{a.platform}_metadata.txt"], cap, wd, chat, f"{a.date}_{a.platform}")
        say(f"📦 ပို့ပြီးပါပြီ ({how}) • {up}")
        state.mark_job(key, status="done", title=src["title"], qc=q)
        return 0
    except Exception as e:
        traceback.print_exc()
        state.mark_job(key, status="failed", error=str(e))
        say(f"❌ [{a.platform}] {a.stage} မအောင်မြင်ပါ: {e}")
        return 1
    finally:
        shutil.rmtree(wd, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
