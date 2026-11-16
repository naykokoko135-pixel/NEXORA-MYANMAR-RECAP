import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from script_writer import generate_recap_outline

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
    grok_configured = bool(os.getenv("XAI_API_KEY"))
    model = os.getenv("XAI_MODEL", "grok-4.7")
    await update.message.reply_text(
        "NEXORA Bot: အလုပ်လုပ်နေပါတယ်။\n"
        f"Grok API key configured: {'Yes' if grok_configured else 'Not yet'}\n"
        f"Grok model: {model if grok_configured else 'မချိတ်ဆက်ရသေးပါ'}\n"
        "လက်ရှိလုပ်ဆောင်နိုင်မှု: Telegram commands + Grok recap outline\n"
        "Video rendering / scheduled queue / social publishing: မချိတ်ဆက်ရသေးပါ။"
    )


async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /create ဇာတ်ကား သို့မဟုတ် ဇာတ်လမ်းအမည်\n"
            "ခွင့်ပြုထားသော source/ကိုယ်ပိုင်အကြောင်းအရာကိုသာ အသုံးပြုပါ။"
        )
        return

    await update.message.reply_text("Grok နဲ့ အကြောင်းအရာကို စီစဉ်နေပါတယ်...")
    try:
        outline = await generate_recap_outline(topic)
        await update.message.reply_text(outline[:3900])
    except Exception:
        log.exception("Grok recap outline generation failed")
        await update.message.reply_text(
            "Grok Script service မရသေးပါ။ Render ရှိ XAI_API_KEY နှင့် "
            "XAI_MODEL configuration ကို စစ်ဆေးပါ။"
        )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n/start\n/status\n/create <topic>\n/help\n\n"
        "လက်ရှိ build သည် Telegram bot + Grok script-outline prototype ဖြစ်သည်။ "
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
