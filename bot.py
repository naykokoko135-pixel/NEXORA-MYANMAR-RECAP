import asyncio
import base64
import binascii
import time
import hmac
from io import BytesIO
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from telegram import InputFile, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from srt_builder import build_srt
from research_builder import generate_research_worksheet
from draft_builder import generate_draft_worksheet, generate_three_part_draft_worksheets
from auto_research import search_movie_sources, ResearchLookupError
from research_draft import matching_cached_research
from voiceover_builder import generate_voiceover_draft, generate_voiceover_part_files
from video_renderer import render_slideshow, VideoRenderError

from script_writer import (generate_recap_outline, generate_all_platform_plan, PLATFORM_NAMES, PLATFORM_DURATIONS, DURATION_PRESETS, DEFAULT_DURATIONS)
from error_reporter import report_error_to_github

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("nexora")

# HTTPX logs full Telegram API URLs at INFO level; those URLs contain the bot token.
# Keep request URLs out of Render logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")
telegram_app: Application | None = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "မင်္ဂလာပါ။ NEXORA Myanmar Recap Bot ပါ။\n\n"
            "/status - စနစ်အခြေအနေ\n"
            "/chatid - Daily Auto ပို့မည့် Chat ID ကြည့်ရန်\n"
            "/create <ခေါင်းစဉ်> - Free Recap template\n"
            "/research <ဇာတ်ကားအမည်> - Source စစ်ဆေးရန် worksheet\n"
            "/auto <ဇာတ်ကားအမည်> - အခမဲ့ ရင်းမြစ်ရှာရန်\n"
            "ပြီးနောက် /draft3 <ဇာတ်ကားအမည်> - ရှာထားသော Notes ကို အလိုအလျောက်သုံးရန်\n"
            "/draft <ဇာတ်ကားအမည်> - Research Notes မှ Draft worksheet\n"
            "/draft3 <ဇာတ်ကားအမည်> - YouTube သုံးပိုင်း Draft worksheets\n"
            "/allplatforms <အမည်> - YouTube/Facebook/TikTok အပိုင်းနှင့် ကြာချိန်ခွဲပြရန်\n"
            "/voiceover <ဇာတ်ကားအမည်> - Notes မှ Voice-over မူကြမ်းဖိုင်ထုတ်ရန်\n"
            "/voiceover3 <ဇာတ်ကားအမည်> - Notes မှ Voice-over ဖိုင် ၃ ဖိုင်ထုတ်ရန်\n"
            "/render - ပုံများ + အသံဖိုင်မှ MP4 ထုတ်ရန်\n"
            "/mode free|ai - Mode ရွေးရန်\n"
            "/srt - English စာတန်းထိုး SRT ဖိုင်ထုတ်ရန်\n"
            "/platform youtube|tiktok|facebook - Platform ရွေးရန်\n"
            "/duration <ကြာချိန်> - Platform အလိုက် ကြာချိန်ရွေးရန်\n"
            "YouTube: 8-10, 12-15, 15-20, 20-30, 30-45, 45-60 မိနစ်\n"
            "/settings - လက်ရှိရွေးချယ်မှုကြည့်ရန်\n"
            "/help - အကူအညီ"
        )


async def chatid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current Telegram chat ID for daily delivery setup."""
    if not update.effective_chat or not update.message:
        return
    await update.message.reply_text(
        "နေ့စဉ် Auto ပို့ရန် Chat ID:\n"
        f"{update.effective_chat.id}\n\n"
        "ဒီနံပါတ်ကို GitHub Repository Settings > Secrets and variables > Actions "
        "တွင် TELEGRAM_CHAT_ID အဖြစ် သိမ်းပါ။ Token သို့မဟုတ် Chat ID ကို အများသိအောင် မမျှဝေပါနှင့်။"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "NEXORA Bot: အလုပ်လုပ်နေပါတယ်။\n"
            "AI API: မချိတ်ထားပါ (အခပေး API မသုံးပါ)\n"
            "လုပ်ဆောင်နိုင်မှု: Auto research + Worksheets + Voice-over TXT + SRT + Image/Audio MP4 render\n"
            "Daily Auto: GitHub Actions မှ မနက် ၅ နာရီ (ထိုင်းစံတော်ချိန်) Research ပို့နိုင်သည်။\n"
            "Social auto-upload: မပါဝင်သေးပါ။"
        )


async def research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("အသုံးပြုပုံ: /research ဇာတ်ကားအမည်")
        return
    worksheet = generate_research_worksheet(topic)
    for start_at in range(0, len(worksheet), 3900):
        await update.message.reply_text(worksheet[start_at:start_at + 3900])



async def auto_research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("အသုံးပြုပုံ: /auto Avatar")
        return
    await update.message.reply_text("အခမဲ့ အများပြည်သူသုံး ရင်းမြစ်ကို ရှာဖွေနေပါတယ်...")
    try:
        result = await asyncio.to_thread(search_movie_sources, topic)
    except ResearchLookupError as exc:
        await update.message.reply_text(f"ရှာဖွေမှု မအောင်မြင်ပါ: {exc}")
        return
    if "ကိုက်ညီသော Wikipedia ဆောင်းပါး မတွေ့ပါ" not in result:
        context.user_data["last_auto_research_title"] = topic
        context.user_data["last_auto_research_result"] = result
        await update.message.reply_text(
            "Research ရလဒ်ကို ဒီ Telegram session အတွက် သိမ်းထားပါပြီ။ "
            "အခု /draft3 " + topic + " လို့ပို့ပြီး Worksheet သုံးပိုင်းထုတ်နိုင်ပါတယ်။"
        )
    for start_at in range(0, len(result), 3900):
        await update.message.reply_text(result[start_at:start_at + 3900])


async def allplatforms_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send an explicit three-part duration plan for all supported platforms."""
    if not update.message:
        return
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("အသုံးပြုပုံ: /allplatforms Anime အမည်")
        return
    plan = generate_all_platform_plan(topic)
    for start_at in range(0, len(plan), 3900):
        await update.message.reply_text(plan[start_at:start_at + 3900])


async def draft_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    first_line, separator, notes = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    topic = parts[1].strip() if len(parts) > 1 else ""
    if not topic or not separator or not notes.strip():
        await update.message.reply_text(
            "အသုံးပြုပုံ:\n/draft Avatar\nပြီးနောက် စာကြောင်းအသစ်မှ စစ်ဆေးထားသော Research Notes များ ထည့်ပါ။"
        )
        return
    platform = context.user_data.get("platform", "youtube")
    duration = context.user_data.get("duration", DEFAULT_DURATIONS[platform])
    try:
        worksheet = generate_draft_worksheet(topic, notes, platform=platform, duration=duration)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    for start_at in range(0, len(worksheet), 3900):
        await update.message.reply_text(worksheet[start_at:start_at + 3900])


async def draft3_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Build three separate YouTube planning worksheets from creator-checked notes."""
    if not update.message or not update.message.text:
        return
    first_line, separator, notes = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    topic = parts[1].strip() if len(parts) > 1 else ""
    if not topic:
        await update.message.reply_text("အသုံးပြုပုံ: /draft3 Avatar")
        return
    if not (separator and notes.strip()):
        notes = matching_cached_research(
            topic,
            context.user_data.get("last_auto_research_title", ""),
            context.user_data.get("last_auto_research_result", ""),
        )
        if not notes:
            await update.message.reply_text(
                "ဒီဇာတ်ကားအတွက် Auto Research မတွေ့သေးပါ။ အရင် /auto Avatar ပို့ပါ။ "
                "ပြီးရင် /draft3 Avatar လို့ ပို့ပါ။ သို့မဟုတ် /draft3 နောက်တစ်ကြောင်းမှာ "
                "စစ်ဆေးထားသော Research Notes ကို တိုက်ရိုက်ထည့်နိုင်ပါတယ်။"
            )
            return
        await update.message.reply_text("သိမ်းထားသော Auto Research ကို Draft ထဲ ထည့်နေပါတယ်...")
    duration = context.user_data.get("duration", DEFAULT_DURATIONS["youtube"])
    try:
        worksheet = generate_three_part_draft_worksheets(topic, notes, duration=duration)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    for start_at in range(0, len(worksheet), 3900):
        await update.message.reply_text(worksheet[start_at:start_at + 3900])


async def voiceover_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Format creator-checked notes as a downloadable Burmese voice-over draft."""
    if not update.message or not update.message.text:
        return
    first_line, separator, notes = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    topic = parts[1].strip() if len(parts) > 1 else ""
    if not topic or not separator or not notes.strip():
        await update.message.reply_text(
            "အသုံးပြုပုံ:\n/voiceover Avatar\n"
            "ပြီးနောက် ဇာတ်ကားနဲ့ ပြန်စစ်ထားတဲ့ ဖြစ်ရပ်များကို စာကြောင်းတစ်ကြောင်းစီ ထည့်ပါ။"
        )
        return
    try:
        draft = generate_voiceover_draft(topic, notes)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    file_obj = BytesIO(draft.encode("utf-8-sig"))
    file_obj.name = "nexora_voiceover_draft.txt"
    await update.message.reply_document(
        document=InputFile(file_obj, filename=file_obj.name),
        caption=(
            "Voice-over မူကြမ်းဖိုင်ပါ။ သင်ပေးထားသော Notes ကိုသာ စီစဉ်ထားပြီး "
            "AI ရေးသားခြင်း သို့မဟုတ် Fact-check လုပ်ခြင်း မဟုတ်ပါ။"
        ),
    )


async def voiceover3_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export the three voice-over sections as separate downloadable text files."""
    if not update.message or not update.message.text:
        return
    first_line, separator, notes = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    topic = parts[1].strip() if len(parts) > 1 else ""
    if not topic:
        await update.message.reply_text("အသုံးပြုပုံ: /voiceover3 Avatar")
        return
    if not (separator and notes.strip()):
        context.user_data["pending_voiceover"] = {"title": topic, "parts": 3}
        await update.message.reply_text(
            f"{topic} အတွက် စစ်ဆေးထားသော Notes အနည်းဆုံး ၆ ကြောင်းကို နောက်မက်ဆေ့ချ်တစ်ခုဖြင့် ပို့ပါ။\n"
            "တစ်ကြောင်းစီရေးပါ။ မလုပ်တော့ပါက /cancel ပို့နိုင်ပါတယ်။"
        )
        return
    try:
        drafts = generate_voiceover_part_files(topic, notes)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    for index, draft in enumerate(drafts, start=1):
        file_obj = BytesIO(draft.encode("utf-8-sig"))
        file_obj.name = f"nexora_{topic.replace(' ', '_')}_part_{index}.txt"
        await update.message.reply_document(
            document=InputFile(file_obj, filename=file_obj.name),
            caption=f"🎙️ {topic} — Part {index}/3"
        )


async def cancel_voiceover_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    pending = context.user_data.pop("pending_voiceover", None)
    if pending:
        await update.message.reply_text("Voice-over Notes စောင့်ဆိုင်းမှုကို ပယ်ဖျက်ပြီးပါပြီ။")
    else:
        await update.message.reply_text("ပယ်ဖျက်ရန် စောင့်နေသော Voice-over မရှိပါ။")


async def voiceover_notes_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    pending = context.user_data.get("pending_voiceover")
    if not pending:
        return
    title = pending.get("title", "")
    notes = update.message.text.strip()
    try:
        drafts = generate_voiceover_part_files(title, notes)
    except ValueError as exc:
        await update.message.reply_text(f"{exc}\nNotes ကို ပြန်စစ်ပြီး ထပ်ပို့ပါ။ မလုပ်တော့ပါက /cancel ပို့ပါ။")
        return
    for index, draft in enumerate(drafts, start=1):
        file_obj = BytesIO(draft.encode("utf-8-sig"))
        file_obj.name = f"nexora_{title.replace(' ', '_')}_part_{index}.txt"
        await update.message.reply_document(document=InputFile(file_obj, filename=file_obj.name), caption=f"🎙️ {title} — Part {index}/3")
    context.user_data.pop("pending_voiceover", None)



async def render_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    action = context.args[0].lower() if context.args else "start"
    if action == "cancel":
        context.user_data.pop("video_render", None)
        await update.message.reply_text("Video ပြင်ဆင်မှုကို ပယ်ဖျက်ပြီးပါပြီ။")
        return
    if action == "finish":
        session = context.user_data.get("video_render")
        if not session or not session.get("images") or not session.get("audio"):
            await update.message.reply_text("ပုံအနည်းဆုံး ၁ ပုံနဲ့ အသံဖိုင် ၁ ဖိုင် လိုပါတယ်။ /render ဖြင့် ပြန်စပါ။")
            return
        await update.message.reply_text("MP4 ထုတ်လုပ်နေပါတယ်။ ခဏစောင့်ပါ...")
        import tempfile
        try:
            with tempfile.TemporaryDirectory(prefix="nexora_video_") as temp:
                output = os.path.join(temp, "nexora_video.mp4")
                await asyncio.to_thread(render_slideshow, session["images"], session["audio"], output)
                with open(output, "rb") as video_file:
                    await update.message.reply_video(
                        video=InputFile(video_file, filename="nexora_video.mp4"),
                        supports_streaming=True,
                        caption="NEXORA MP4 ပြီးပါပြီ။ အသုံးပြုခွင့်ရှိသော ပုံ/အသံများကိုသာ ထည့်သုံးပါ။",
                        read_timeout=120,
                        write_timeout=120,
                    )
        except VideoRenderError as exc:
            await update.message.reply_text(str(exc))
        except Exception:
            log.exception("Video render delivery failed")
            await update.message.reply_text("MP4 ပို့မရပါ။ ပိုသေးသောဖိုင်များဖြင့် ထပ်စမ်းပါ။")
        finally:
            context.user_data.pop("video_render", None)
        return
    context.user_data["video_render"] = {"images": [], "audio": None}
    await update.message.reply_text(
        "Video ဖန်တီးမှု စတင်ပါပြီ။\n"
        "၁) ပုံ JPG/PNG/WEBP အများဆုံး ၁၂ ပုံ ပို့ပါ။\n"
        "၂) Narration အသံ MP3/M4A/WAV/OGG တစ်ဖိုင် ပို့ပါ (၂၀ MB အောက်၊ ၁၀ မိနစ်အောက်)။\n"
        "၃) ပြီးရင် /render finish ပို့ပါ။ မလုပ်တော့ပါက /render cancel ပို့ပါ။\n"
        "ကိုယ်ပိုင် သို့မဟုတ် အသုံးပြုခွင့်ရှိသော ပုံ/အသံကိုသာ သုံးပါ။"
    )


async def video_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    session = context.user_data.get("video_render")
    if session is None:
        return
    message = update.message
    media_file = None
    filename = ""
    kind = ""
    if message.photo:
        media_file = await message.photo[-1].get_file()
        filename, kind = f"photo_{len(session['images']) + 1}.jpg", "image"
    elif message.audio:
        media_file = await message.audio.get_file()
        filename = message.audio.file_name or "narration.mp3"
        kind = "audio"
    elif message.voice:
        media_file = await message.voice.get_file()
        filename, kind = "narration.ogg", "audio"
    if media_file is None:
        return
    size = getattr(media_file, "file_size", 0) or 0
    limit = 20 * 1024 * 1024 if kind == "audio" else 8 * 1024 * 1024
    if size > limit:
        await message.reply_text("ဖိုင်အရွယ်အစား ကြီးနေပါတယ်။ ပိုသေးတဲ့ဖိုင်သုံးပါ။")
        return
    buffer = BytesIO()
    await media_file.download_to_memory(out=buffer)
    data = buffer.getvalue()
    if kind == "image":
        if len(session["images"]) >= 12:
            await message.reply_text("ပုံ ၁၂ ပုံ ပြည့်ပါပြီ။ /render finish ပို့ပါ။")
            return
        session["images"].append((filename, data))
        await message.reply_text(f"ပုံ {len(session['images'])}/12 လက်ခံပြီးပါပြီ။")
    else:
        if len(data) > 20 * 1024 * 1024:
            await message.reply_text("အသံဖိုင်သည် ၂၀ MB အောက် ဖြစ်ရပါမယ်။")
            return
        session["audio"] = (filename, data)
        await message.reply_text("Narration အသံဖိုင် လက်ခံပြီးပါပြီ။ /render finish ပို့နိုင်ပါပြီ။")


async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /create ဇာတ်ကားအမည် သို့မဟုတ် အကြောင်းအရာ"
        )
        return
    platform = context.user_data.get("platform", "youtube")
    duration = context.user_data.get("duration", DEFAULT_DURATIONS[platform])
    if duration not in PLATFORM_DURATIONS[platform]:
        duration = DEFAULT_DURATIONS[platform]
        context.user_data["duration"] = duration
    outline = generate_recap_outline(topic, platform=platform, duration=duration)
    for start_at in range(0, len(outline), 3900):
        await update.message.reply_text(outline[start_at:start_at + 3900])



async def platform_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    choice = context.args[0].lower() if context.args else ""
    if choice not in PLATFORM_NAMES:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /platform youtube | tiktok | facebook"
        )
        return
    context.user_data["platform"] = choice
    current = context.user_data.get("duration")
    if current not in PLATFORM_DURATIONS[choice]:
        context.user_data["duration"] = DEFAULT_DURATIONS[choice]
    options = ", ".join(PLATFORM_DURATIONS[choice])
    await update.message.reply_text(
        f"Platform ကို {PLATFORM_NAMES[choice]} အဖြစ် ရွေးပြီးပါပြီ။\n"
        f"ရနိုင်သောကြာချိန်: {options}\n"
        f"Default: {DEFAULT_DURATIONS[choice]} မိနစ်"
    )


async def duration_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    platform = context.user_data.get("platform", "youtube")
    choice = context.args[0] if context.args else ""
    if choice not in PLATFORM_DURATIONS[platform]:
        options = ", ".join(PLATFORM_DURATIONS[platform])
        await update.message.reply_text(
            f"အသုံးပြုပုံ: /duration 15-20\n{PLATFORM_NAMES[platform]} အတွက် ရနိုင်သောကြာချိန်: {options}"
        )
        return
    context.user_data["duration"] = choice
    await update.message.reply_text(
        f"ရည်မှန်းကြာချိန် {DURATION_PRESETS[choice]} မိနစ်ကို ရွေးပြီးပါပြီ။"
    )


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    platform = context.user_data.get("platform", "youtube")
    duration = context.user_data.get("duration", DEFAULT_DURATIONS[platform])
    await update.message.reply_text(
        f"လက်ရှိရွေးချယ်မှု\nPlatform: {PLATFORM_NAMES[platform]}\n"
        f"ကြာချိန်: {DURATION_PRESETS.get(duration, duration)} မိနစ်\n"
        "ပြောင်းရန် /platform နှင့် /duration ကို အသုံးပြုပါ။"
    )

async def mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    choice = context.args[0].lower() if context.args else ""
    if choice not in {"free", "ai"}:
        await update.message.reply_text("အသုံးပြုပုံ: /mode free သို့မဟုတ် /mode ai")
        return
    context.user_data["mode"] = choice
    if choice == "ai":
        await update.message.reply_text(
            "AI Mode ကို ရွေးထားပါတယ်။ လက်ရှိမှာ သတ်မှတ်ချက်နှင့်ကိုက်ညီသော AI ဝန်ဆောင်မှု မချိတ်ထားသေးပါ။ "
            "အခပေး API ကို အလိုအလျောက် မသုံးပါ။ /create ကို Free Builder ဖြင့် ဆက်လုပ်နိုင်ပါတယ်။"
        )
    else:
        await update.message.reply_text("Free Mode ဖွင့်ပြီးပါပြီ။ API key မလိုပါ။")


async def srt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    raw = update.message.text.partition("\n")[2].strip()
    if not raw:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /srt ပြီးနောက် စာကြောင်းတစ်ကြောင်းစီ ထည့်ပါ။\n"
            "00:00:00,000 --> 00:00:05,000 | Welcome to the story.\n"
            "00:00:05,000 --> 00:00:10,000 | The journey begins."
        )
        return
    try:
        srt_text = build_srt(raw)
    except ValueError as exc:
        await update.message.reply_text(f"စာတန်းထိုးပုံစံ မမှန်ပါ: {exc}")
        return
    file_obj = BytesIO(srt_text.encode("utf-8-sig"))
    file_obj.name = "nexora_english_subtitles.srt"
    await update.message.reply_document(
        document=InputFile(file_obj, filename=file_obj.name),
        caption="NEXORA English Subtitle SRT ဖိုင်"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "Commands:\n/start\n/status\n/create <topic>\n/mode free|ai\n/srt\n/platform youtube|tiktok|facebook\n/duration <minutes>\n/settings\n/help\n\n"
            "YouTube: 8-10, 12-15, 15-20, 20-30, 30-45, 45-60\n"
            "TikTok: 1-3, 3-5\nFacebook: 3-5, 5-7, 8-10, 10-15\n\n"
            "/auto သည် Wikipedia မှ source lead များရှာပေးသည်၊ အချက်အလက်ကို ကိုယ်တိုင်ပြန်စစ်ပါ။\n"
            "/draft သည် ပေးထားသော Research Notes ကို worksheet အဖြစ် စီစဉ်ပေးသည်။\n"
            "/draft3 သည် YouTube အတွက် သီးခြား worksheet သုံးခု ထုတ်ပေးသည်။\n"
            "/allplatforms သည် YouTube/Facebook/TikTok အတွက် အပိုင်းနှင့် ကြာချိန် သီးခြားခွဲပြသည်။\n"
            "/voiceover <အမည်> နှင့် /voiceover3 <အမည်> သည် သင်ပေးသော စစ်ဆေးပြီး Notes ကို TXT ဖိုင်အဖြစ် စီစဉ်ပေးသည်။\n"
            "Voice-over အတွက် ဇာတ်ကားနှင့် ပြန်စစ်ထားသော Notes အနည်းဆုံး ၆ ကြောင်း လိုအပ်သည်။\n"
            "အသုံးပြုပုံ: /voiceover3 Avatar ပြီးနောက် စာကြောင်းအသစ်မှ ဖြစ်ရပ်မှန် Notes များ ထည့်ပါ။\n"
            "Wikipedia /auto ရလဒ်တိုများကို တိုက်ရိုက်သုံးရန် မလုံလောက်ပါ။ Source link များကို ပြန်စစ်ပြီး ကိုယ်တိုင် Notes ရေးပါ။\n"
            "/auto Avatar ပြီးနောက် /draft3 Avatar ပို့လျှင် ရှာထားသော Notes ကို အလိုအလျောက် ထည့်ပေးသည်။\n"
            "/render ဖြင့် ပုံများနှင့် narration အသံမှ MP4 slideshow ထုတ်နိုင်သည်။ /render finish ဖြင့် ပြီးစီးစေပါ။\n"
            "Free Mode သည် API မလိုပါ။ AI Mode သည် provider မချိတ်ရသေးပါ။ "
            "/srt ဖြင့် timestamp ပါသော English စာသားမှ .srt ဖိုင်ထုတ်နိုင်သည်။"
        )


async def on_telegram_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    # Do not log exception text: request errors can contain credential-bearing URLs.
    error = context.error
    error_name = type(error).__name__ if error else "UnknownError"
    log.error("Telegram update handler failed (%s)", error_name)
    if error is not None:
        try:
            reported = await asyncio.to_thread(
                report_error_to_github,
                error,
                update_kind="telegram_update",
            )
            if reported:
                log.info("Privacy-safe error report created in GitHub Issues")
        except Exception:
            # Reporting must never cause another handler failure.
            log.warning("GitHub error reporting could not be completed")


@asynccontextmanager
async def lifespan(web_app: FastAPI):
    global telegram_app
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    if not WEBHOOK_SECRET:
        raise RuntimeError("TELEGRAM_WEBHOOK_SECRET is missing")
    if not PUBLIC_URL:
        raise RuntimeError("RENDER_EXTERNAL_URL is missing")

    telegram_app = Application.builder().token(TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("status", status))
    telegram_app.add_handler(CommandHandler("chatid", chatid_cmd))
    telegram_app.add_handler(CommandHandler("create", create))
    telegram_app.add_handler(CommandHandler("research", research_cmd))
    telegram_app.add_handler(CommandHandler("auto", auto_research_cmd))
    telegram_app.add_handler(CommandHandler("draft", draft_cmd))
    telegram_app.add_handler(CommandHandler("draft3", draft3_cmd))
    telegram_app.add_handler(CommandHandler("allplatforms", allplatforms_cmd))
    telegram_app.add_handler(CommandHandler("voiceover", voiceover_cmd))
    telegram_app.add_handler(CommandHandler("voiceover3", voiceover3_cmd))
    telegram_app.add_handler(CommandHandler("render", render_cmd))
    telegram_app.add_handler(MessageHandler(filters.PHOTO | filters.AUDIO | filters.VOICE, video_media_message))
    telegram_app.add_handler(CommandHandler("cancel", cancel_voiceover_cmd))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, voiceover_notes_message))
    telegram_app.add_handler(CommandHandler("mode", mode_cmd))
    telegram_app.add_handler(CommandHandler("srt", srt_cmd))
    telegram_app.add_handler(CommandHandler("platform", platform_cmd))
    telegram_app.add_handler(CommandHandler("duration", duration_cmd))
    telegram_app.add_handler(CommandHandler("settings", settings_cmd))
    telegram_app.add_handler(CommandHandler("help", help_cmd))
    telegram_app.add_error_handler(on_telegram_error, block=False)

    await telegram_app.initialize()
    await telegram_app.start()
    try:
        await telegram_app.bot.set_webhook(
            url=f"{PUBLIC_URL.rstrip('/')}/telegram-webhook",
            secret_token=WEBHOOK_SECRET,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
        )
        log.info("NEXORA Telegram webhook started")
        yield
    finally:
        # Keep the Telegram webhook registered when Render stops or sleeps the service.
        # Telegram can retry pending updates after the service starts again.
        await telegram_app.stop()
        await telegram_app.shutdown()
        telegram_app = None


web_app = FastAPI(title="NEXORA Myanmar Recap Bot", lifespan=lifespan)


@web_app.get("/")
async def home():
    return {"app": "NEXORA Myanmar Recap Bot", "status": "online"}


@web_app.get("/health")
async def health():
    return {"status": "ok", "telegram": telegram_app is not None}


@web_app.get("/chatgpt/bridge-health")
async def chatgpt_bridge_health():
    """Expose configuration presence only; never return secret values or chat IDs."""
    try:
        chat_id_configured = int(os.getenv("CHATGPT_BRIDGE_CHAT_ID", "")) > 0
    except ValueError:
        chat_id_configured = False
    return {
        "status": "ok",
        "telegram": telegram_app is not None,
        "bridge_api_key_configured": bool(os.getenv("CHATGPT_BRIDGE_API_KEY")),
        "bridge_chat_id_configured": chat_id_configured,
        "bridge_ready": bool(os.getenv("CHATGPT_BRIDGE_API_KEY")) and chat_id_configured and telegram_app is not None,
    }


@web_app.post("/telegram-webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if not WEBHOOK_SECRET or not hmac.compare_digest(
        x_telegram_bot_api_secret_token or "", WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=403, detail="Forbidden")
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Bot is starting")
    payload = await request.json()
    update = Update.de_json(payload, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return {"ok": True}


# Optional authenticated bridge for a Custom GPT Action. Configure both values in
# Render Environment; never commit either secret or put them in chat.
CHATGPT_BRIDGE_API_KEY = os.getenv("CHATGPT_BRIDGE_API_KEY")
CHATGPT_BRIDGE_CHAT_ID = os.getenv("CHATGPT_BRIDGE_CHAT_ID")
BRIDGE_ALLOWED_COMMANDS = {"status", "help", "auto", "create", "research", "draft3", "allplatforms", "voiceover3", "render"}


def _bridge_authorized(request: Request) -> bool:
    supplied = request.headers.get("x-nexora-bridge-key", "")
    return bool(CHATGPT_BRIDGE_API_KEY) and hmac.compare_digest(
        supplied, CHATGPT_BRIDGE_API_KEY
    )


@web_app.post("/chatgpt/command")
async def chatgpt_bridge_command(request: Request):
    """Run one allow-listed NEXORA bot command in the owner's configured private chat."""
    if not _bridge_authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not ready")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    command = str(payload.get("command", "")).strip().lower().lstrip("/")
    argument = str(payload.get("argument", "")).strip()
    if command not in BRIDGE_ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Command is not allowed")
    if len(argument) > 3500 or "\n" in argument or "\r" in argument:
        raise HTTPException(status_code=400, detail="Argument is too long or invalid")
    try:
        chat_id = int(CHATGPT_BRIDGE_CHAT_ID or "")
    except ValueError:
        raise HTTPException(status_code=503, detail="CHATGPT_BRIDGE_CHAT_ID is not configured")
    if chat_id <= 0:
        raise HTTPException(status_code=503, detail="Configure a private positive Telegram chat ID")
    text = "/" + command + ((" " + argument) if argument else "")
    synthetic_update = Update.de_json({
        "update_id": time.time_ns() % 2_000_000_000,
        "message": {
            "message_id": int(time.time()) % 2_000_000_000,
            "date": int(time.time()),
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "is_bot": False, "first_name": "NEXORA Bridge"},
            "text": text,
            "entities": [{"type": "bot_command", "offset": 0, "length": len("/" + command)}],
        },
    }, telegram_app.bot)
    await telegram_app.process_update(synthetic_update)
    return {"ok": True, "command": command, "delivered_to_telegram": True}


@web_app.post("/chatgpt/send-file")
async def chatgpt_bridge_send_file(request: Request):
    """Send a small base64-encoded creator-owned file to the configured private chat."""
    if not _bridge_authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not ready")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    filename = str(payload.get("filename", ""))
    encoded = payload.get("content_base64", "")
    allowed_suffixes = {".mp3", ".wav", ".ogg", ".jpg", ".jpeg", ".png", ".webp", ".mp4", ".txt", ".srt"}
    suffix = os.path.splitext(filename)[1].lower()
    if not filename or len(filename) > 100 or suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="Unsupported filename or file type")
    if not isinstance(encoded, str) or len(encoded) > 28_000_000:
        raise HTTPException(status_code=413, detail="File is too large")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid base64 file content")
    if not content or len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File must be between 1 byte and 20 MB")
    try:
        chat_id = int(CHATGPT_BRIDGE_CHAT_ID or "")
    except ValueError:
        raise HTTPException(status_code=503, detail="CHATGPT_BRIDGE_CHAT_ID is not configured")
    if chat_id <= 0:
        raise HTTPException(status_code=503, detail="Configure a private positive Telegram chat ID")
    file_obj = BytesIO(content)
    file_obj.name = os.path.basename(filename)
    await telegram_app.bot.send_document(
        chat_id=chat_id,
        document=InputFile(file_obj, filename=file_obj.name),
        caption="ဖိုင်ကို ChatGPT Bridge မှ ပို့ထားပါတယ်။ အသုံးပြုခွင့်ရှိသော မီဒီယာကိုသာ အသုံးပြုပါ။",
        read_timeout=60,
        write_timeout=60,
    )
    return {"ok": True, "filename": file_obj.name, "bytes_sent": len(content)}
