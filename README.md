# NEXORA Myanmar Recap Bot (Free-tier starter)

A Telegram bot that creates original Burmese recap/commentary scripts with the Gemini API free tier, subject to Google's model availability and quota.

## Features
- Telegram commands: `/start`, `/status`, `/create <topic>`, `/help`
- Burmese recap script outline generation
- Telegram webhook (suitable for a Render Free Web Service)
- Health endpoint at `/health`

## Not included
- Automatic video editing/rendering or text-to-speech
- Daily five-video queue or persistent job database
- Automatic publishing to YouTube, TikTok, or Facebook
- Licensed film/video footage

## Free-tier deployment
1. Use Render **New + > Blueprint** and connect this repository.
2. Select the free web service plan if prompted.
3. Add the required environment values in Render:
   - `TELEGRAM_BOT_TOKEN`: your Telegram bot token
   - `GEMINI_API_KEY`: your Gemini API key
   - `TELEGRAM_WEBHOOK_SECRET`: generate a long random value using letters, numbers, underscore, and hyphen
   - `GEMINI_MODEL`: defaults to `gemini-3.8-flash`
4. Deploy. Render provides `RENDER_EXTERNAL_URL` to web services; the bot registers its Telegram webhook at startup.
5. Open the Render service URL and confirm it returns an online status.
6. In Telegram, send `/start`, then `/status`, then try `/create <topic>`.

## Important free-plan limits
- Gemini's free tier has model-specific quotas and availability limits. Check the active limits in Google AI Studio before use.
- Render Free web services spin down after 15 minutes without inbound traffic and may take about a minute to wake up. This is not an always-on production bot.
- Render Free services have ephemeral local storage; do not rely on local files for permanent storage.
- Free-tier provider policies and quotas can change.

## Privacy, security, and copyright
- Never put Telegram tokens or API keys in GitHub, chat messages, or screenshots.
- Store secrets only in Render Environment settings.
- Google states free-tier content may be used to improve its products; do not send private or sensitive material.
- Use only source material you own, have permission to use, or that is public domain. Generate original commentary; do not copy dialogue, scripts, or another creator's recap.
- Review every script and obtain rights/permission for any footage before publishing.
- This starter generates text only; it does not automatically publish videos.
