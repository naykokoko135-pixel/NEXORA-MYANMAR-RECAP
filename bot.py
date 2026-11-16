import hmac
from io import BytesIO
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from telegram import InputFile, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from srt_builder import build_srt
from research_builder import generate_research_worksheet

from script_writer import (generate_recap_outline, PLATFORM_NAMES, PLATFORM_DURATIONS, DURATION_PRESETS, DEFAULT_DURATIONS)

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
            "/create <ခေါင်းစဉ်> - Free Recap template\n"
            "/research <ဇာတ်ကားအမည်> - Source စစ်ဆေးရန် worksheet\n"
            "/mode free|ai - Mode ရွေးရန်\n"
            "/srt - English စာတန်းထိုး SRT ဖိုင်ထုတ်ရန်\n"
            "/platform youtube|tiktok|facebook - Platform ရွေးရန်\n"
            "/duration <ကြာချိန်> - Platform အလိုက် ကြာချိန်ရွေးရန်\n"
            "YouTube: 8-10, 12-15, 15-20, 20-30, 30-45, 45-60 မိနစ်\n"
            "/settings - လက်ရှိရွေးချယ်မှုကြည့်ရန်\n"
            "/help - အကူအညီ"
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "NEXORA Bot: အလုပ်လုပ်နေပါတယ်။\n"
            "AI API: မချိတ်ထားပါ (အခပေး API မသုံးပါ)\n"
            "လုပ်ဆောင်နိုင်မှု: Platform/Duration Presets + Free Recap template + SRT export\n"
            "Video rendering / scheduled queue / social auto-upload: မပါဝင်သေးပါ။"
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
            "Free Mode သည် API မလိုပါ။ AI Mode သည် provider မချိတ်ရသေးပါ။ "
            "/srt ဖြင့် timestamp ပါသော English စာသားမှ .srt ဖိုင်ထုတ်နိုင်သည်။"
        )


async def on_telegram_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    # Do not log exception text: request errors can contain credential-bearing URLs.
    error_name = type(context.error).__name__ if context.error else "UnknownError"
    log.error("Telegram update handler failed (%s)", error_name)


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
    telegram_app.add_handler(CommandHandler("create", create))
    telegram_app.add_handler(CommandHandler("research", research_cmd))
    telegram_app.add_handler(CommandHandler("mode", mode_cmd))
    telegram_app.add_handler(CommandHandler("srt", srt_cmd))
    telegram_app.add_handler(CommandHandler("platform", platform_cmd))
    telegram_app.add_handler(CommandHandler("duration", duration_cmd))
    telegram_app.add_handler(CommandHandler("settings", settings_cmd))
    telegram_app.add_handler(CommandHandler("help", help_cmd))
    telegram_app.add_error_handler(on_telegram_error)

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
