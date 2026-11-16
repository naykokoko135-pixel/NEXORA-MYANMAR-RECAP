# NEXORA Myanmar Recap Bot — Free Template Build

A free Telegram bot for Burmese recap-writing worksheets and English subtitle SRT export.

## Commands
- `/start`, `/status`, `/help`
- `/create <topic>` — create a recap worksheet using the selected presets
- `/research <movie title>` — create a source-tracking research worksheet before writing
- `/auto <movie title>` — search public Wikipedia article summaries and source links without an API key
- `/draft <movie title>` followed by a new line of your checked research notes — create a chapter-by-chapter draft worksheet using only those notes
- `/platform youtube|tiktok|facebook` — select the publishing platform
- `/duration <minutes>` — choose a duration valid for the selected platform
- `/settings` — show the current user's selections
- `/mode free|ai` — choose a mode label; AI provider is not connected
- `/srt` — convert timestamped English subtitle lines into an SRT file

## Platform duration presets
- YouTube: `8-10`, `12-15`, `15-20`, `20-30`, `30-45`, `45-60` minutes. Default: `15-20`.
- TikTok: `1-3`, `3-5` minutes. Default: `1-3`.
- Facebook: `3-5`, `5-7`, `8-10`, `10-15` minutes. Default: `5-7`.

YouTube long-form worksheets include chapter-based story development, character/background prompts, plot progression, turning points, climax, ending, and review. Duration presets guide the outline; they do not automatically write a timed or fact-checked script. Platform and duration selections are stored in Telegram's per-user session data and may reset when the service restarts.

## Movie research workflow
Use `/research <movie title>` to record release details, plot checkpoints, uncertain facts, and two source references. This command creates an offline worksheet only; it does not browse the web, verify sources, or generate factual plot summaries. Review your notes against reliable sources before using them in a recap.

## Automatic source discovery
Use `/auto Avatar` to search English Wikipedia for up to three relevant article summaries and source links. The lookup uses the public MediaWiki API and requires no API key or paid AI service. Wikipedia is community-edited, results may be incomplete or unrelated, and this feature does not verify facts against the movie or official sources. Treat results as research leads and cross-check them before writing.

## Research notes to recap draft
Use `/draft Avatar` and put your checked notes on the following lines in the same Telegram message. The bot preserves those notes and organizes prompts into chapters for the selected platform and duration. It does not write a finished factual narrative, independently verify notes, browse the web, or invent missing plot details. Keep source references with your notes and review the result before publishing.

## Important limitations
- `/auto` automates initial public-source discovery only; it does not create a complete verified plot summary or finished recap script.
- This is not a connection to the ChatGPT conversation or an AI writing provider.
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
