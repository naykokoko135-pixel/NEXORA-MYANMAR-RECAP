# NEXORA Myanmar Recap Bot — Free Template Build

A free Telegram bot for Burmese recap-writing worksheets and English subtitle SRT export.

## Commands
- `/start`, `/status`, `/help`
- `/create <topic>` — create a recap worksheet using the selected presets
- `/platform youtube|tiktok|facebook` — select the publishing platform
- `/duration 1-3|3-5|5-7|8-10|12-15` — choose a target duration in minutes
- `/settings` — show the current user's selections
- `/mode free|ai` — choose a mode label; AI provider is not connected
- `/srt` — convert timestamped English subtitle lines into an SRT file

Defaults are YouTube and 5–7 minutes. Platform and duration selections are stored in Telegram's per-user session data and may reset when the service restarts.

## Important limitations
- This is a writing worksheet, not automatic factual movie research or AI plot generation.
- English subtitles must be translated and checked by the user; SRT export does not translate.
- No video rendering, text-to-speech, scheduled queue, or automatic social publishing.
- The AI mode does not call an AI service and does not trigger paid fallback.
- Free hosting may sleep or restart; per-user session selections are not permanent storage.

## Deploy
1. Connect the repository to Render using **New + > Blueprint**.
2. Select the Free web service plan.
3. Add `TELEGRAM_BOT_TOKEN` in Render Environment.
4. Let the Blueprint generate `TELEGRAM_WEBHOOK_SECRET`.
5. Deploy and check the service URL and Telegram `/status`.

## Safe use
- Never put bot tokens or secrets in GitHub, chat messages, or screenshots.
- Use footage, images, music, and source material that you own, have permission to use, or are licensed to use.
- Write original commentary and verify movie facts before publishing.
- Keep a human review step before uploading.
