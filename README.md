# NEXORA Myanmar Recap Bot — Free Template Build

A free Telegram bot that creates a Burmese recap outline template without requiring any paid or external AI API.

## Features
- Telegram commands: `/start`, `/status`, `/create <topic>`, `/help`
- Burmese recap outline template with intro, topic summary, analysis, conclusion, and CTA
- Telegram webhook and FastAPI health endpoint
- No Grok, Gemini, OpenAI, or other AI API key required

## Not included
- AI-generated plot summaries (the bot does not call an AI API)
- Text-to-speech or automatic video rendering
- Daily five-video queue or persistent storage
- Automatic publishing to YouTube, TikTok, or Facebook

## Deploy free on Render
1. Connect this repository to Render using **New + > Blueprint**.
2. Choose the Free web service plan.
3. Add `TELEGRAM_BOT_TOKEN` in Render Environment.
4. Render Blueprint generates `TELEGRAM_WEBHOOK_SECRET` automatically.
5. Deploy. Render supplies `RENDER_EXTERNAL_URL`; the bot registers its webhook at startup.
6. Open the service URL and check that it returns an online status.
7. In Telegram, send `/start`, `/status`, then `/create <topic>`.

## Free-plan limitations
- Render Free web services sleep after 15 minutes without inbound traffic and may take about a minute to wake up.
- Free services have ephemeral local storage; do not rely on local files for permanent storage.
- Telegram bot API use does not require an AI API subscription, but the hosting provider's free limits still apply.

## Safe and lawful use
- Never put your Telegram bot token in GitHub, chat messages, or screenshots.
- The bot does not need an AI API key.
- Use source material you own, have permission to use, or that is public domain.
- Write original commentary; do not copy scripts, dialogue, or another creator's recap.
- Review content and obtain permission for footage before publishing.
- Keep a human review step before uploading any content.
