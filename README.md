# NEXORA Myanmar Recap Bot — Free Template Build

A free Telegram bot for Burmese recap-writing worksheets and English subtitle SRT export.

## Commands
- `/start`, `/status`, `/chatid`, `/help`
- `/create <topic>` — create a recap worksheet using the selected presets
- `/research <movie title>` — create a source-tracking research worksheet before writing
- `/auto <movie title>` — search public Wikipedia article summaries and source links without an API key
- `/draft <movie title>` followed by a new line of your checked research notes — create a chapter-by-chapter draft worksheet
- `/draft3 <movie title>` — create three YouTube planning worksheets using the latest matching `/auto` result, or supply checked notes on following lines
- `/voiceover <movie title>` followed by checked notes — export one combined Burmese voice-over draft as a `.txt` file\n- `/voiceover3 <movie title>` followed by checked notes — export three separate part files as `.txt` downloads
- `/platform youtube|tiktok|facebook` — select the publishing platform
- `/duration <minutes>` — choose a duration valid for the selected platform
- `/settings` — show the current user's selections
- `/mode free|ai` — choose a mode label; AI provider is not connected
- `/srt` — convert timestamped English subtitle lines into an SRT file

## Three-part YouTube worksheets
Use `/draft3 <movie title>` and put your checked research notes on the following lines in the same Telegram message. NEXORA creates three distinct planning worksheets:
1. Part 1 — introduction, setting, and main characters
2. Part 2 — central problem, conflict, and turning points
3. Part 3 — climax, ending, and original commentary

The selected YouTube duration is divided approximately across the three parts. These are editable planning worksheets, not three finished scripts or videos. The bot only uses the notes supplied by the creator; it does not invent missing plot facts or independently verify them. Check all notes against the film and reliable sources before publishing.

## Platform duration presets
- YouTube: `8-10`, `12-15`, `15-20`, `20-30`, `30-45`, `45-60` minutes. Default: `15-20`.
- TikTok: `1-3`, `3-5` minutes. Default: `1-3`.
- Facebook: `3-5`, `5-7`, `8-10`, `10-15` minutes. Default: `5-7`.

YouTube long-form worksheets include chapter-based story development, character/background prompts, plot progression, turning points, climax, ending, and review. Duration presets guide the outline; they do not automatically write a timed or fact-checked script. Platform and duration selections are stored in Telegram's per-user session data and may reset when the service restarts.

## Movie research workflow
Use `/research <movie title>` to record release details, plot checkpoints, uncertain facts, and two source references. This command creates an offline worksheet only; it does not browse the web, verify sources, or generate factual plot summaries. Review your notes against reliable sources before using them in a recap.

## Automatic source discovery
Use `/auto Avatar` to search English Wikipedia for up to three article summaries and source links. The lookup prioritizes a page whose title matches the requested movie name, then labels other matches as related results. The lookup uses the public MediaWiki API and requires no API key or paid AI service. Wikipedia is community-edited, results may be incomplete or unrelated, and this feature does not verify facts against the movie or official sources. Treat results as research leads and cross-check them before writing.

## Research notes to recap draft
Use `/draft Avatar` and put your checked notes on the following lines in the same Telegram message. The bot preserves those notes and organizes prompts into chapters for the selected platform and duration. It does not write a finished factual narrative, independently verify notes, browse the web, or invent missing plot details. Keep source references with your notes and review the result before publishing.

## Auto research to three-part draft

1. Send `/auto Avatar` to find up to three public Wikipedia article leads.
2. NEXORA temporarily keeps that result in the current Telegram user session.
3. Send `/draft3 Avatar` (same movie title) to place the saved research result into the three YouTube worksheets.
4. You can still send `/draft3 Avatar` followed by your own checked notes; those notes take priority over the saved result.

The saved result is matched by movie title and is only kept in the bot's in-memory Telegram session. It can be lost if the service restarts or the session is reset. A no-results lookup is not saved. Wikipedia excerpts and related search results are research leads, not verified plot facts; review the links and confirm details against the film and reliable sources before publishing. This feature does not connect ChatGPT or generate a finished recap script.


## Voice-over draft export

Send `/voiceover Avatar` and put at least six film-checked fact lines on the following lines. NEXORA rejects sparse notes and obvious placeholders instead of exporting an almost-empty draft. It divides the supplied notes, in their original order, into three balanced sections: Part 1 (setting/characters), Part 2 (conflict/turning points), and Part 3 (climax/ending). It adds generic Burmese transitions but preserves creator notes as supplied.

Example:

```text
/voiceover Avatar
[At least six checked facts, one per line]
[Keep them in story order and include source references]
```

This remains a deterministic free formatter, not an AI writer, translator, or fact-checker. It does not invent missing plot events or guarantee a 15–20 minute runtime. Wikipedia search snippets alone are not enough; review facts against the film and reliable sources, and add original commentary before recording.

For three separate downloads, use `/voiceover3 Avatar` as the first line and put checked facts on new lines in story order. Do not paste the complete `/auto` result as if it were a script: search headings, related results, and source links are not plot facts, and short Wikipedia excerpts alone will be rejected if fewer than six usable fact lines remain.

## Daily automatic research (5:00 AM Thailand time)
The `.github/workflows/daily-auto.yml` workflow runs daily at 22:00 UTC (05:00 Asia/Bangkok on the following local date). It chooses one title per day from a built-in rotation, runs the free Wikipedia source lookup, and sends the research leads plus a three-part YouTube planning structure to the configured Telegram chat. The three parts are planning sections, not three finished scripts or videos.

To enable delivery:
1. In Telegram, open your NEXORA bot and send `/chatid`. Copy the numeric chat ID shown.
2. In GitHub, open **Settings > Secrets and variables > Actions > New repository secret**.
3. Add `TELEGRAM_BOT_TOKEN` (the current bot token) and `TELEGRAM_CHAT_ID` (the chat ID from `/chatid`).
4. In **Actions**, enable workflows if GitHub asks, then use **Daily NEXORA Auto Research > Run workflow** once to test. The scheduled run is daily at 05:00 Thailand time.
5. Do not paste tokens into chat, code, commits, or screenshots. If a token was exposed, revoke it in BotFather and update both Render and GitHub secrets.

GitHub's scheduled workflow can start a little later than the exact minute. The bot's Render Free web service does not need to stay awake for the GitHub Actions job.

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


## Three separate voice-over files
Send `/voiceover3 <movie title>` followed by at least six creator-checked fact lines. NEXORA exports Part 1, Part 2, and Part 3 as three separate UTF-8 text downloads. The original note order and wording are preserved, with brief generic transitions. This is still a formatter—not an AI scriptwriter, translator, or fact-checker—and it does not guarantee a target runtime.
