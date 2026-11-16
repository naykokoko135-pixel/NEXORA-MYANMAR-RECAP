# NEXORA Myanmar Recap Bot - Grok integration

## Included
- Telegram bot polling
- `/start`, `/status`, `/create`, `/help`
- Grok-powered Burmese recap commentary outline generator
- Render background worker blueprint
- Safe placeholders for video and publishing integrations

## Not included yet
- Text-to-speech / FFmpeg video rendering
- Daily five-video queue and scheduler
- TikTok, Facebook, YouTube upload integrations
- Persistent database / storage

Do not describe this build as a complete automatic video factory.

## Configure and deploy on Render
1. Connect this GitHub repository to Render using **New + > Blueprint**.
2. Render reads `render.yaml` and creates the background worker.
3. In the worker's Environment settings, add:
   - `TELEGRAM_BOT_TOKEN`: your Telegram bot token
   - `XAI_API_KEY`: your existing xAI API key
   - `XAI_MODEL`: defaults to `grok-4.7`; change only if your console shows a different enabled model
4. Deploy and inspect logs for `Starting NEXORA Telegram bot polling`.
5. In Telegram, send `/start`, then `/status`.
6. Test with `/create [topic]`.

## Important
- Never paste tokens or API keys into Telegram chats, GitHub, screenshots, or this conversation.
- Enter secrets only in Render's Environment settings.
- The xAI API is usage-billed; check the console's billing and available balance before making requests.
- Use only authorized accounts and lawful source material.
- Recap scripts must be original commentary. Do not copy scripts, dialogue, or use unlicensed footage.
- Keep a human approval step before publishing.
- Video rendering, scheduling, and social uploads are not implemented in this version.
