import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from ai.script_writer import generate_recap_outline

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("nexora")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "မင်္ဂလာပါ။ NEXORA Myanmar Recap Bot ပါ။\n\n"
        "/status - စနစ်အခြေအနေ\n"
        "/create - Recap အကြမ်းဖျဉ်းတစ်ခု ပြင်ဆင်ရန်\n"
        "/help - အကူအညီ"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    configured = all(os.getenv(k) for k in ("OPENAI_API_KEY", "XAI_API_KEY"))
    await update.message.reply_text(
        "NEXORA Bot: အလုပ်လုပ်နေပါတယ်။\n"
        f"AI API keys configured: {'Yes' if configured else 'Not yet'}\n"
        "Video rendering / social publishing: နောက်အဆင့်တွင် ချိတ်ဆက်ရပါမည်။"
    )

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /create ဇာတ်ကား သို့မဟုတ် ဇာတ်လမ်းအမည်\n"
            "ခွင့်ပြုထားသော source/ကိုယ်ပိုင်အကြောင်းအရာကိုသာ အသုံးပြုပါ။"
        )
        return
    await update.message.reply_text("အကြောင်းအရာကို စီစဉ်နေပါတယ်...")
    try:
        outline = await generate_recap_outline(topic)
        await update.message.reply_text(outline[:3900])
    except Exception as exc:
        log.exception("Recap outline generation failed")
        await update.message.reply_text(
            "Script service မရသေးပါ။ API Key နှင့် configuration ကို စစ်ဆေးပါ။"
        )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n/start\n/status\n/create <topic>\n/help\n\n"
        "လက်ရှိ build သည် bot + script-outline prototype ဖြစ်သည်။ "
        "အလိုအလျောက် video ထုတ်လုပ်ခြင်းနှင့် တင်ခြင်းကို မချိတ်ဆက်ရသေးပါ။"
    )

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("create", create))
    app.add_handler(CommandHandler("help", help_cmd))
    log.info("Starting NEXORA Telegram bot polling")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
