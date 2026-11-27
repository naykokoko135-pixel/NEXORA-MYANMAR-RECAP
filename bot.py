"""Telegram control bot (light; runs on Render Free). Heavy work is dispatched to GitHub Actions."""
import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from . import config, gh, research, voices

SETTINGS_FILE = config.DATA_DIR / "settings.json"
DEFAULTS = dict(platform="youtube", mode="full", voice="story_female", profile="", srt="en", minutes=0)
HELP = """🎬 Nexora Recap Bot
/create [youtube|facebook|tiktok] [title] — video အပြည့် (title မပေးရင် trend အလိုက်)
/auto — daily pipeline (3 platform) အခု run
/draft /draft3 /aiscript — script သာ
/voiceover /voiceover3 — script+MP3+SRT
/recapvideo /recapstudio /render — MP4 အပြည့်
/multisourceresearch [platform] — research report
/animationepisodes <title> — episode စာရင်း
/voices — voice presets • /tts_design <preset> • /voiceclone <profile>
/voiceprofile list|add <name>|delete <name>  (audio ပို့ပြီး caption မှာ /voiceprofile add name)
/scenetts <text> — TTS စမ်း • /effects • /srt on|off|en|my|both
/platform <p> • /duration <min> • /mode draft|voice|full • /settings
/status • /cancel • /retry • /health • /commentstatus • /studio (website automation status)"""


def load_settings(chat):
    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text("utf-8")).get(str(chat), {})}
    except Exception:
        return dict(DEFAULTS)


def save_setting(chat, **kw):
    try:
        d = json.loads(SETTINGS_FILE.read_text("utf-8"))
    except Exception:
        d = {}
    d[str(chat)] = {**d.get(str(chat), {}), **kw}
    SETTINGS_FILE.write_text(json.dumps(d), "utf-8")


async def reply(u, text):
    await u.effective_message.reply_text(text[:4000], disable_web_page_preview=True)


def parse_platform(args, s):
    if args and args[0].lower() in config.PLATFORMS:
        return args[0].lower(), " ".join(args[1:])
    return s["platform"], " ".join(args)


def need_gh():
    if not os.getenv("GH_TOKEN"):
        raise RuntimeError("Render env မှာ GH_TOKEN မထည့်ရသေးပါ (README ကြည့်ပါ)")


async def launch(u, stage, args, title_ok=True, multi=False):
    s = load_settings(u.effective_chat.id)
    try:
        need_gh()
        if multi:
            gh.dispatch("daily.yml", dict(stage=stage, voice=s["voice"], profile=s["profile"], chat=u.effective_chat.id))
            return await reply(u, f"🚀 3 platform ({stage}) စတင်ပါပြီ။ ရလဒ်ကို ဒီ chat ထဲ ပို့ပေးပါမယ်။")
        p, title = parse_platform(args, s)
        gh.dispatch("render.yml", dict(platform=p, title=title if title_ok else "", stage=stage, voice=s["voice"],
                                       profile=s["profile"], chat=u.effective_chat.id, minutes=s["minutes"]))
        await reply(u, f"🚀 {p} • {stage} • {title or 'auto trend'} စတင်ပါပြီ။ /status ဖြင့်ကြည့်နိုင်ပါတယ်။")
    except Exception as e:
        await reply(u, f"❌ {e}")


def cmd(stage, multi=False):
    async def h(u: Update, c: ContextTypes.DEFAULT_TYPE):
        s = load_settings(u.effective_chat.id)
        st = s["mode"] if stage == "mode" else stage
        st = {"draft": "script", "voice": "voice", "full": "full"}.get(st, st)
        await launch(u, st, c.args, multi=multi)
    return h


async def start(u, c):
    await reply(u, "မင်္ဂလာပါ 👋\n" + HELP)


async def help_(u, c):
    await reply(u, HELP)


async def settings_(u, c):
    s = load_settings(u.effective_chat.id)
    await reply(u, "⚙️ " + "\n".join(f"{k}: {v}" for k, v in s.items()))


def setter(key, valid=None, conv=str):
    async def h(u, c):
        if not c.args:
            return await reply(u, f"အသုံးပြုပုံ: /{key} <value> • အခု: {load_settings(u.effective_chat.id)[key]}")
        try:
            v = conv(c.args[0])
        except Exception:
            return await reply(u, "တန်ဖိုး မမှန်ပါ")
        if valid and v not in valid:
            return await reply(u, f"ရွေးချယ်စရာ: {', '.join(map(str, valid))}")
        save_setting(u.effective_chat.id, **{key: v})
        await reply(u, f"✅ {key} = {v}")
    return h


async def duration(u, c):
    s = load_settings(u.effective_chat.id)
    P = config.PLATFORMS[s["platform"]]
    try:
        m = float(c.args[0])
        assert P["min"] <= m <= P["max"]
    except Exception:
        return await reply(u, f"{s['platform']} အတွက် {P['min']}–{P['max']} မိနစ်အတွင်းသာ ပေးပါ။ (0 = default)")
    save_setting(u.effective_chat.id, minutes=m)
    await reply(u, f"✅ target {m} min")


async def voices_(u, c):
    await reply(u, "🎙 Presets:\n" + "\n".join(f"• {k}" for k in config.VOICE_PRESETS) +
                "\n\nကိုယ်ပိုင်အသံ: /voiceprofile add <name> (audio ပို့ပါ) → /voiceclone <name>")


async def tts_design(u, c):
    if not c.args or c.args[0] not in config.VOICE_PRESETS:
        return await reply(u, "preset: " + ", ".join(config.VOICE_PRESETS))
    save_setting(u.effective_chat.id, voice=c.args[0], profile="")
    await reply(u, f"✅ voice = {c.args[0]}")


async def voiceclone(u, c):
    if not c.args:
        return await reply(u, "/voiceclone <profile> (သို့) /voiceclone off")
    if c.args[0] == "off":
        save_setting(u.effective_chat.id, profile="")
        return await reply(u, "✅ clone ပိတ်ပြီး preset ပြန်သုံးမယ်")
    try:
        voices.get_profile(c.args[0])
    except Exception as e:
        return await reply(u, f"❌ {e}")
    note = "" if os.getenv("VOICE_GPU_URL") else "\n⚠️ VOICE_GPU_URL မထည့်ရသေးလို့ preset TTS fallback သုံးမယ်"
    save_setting(u.effective_chat.id, profile=c.args[0])
    await reply(u, f"✅ profile = {c.args[0]}{note}")


async def voiceprofile(u, c):
    a = c.args or ["list"]
    try:
        if a[0] == "list":
            ps = voices.listing()
            return await reply(u, "👤 Profiles:\n" + ("\n".join("• " + p["name"] for p in ps) or "မရှိသေးပါ"))
        if a[0] == "delete" and len(a) > 1:
            voices.delete(a[1])
            return await reply(u, "🗑 ဖျက်ပြီး")
        if a[0] == "export":
            f = voices.export_zip(Path(tempfile.gettempdir()) / "voices_backup.zip")
            return await u.effective_message.reply_document(open(f, "rb"))
        if a[0] == "add" and len(a) > 1:
            m = u.effective_message.reply_to_message
            if not (m and (m.voice or m.audio or m.document)):
                return await reply(u, "audio/voice message ကို reply လုပ်ပြီး /voiceprofile add <name> ပို့ပါ")
            await handle_audio(u, c, name=a[1], msg=m)
            return
    except Exception as e:
        return await reply(u, f"❌ {e}")
    await reply(u, "/voiceprofile list | add <name> | delete <name> | export")


async def handle_audio(u, c, name=None, msg=None):
    msg = msg or u.effective_message
    cap = (msg.caption or "").split()
    if name is None:
        if len(cap) < 3 or cap[0] != "/voiceprofile" or cap[1] != "add":
            return
        name = cap[2]
    att = msg.voice or msg.audio or msg.document
    f = await att.get_file()
    data = bytes(await f.download_as_bytearray())
    n = voices.add(name, data, ext=(f.file_path or "x.ogg").rsplit(".", 1)[-1], meta=dict(owner=str(u.effective_chat.id)))
    await reply(u, f"✅ profile '{n}' သိမ်းပြီး ({len(data) // 1024} KB)")


async def scenetts(u, c):
    text = " ".join(c.args)
    if not text:
        return await reply(u, "/scenetts <မြန်မာစာ>")
    import edge_tts
    s = load_settings(u.effective_chat.id)
    v, pitch, rate = config.VOICE_PRESETS[s["voice"]]
    p = Path(tempfile.gettempdir()) / "scenetts.mp3"
    await edge_tts.Communicate(text, v, rate=rate, pitch=pitch).save(str(p))
    if not p.exists() or p.stat().st_size < 1000:
        return await reply(u, "❌ TTS မအောင်မြင်ပါ")
    await u.effective_message.reply_audio(open(p, "rb"))


async def research_cmd(u, c):
    s = load_settings(u.effective_chat.id)
    p = c.args[0] if c.args and c.args[0] in config.PLATFORMS else s["platform"]
    await reply(u, f"🔎 {p} research လုပ်နေပါတယ်...")
    try:
        r = await asyncio.to_thread(research.pick, p, (), (), None, lambda *_: None)
        await reply(u, f"✅ {r['title']} ({r['year']}) [{r['category']}]\nSources: {', '.join(r['sources'])}\n"
                       f"Views30d: {r['views']} • plot {len(r['plot'])} chars\n{r['wiki_url']}")
    except Exception as e:
        await reply(u, f"❌ {e}")


async def episodes(u, c):
    if not c.args:
        return await reply(u, "/animationepisodes <title>")
    try:
        name, seasons = await asyncio.to_thread(research.episodes, " ".join(c.args))
        await reply(u, f"📺 {name}\n" + "\n".join(f"Season {k}: {v} eps" for k, v in sorted(seasons.items())))
    except Exception as e:
        await reply(u, f"❌ မတွေ့ပါ: {e}")


async def status(u, c):
    try:
        need_gh()
        rs = await asyncio.to_thread(gh.runs, 6)
        await reply(u, "📊\n" + "\n".join(f"#{r['id']} {r['name']} • {r['status']}/{r['conclusion'] or '…'}" for r in rs))
    except Exception as e:
        await reply(u, f"❌ {e}")


async def cancel(u, c):
    try:
        need_gh()
        rs = await asyncio.to_thread(gh.runs, 10)
        act = [r for r in rs if r["status"] in ("in_progress", "queued")]
        for r in act:
            await asyncio.to_thread(gh.cancel, r["id"])
        await reply(u, f"🛑 {len(act)} job ရပ်လိုက်ပါပြီ")
    except Exception as e:
        await reply(u, f"❌ {e}")


async def retry(u, c):
    try:
        need_gh()
        rs = await asyncio.to_thread(gh.runs, 10)
        f = next((r for r in rs if r["conclusion"] == "failure"), None)
        if not f:
            return await reply(u, "failed job မရှိပါ")
        ok = await asyncio.to_thread(gh.rerun, f["id"])
        await reply(u, "🔁 retry စတင်ပါပြီ" if ok else "❌ retry မရပါ")
    except Exception as e:
        await reply(u, f"❌ {e}")


async def health(u, c):
    chk = {"GEMINI_API_KEY": bool(config.GEMINI_KEY), "TMDB_API_KEY": bool(config.TMDB_KEY), "GH_TOKEN": bool(os.getenv("GH_TOKEN")),
           "R2 (large file link)": bool(os.getenv("R2_BUCKET")), "GPU worker": bool(os.getenv("VOICE_GPU_URL")),
           "Persistent voice dir": str(voices.ROOT), "disk free GB": round(shutil.disk_usage(".").free / 1e9, 1)}
    await reply(u, "🩺\n" + "\n".join(f"{'✅' if v else '⚠️'} {k}: {v}" for k, v in chk.items()))


async def studio_(u, c):
    try:
        from .studio import notifier
        await reply(u, await asyncio.to_thread(notifier.status_text))
    except Exception as e:
        await reply(u, f"❌ Studio မရနိုင်ပါ: {e}")


async def effects(u, c):
    await reply(u, "🎞 Effects:\n" + "\n".join("• " + e for e in config.EFFECTS))


async def commentstatus(u, c):
    on = os.getenv("COMMENT_REPLY", "0") == "1" and os.getenv("YT_REFRESH_TOKEN")
    await reply(u, "💬 Comment auto-reply: " + ("API ready (enabled)" if on else "OFF — YouTube/Facebook API ခွင့်ပြုချက် + COMMENT_REPLY=1 လိုအပ်"))


def build():
    app = Application.builder().token(config.TG_TOKEN).build()
    H = app.add_handler
    simple = {"start": start, "help": help_, "settings": settings_, "voices": voices_, "tts_design": tts_design,
              "voiceclone": voiceclone, "voiceprofile": voiceprofile, "scenetts": scenetts, "multisourceresearch": research_cmd,
              "animationepisodes": episodes, "status": status, "cancel": cancel, "retry": retry, "health": health,
              "effects": effects, "commentstatus": commentstatus, "studio": studio_, "duration": duration,
              "platform": setter("platform", list(config.PLATFORMS)), "mode": setter("mode", ["draft", "voice", "full"]),
              "srt": setter("srt", ["on", "off", "en", "my", "both"])}
    for k, f in simple.items():
        H(CommandHandler(k, f))
    for k in ("create", "recapvideo", "recapstudio", "render"):
        H(CommandHandler(k, cmd("full" if k != "create" else "mode")))
    H(CommandHandler("draft", cmd("script")))
    H(CommandHandler("aiscript", cmd("script")))
    H(CommandHandler("voiceover", cmd("voice")))
    H(CommandHandler("draft3", cmd("script", multi=True)))
    H(CommandHandler("voiceover3", cmd("voice", multi=True)))
    H(CommandHandler("auto", cmd("full", multi=True)))
    H(MessageHandler((filters.VOICE | filters.AUDIO | filters.Document.AUDIO) & filters.CaptionRegex(r"^/voiceprofile"), handle_audio))
    return app


async def serve():
    app = build()
    port = int(os.getenv("PORT", "10000"))
    base = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL", "")
    secret = os.getenv("WEBHOOK_SECRET", "nexora")
    routes = web.RouteTableDef()

    @routes.get("/health")
    async def _h(_):
        return web.json_response({"ok": True})

    @routes.post("/tg/{s}")
    async def _w(req):
        if req.match_info["s"] != secret:
            return web.Response(status=403)
        await app.update_queue.put(Update.de_json(await req.json(), app.bot))
        return web.Response(text="ok")

    async with app:
        await app.start()
        if base:  # webhook: Render Free wakes on incoming request
            await app.bot.set_webhook(f"{base.rstrip('/')}/tg/{secret}", drop_pending_updates=False)
        else:
            await app.bot.delete_webhook()
            await app.updater.start_polling()
        wa = web.Application()
        wa.add_routes(routes)
        try:  # NEXORA Studio website + automation engine; the Telegram bot keeps working even if it cannot start
            from .studio import api as studio_api
            studio_api.mount(wa)
        except Exception as e:  # pragma: no cover - defensive
            print("studio disabled:", repr(e))
        runner = web.AppRunner(wa)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()
        print("bot up, port", port, "webhook" if base else "polling")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(serve())
