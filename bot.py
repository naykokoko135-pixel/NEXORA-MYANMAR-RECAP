import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("nexora")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")
telegram_app: Application | None = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "မင်္ဂလာပါ။ NEXORA Myanmar Recap Bot ပါ။\n\n"
        "/status - စနစ်အခြေအနေ\n"
        "/create <အကြောင်းအရာ> - မူရင်း Recap script ရေးရန်\n"
        "/help - အကူအညီ"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "NEXORA Bot: အလုပ်လုပ်နေပါတယ်။\n"
        f"Gemini API: {'ချိတ်ဆက်ရန် Key ရှိသည်' if GEMINI_API_KEY else 'မချိတ်ဆက်ရသေးပါ'}\n"
        f"Model: {GEMINI_MODEL}\n"
        "ဤ build သည် script outline ထုတ်ပေးနိုင်သည်။ Video rendering နှင့် "
        "YouTube/TikTok/Facebook auto-upload မပါဝင်သေးပါ။"
    )


async def generate_recap(topic: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing")

    prompt = f"""
သင်သည် မြန်မာဘာသာ Recap အယ်ဒီတာဖြစ်သည်။
အကြောင်းအရာ: {topic}

အသုံးပြုသူပေးထားသော သို့မဟုတ် အသုံးပြုခွင့်ရှိသော အချက်အလက်ကိုသာ အခြေခံပြီး
မူရင်း commentary ပါဝင်သော Recap script outline ကို မြန်မာဘာသာဖြင့် ရေးပါ။
- Spoiler warning ထည့်ပါ။
- Intro, အဓိကအကြောင်းအရာ, ဇာတ်ကောင်/အယူအဆသုံးသပ်ချက်,
  ကိုယ်ပိုင်အမြင်, conclusion နှင့် CTA ပါဝင်ပါ။
- မသိသော plot သို့မဟုတ် fact များကို မခန့်မှန်းပါနှင့်။ [VERIFY] ဟု မှတ်သားပါ။
- ဇာတ်ဝင်ခန်းတစ်ခန်းချင်းစီကို အသေးစိတ်ပြန်မရေးပါနှင့်။
- မူပိုင်ခွင့်ရှိသော dialogue၊ script၊ သို့မဟုတ် အခြားသူ၏ recap ကို မကူးယူပါနှင့်။
- မူရင်းရုပ်ရှင်/ဗီဒီယိုကို အစားထိုးနိုင်လောက်အောင် မပြန်လည်ဖော်ပြပါနှင့်။
- သဘာဝကျသော narration ပုံစံ၊ အပိုင်းခွဲခေါင်းစဉ်များနှင့် အချိန်ခန့်မှန်းချက် ထည့်ပါ။
"""
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text or "Script မရရှိပါ။ နောက်တစ်ကြိမ် ပြန်စမ်းကြည့်ပါ။"


async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /create ဇာတ်ကားအမည် သို့မဟုတ် အကြောင်းအရာ\n"
            "ပိုမိုတိကျစေရန် ကိုယ်ပိုင်အကျဉ်းချုပ်/အချက်အလက်များကို ထည့်ပေးပါ။"
        )
        return

    await update.message.reply_text("မူရင်း Recap script ကို ပြင်ဆင်နေပါတယ်...")
    try:
        script = await generate_recap(topic)
        # Telegram message limit is 4096 characters.
        chunks = [script[i:i + 3900] for i in range(0, len(script), 3900)]
        for chunk in chunks:
            await update.message.reply_text(chunk)
    except Exception:
        log.exception("Gemini recap generation failed")
        await update.message.reply_text(
            "Script မထုတ်နိုင်ပါ။ GEMINI_API_KEY၊ model name နှင့် free-tier quota ကို စစ်ဆေးပါ။"
        )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n/start\n/status\n/create <topic>\n/help\n\n"
        "မှတ်ချက်: Bot သည် မူရင်း Recap script/outline ကိုသာ ထုတ်ပေးသည်။ "
        "ဗီဒီယိုဖိုင်ဖန်တီးခြင်းနှင့် လူမှုကွန်ရက်သို့ အလိုအလျောက်တင်ခြင်း မပါဝင်သေးပါ။"
    )


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
    telegram_app.add_handler(CommandHandler("help", help_cmd))

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(
        url=f"{PUBLIC_URL.rstrip('/')}/telegram-webhook",
        secret_token=WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    log.info("NEXORA Telegram webhook started")
    try:
        yield
    finally:
        await telegram_app.bot.delete_webhook()
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
