# NEXORA Myanmar Recap Bot - Starter v1

## Included
- Telegram bot polling
- `/start`, `/status`, `/create`, `/help`
- OpenAI-powered Burmese recap outline generator
- Render background worker blueprint
- Safe placeholders for video and publishing integrations

## Not included yet
- Grok API calls (XAI key is reserved for the next integration)
- Text-to-speech / FFmpeg rendering
- daily five-video queue and scheduler
- TikTok, Facebook, YouTube upload integrations
- persistent database / storage

Do not describe this starter as a complete automatic video factory.

## Deploy to Render
1. Upload this project to a private GitHub repository.
2. In Render, choose **New + > Blueprint** and connect that repository.
3. Render reads `render.yaml`. Create the worker.
4. In the worker's Environment settings, add:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `XAI_API_KEY` (not used until Grok integration is added)
5. Deploy and inspect the logs for `Starting NEXORA Telegram bot polling`.
6. Open your Telegram bot and send `/start`, then `/status`.

## Important
- Never paste tokens or API keys into Telegram chats, GitHub, or this conversation.
- Use only authorized accounts and platform APIs.
- Movie/series recap scripts must be original commentary based on lawful source material.
  Do not copy scripts, dialogue, or use unlicensed movie footage.
- Keep a human approval step before publishing.
- Platform upload eligibility, duration limits, and API permissions vary by account and platform.
