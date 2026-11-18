# NEXORA Myanmar Recap Bot — Free Template Build

A free Telegram bot for Burmese recap-writing worksheets and English subtitle SRT export.

## Commands
- `/start`, `/status`, `/chatid`, `/help`
- `/create <topic>` — create a recap worksheet using the selected presets
- `/research <movie title>` — create a source-tracking research worksheet before writing
- `/auto <movie title>` — search public Wikipedia article summaries and source links without an API key
- `/draft <movie title>` followed by a new line of your checked research notes — create a chapter-by-chapter draft worksheet
- `/draft3 <movie title>` — create three YouTube planning worksheets using the latest matching `/auto` result, or supply checked notes on following lines
- `/allplatforms <title>` — show explicit three-part duration plans for YouTube, Facebook, and TikTok
- `/voiceover <movie title>` followed by checked notes — export one combined Burmese voice-over draft as a `.txt` file\n- `/voiceover3 <movie title>` followed by checked notes — export three separate part files as `.txt` downloads
- `/platform youtube|tiktok|facebook` — select the publishing platform
- `/duration <minutes>` — choose a duration valid for the selected platform
- `/settings` — show the current user's selections
- `/mode free|ai` — choose a mode label; AI provider is not connected
- `/srt` — convert timestamped subtitle lines into an SRT file\n- `/srtmy` — split a supplied Burmese narration script into estimated-time Burmese SRT captions\n- `/tts <preset>` — create a Burmese MP3 using a selected delivery-style preset
- `/voices` — list Burmese voice identities and delivery-style presets
- `/tts-local` followed by Burmese text on the next line — experimental local MyanmarTTS WAV (requires optional dependencies and explicit host enablement)
- `/ttssrt <preset>` — create an MP3 and word-boundary-timed Burmese SRT together
- `/voicedemo <preset>` — audition an existing Burmese Edge TTS delivery style
- `/tts_design <voice_name>` followed by Burmese text — create a fictional synthetic voice WAV (optional compatible host only)
- `/scenedesign` followed by `[ai:story_female]` scene headers and Burmese text — create separate fictional AI voice WAV files per scene (optional compatible GPU host only)

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

## Anime synopsis research with AniList

Use `/animesynopsis <Anime title>` to look up an exact-title Anime entry through the public AniList GraphQL API. NEXORA returns the title, format, year, episode count (when available), source link, and a short synopsis. No API key or paid AI provider is required.

AniList search results are not treated as exact matches unless the requested title matches an official title or listed synonym. Ambiguous and fuzzy matches are rejected. Indian-origin entries are excluded. AniList synopsis text is a series-level overview, not an episode-by-episode plot summary; it is shown only as a research lead and is not passed to the automatic MP4 recap renderer. It is not automatically translated into Burmese, so verify the facts and language before using it.

## Cartoon and Donghua series research

Use `/seriesresearch <title>` to request an exact-title TVmaze show match. NEXORA only displays the summary when TVmaze marks the entry with the Animation genre and rejects Indian-origin shows. The returned summary is a series-level overview, not an episode plot. TVmaze records are community-maintained; the command does not infer whether an animated work is 2D or 3D, and it does not create a recap video.

## Animated series episode research

Use `/animationepisodes <title>` to retrieve up to five short episode-summary excerpts from an exact TVmaze series match. The series must be tagged with the Animation genre and have a known non-Indian country. Each excerpt is capped at 240 characters and includes its TVmaze source link. This is episode-level research material, not a complete recap script, scene transcript, or studio-verified account. TVmaze data is community-maintained and must be checked before use.

## International movie plot research

Use `/movieplotresearch <title>` to require an exact Wikidata title match, exclude Indian-origin entries and entries with animation-related genres, then retrieve an explicitly labelled Plot/Synopsis section from the linked English Wikipedia article. The result is a research excerpt only. English Wikipedia is community-edited, a missing Plot section is rejected, and the command does not translate the text or create a recap MP4. Confirm the title is a live-action international movie and verify plot facts against reliable sources before use.

## Longer licensed recap video preview
After the MP4, NEXORA also sends `nexora_footage_attribution.txt` with the Commons file name, creator/artist, attribution text when supplied, license, usage terms, source page, and Wikidata source. Treat this as a checklist: verify the exact license version and creator details on the Commons page before publishing.
It also sends the narration as `nexora_recap_voiceover.mp3` and the standalone, UTF-8 Burmese captions as `nexora_recap_subtitles.srt`; the MP4 retains its embedded selectable subtitle track too.


Use `/recapvideo <exact title>` followed by an optional preset line and creator-written Burmese narration. NEXORA requires an exact Wikidata title record with known non-Indian country metadata, searches Wikimedia Commons, and proceeds only when a strong title metadata match has an allowed CC0/CC BY/CC BY-SA/Public Domain license. It then generates Burmese narration, word-aligned SRT, and an MP4 preview up to five minutes in the selected platform ratio.

Example:
```
/recapvideo Frieren: Beyond Journey's End
narrator
[ကိုယ်တိုင်ရေးပြီး Episode နှင့် ပြန်စစ်ထားသော narration]
```

The command rejects unknown country metadata and Indian-origin/co-production records. A Commons file-title match does not prove the clip depicts the correct episode or scene; inspect the finished MP4 manually and verify the license, attribution, and any Share-Alike obligations before publishing. The source footage may loop to cover narration duration. This is a preview workflow, not an automatically researched full episode recap, and it does not infer 3D animation from a generic Animation genre.

## Recap voice + synchronized subtitles

Use `/recapvoice [preset]` followed by creator-written Burmese narration in the same Telegram message. If no preset is supplied, NEXORA uses `narrator`. It generates one MP3 and one SRT using Edge TTS word-boundary timing. Available presets are listed by `/voices`; presets reuse the two currently available Burmese neural voices (Nilar and Thiha), not separate cloned actors. The script limit is 6,000 characters.

Example:
```
/recapvoice narrator
ဒီနေ့ ဇာတ်လမ်းရဲ့ အဓိကဖြစ်ရပ်တွေကို ပြောပြပါမယ်။
```

This step does not attach footage or render an MP4. Edge TTS requires network access; proofread names and subtitle timing before publishing.

## Episode recap outline worksheet

Use `/episodeoutline <series title>` after choosing a platform with `/platform youtube|facebook|tiktok`. NEXORA requests an exact TVmaze Animation series match, requires a known non-Indian country, and selects one highest-rated episode with a valid community rating and source URL. It creates a Burmese creator worksheet with an opening hook, setup, story-beat prompts, turning point, climax, ending, original commentary, and media-rights checks.

The worksheet includes only a short TVmaze research lead. It does not translate or rewrite the episode plot, invent scene events, generate a finished script, synthesize narration, or render an MP4. Verify every plot point against the actual episode and write original commentary. TVmaze ratings are community ratings, not view counts or popularity. This command does not classify 3D animation; an Animation genre tag is not proof of 3D.

Example:
`/episodeoutline Frieren: Beyond Journey's End`

## Highest-rated animated episode research

Use `/topratedepisodes <series title>` to retrieve up to five highest-rated episodes from TVMaze for an exact title match. The command requires the Animation genre and a known non-Indian country, includes episode source links, and omits episodes without a valid rating. It does not infer whether a series is 2D or 3D.

Important: TVMaze episode ratings are community ratings, not episode view counts, audience size, or live popularity. A high rating is only one research signal; it does not prove an episode will attract more recap views. For popularity, use comparable official view/engagement data when publicly available. If those metrics are missing, report them as unavailable rather than estimating them.

Example:
`/topratedepisodes Sample Donghua`

## Channel growth and publishing pack

Use `/growthpack <category>|<title>|<verified summary optional>` after selecting a platform with `/platform youtube|facebook|tiktok`. Supported categories are Anime, 3D Animation, Cartoon, Donghua, and International Movies (live-action). The command prepares platform-specific title options, an opening hook, description, hashtags, thumbnail/cover guidance, pacing suggestions, a comment prompt, and a pre-publish quality checklist. If a verified plot summary is supplied, it is included in the description; if not, the pack leaves a placeholder instead of inventing plot details.

This is a publishing and quality-planning helper, not a live trend detector, automatic popularity ranking, thumbnail image generator, or guarantee of views/likes. Use only accurate titles/thumbnails and media you own or are licensed to use. After publishing, review impressions, CTR, audience retention, average view duration, and returning viewers to decide what to improve.

Example:
`/growthpack Anime|Frieren: Beyond Journey's End|[verified short summary]`

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

## Animation categories and three-platform recap plan\n\nThe daily title rotation includes Anime, 3D Animation, Cartoon, and Donghua candidates. Use `/allplatforms <title>` to print the recommended split: YouTube 3 × 8–10 minutes (24–30 minutes total), Facebook 3 × 3–5 minutes (9–15 minutes total), and TikTok 3 × 1–3 minutes (3–9 minutes total). Part 1 covers the hook, world, characters, and setup; Part 2 covers the central conflict and turning points; Part 3 covers the climax/resolution within the stated film/season/arc and original commentary. Create separate edits for each platform.\n\nThe daily list is a curated catalogue, not a live popularity ranking. Check recent views, upload dates, search interest, and audience response before calling a title trending. The bot does not yet automatically measure live trends.\n\n## Daily automatic research (5:00 AM Thailand time)
The `.github/workflows/daily-auto.yml` workflow runs daily at 22:00 UTC (05:00 Asia/Bangkok on the following local date). It chooses one title per day from a built-in rotation across Anime, 3D Animation, Cartoon, and Donghua, runs the free Wikipedia source lookup, and sends research leads plus explicit YouTube/Facebook/TikTok part durations to the configured Telegram chat. The titles are curated candidates, not a live popularity ranking.

To enable delivery:
1. In Telegram, open your NEXORA bot and send `/chatid`. Copy the numeric chat ID shown.
2. In GitHub, open **Settings > Secrets and variables > Actions > New repository secret**.
3. Add `TELEGRAM_BOT_TOKEN` (the current bot token) and `TELEGRAM_CHAT_ID` (the chat ID from `/chatid`).
4. In **Actions**, enable workflows if GitHub asks, then use **Daily NEXORA Auto Research > Run workflow** once to test. The scheduled run is daily at 05:00 Thailand time.
5. Do not paste tokens into chat, code, commits, or screenshots. If a token was exposed, revoke it in BotFather and update both Render and GitHub secrets.

GitHub's scheduled workflow can start a little later than the exact minute. The bot's Render Free web service does not need to stay awake for the GitHub Actions job.






## Free Telegram backup for voice profiles

Render Free services do not provide a persistent disk. To avoid losing the only copy of a voice profile when the container restarts, NEXORA sends a fresh ZIP backup to the same Telegram chat after a profile is added, deleted, or imported. Keep the latest \`nexora_voice_profiles_latest.zip\` document in the chat (or save a private copy in Telegram Saved Messages).

After a Render restart/redeploy, the free container's local SQLite database may be empty. Send \`/voiceprofile import\`, then upload the latest ZIP document from the chat. NEXORA restores the profiles and sends a new backup. This is a manual restore workflow; Telegram Bot API does not let the bot browse old chat messages to restore a previous backup automatically. The backup is private voice data: do not share it publicly, and only store recordings you own or are authorized to use.

## Persistent voice profile storage

Voice Profile audio is stored in a per-Telegram-user SQLite database by `voice_profile_storage.py`. The default database path is `data/nexora_voice_profiles.sqlite3`. This survives process restarts only when that path is on persistent storage; a normal Render container filesystem is ephemeral and can be replaced during redeploys.

For Render, attach a Persistent Disk to the web service, mount it at `/var/data`, and set the private environment variable `VOICE_PROFILE_DB_PATH=/var/data/nexora_voice_profiles.sqlite3`. Redeploy after the disk and environment variable are configured. Do not point the database into the Git checkout or another ephemeral directory. Without the mounted disk, the SQLite integration works during the current container lifetime but does **not** guarantee survival across redeploys.

Each Telegram user ID has an isolated profile collection. The database stores audio BLOBs; keep the disk and exported ZIP backups private. Only upload recordings you own or are authorized to use. SQLite is included with Python, so no extra package is required. `/voiceprofile export` remains available as an additional manual backup.

## Burmese MP3 voice-over

Send \`/tts female\` or \`/tts male\`, then put the Burmese narration text on the next line. NEXORA can generate an MP3 using the Burmese neural voices \`my-MM-NilarNeural\` (female) or \`my-MM-ThihaNeural\` (male). The command accepts up to 6,000 characters and returns an MP3 file.

This uses the third-party \`edge-tts\` Python package to access Microsoft Edge's **online** text-to-speech service without an API key. It requires outbound internet access; it is not an offline model or a guaranteed/official Azure Speech API. The text you submit with \`/tts\` is sent to that online speech service for synthesis. Do not submit private or confidential text. Service availability, voice availability, and usage limits can change. Review the generated pronunciation and audio quality before publishing.

## Burmese subtitle draft export

Send `/srtmy` and put the Burmese narration script on the following lines. NEXORA splits it into readable caption chunks and creates a UTF-8 SRT download with estimated sequential timestamps. The estimate uses character count and a default reading-speed assumption; it is **not speech recognition or audio alignment**. Play the final narration and adjust caption timing before publishing. The command does not translate English into Burmese.

## Basic MP4 rendering from Telegram

The first rendering step is a simple slideshow: send `/render`, upload 1–12 JPG/PNG/WEBP images and one narration audio file (MP3/M4A/WAV/OGG, up to 20 MB and 10 minutes), then send `/render finish`. NEXORA returns a 720p MP4 with the images timed across the narration. Use `/render cancel` to clear the current session. The media is held in the running bot session and is not a permanent project archive.

This is not automatic text-to-speech, movie-footage generation, AI scene selection, or social auto-upload. Provide images/audio that you own or are licensed to use. Keep a human review step before publishing.

## Important limitations
- `/auto` automates initial public-source discovery only; it does not create a complete verified plot summary or finished recap script.
- This is not a connection to the ChatGPT conversation or an AI writing provider.
- SRT export does not translate. `/srtmy` can draft Burmese captions from Burmese text, but its estimated timestamps must be synchronized manually to the final narration.
- Burmese MP3 synthesis is available through the optional online Edge TTS command; it requires internet access and sends the submitted script to the remote speech service. It is not offline or guaranteed.\n- No AI scene selection, scheduled video queue, or automatic social publishing.
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


## Automatic privacy-safe GitHub error reports
NEXORA can create a GitHub Issue automatically when a Telegram update handler raises an unhandled exception.

To enable it:
1. Create a fine-grained GitHub personal access token restricted to this repository, with **Issues: Read and write** permission only.
2. In Render, open the NEXORA web service's **Environment** settings and add `GITHUB_ERROR_REPORT_TOKEN` with that token as its value.
3. Add `GITHUB_REPOSITORY` with value `naykokoko135-pixel/NEXORA-MYANMAR-RECAP` (optional for this repository).
4. Save changes and let Render redeploy.

The token is stored only in Render Environment; never paste it into Telegram, ChatGPT, GitHub source files, or screenshots. The reporter excludes Telegram message text, user/chat IDs, exception messages, and environment values. Duplicate errors with the same code fingerprint are limited to one report per 10 minutes per running process. If the token is not configured, normal bot operation continues and no GitHub report is sent. This reports unhandled Telegram handler exceptions; it does not automatically diagnose or modify code.


## Comment reply assistant

NEXORA includes a conservative comment-reply module:
- YouTube and Facebook Page: official API adapters can reply to short, unambiguous positive comments only.
- Questions, complaints, long/unclear comments, links, and contact details are left for human review.
- TikTok: reply text drafts only. TikTok's public Research API documents reading comments, not posting creator replies.
- Duplicate protection: YouTube threads with existing replies and Facebook comments already replied to by the Page are skipped.
- Safety defaults: `COMMENT_AUTOREPLY_ENABLED` is OFF unless explicitly enabled; at most 3 replies per platform per polling cycle.

Telegram commands:
- `/commentstatus` — show whether platform configuration is present (never displays tokens).
- `/commentdraft youtube|facebook|tiktok <comment>` — preview a safe reply draft; it does not post.

Render environment configuration (enter values privately in Render; never paste tokens into chat or commit them):
- `COMMENT_AUTOREPLY_ENABLED=true` — explicit master switch (leave unset/false until tested).
- `COMMENT_POLL_SECONDS=300` — polling interval; the app clamps it to 120–3600 seconds.
- YouTube: `YOUTUBE_COMMENT_ACCESS_TOKEN`, `YOUTUBE_CHANNEL_ID`, `YOUTUBE_COMMENT_VIDEO_IDS` (comma-separated video IDs). OAuth authorization needs the YouTube comment scope.
- Facebook Page: `FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`, `FACEBOOK_POST_IDS` (comma-separated post IDs), and the Page's approved comment read/reply permissions.
- TikTok has no auto-posting adapter in this release.

The module is disabled by default. Configure and test one platform at a time. API permissions, valid tokens, and platform approval are required; a configured variable alone does not prove that replies are working. The current reply text is deterministic and does not use a paid AI API.


## Burmese MP3 with word-aligned subtitles

Send `/ttssrt female` or `/ttssrt male`, then put the Burmese narration script on the next line. NEXORA streams the speech audio and word-boundary timing metadata from the online TTS service, then returns an MP3 and an SRT built from those timing events. This is more closely aligned than the estimated timestamps from `/srtmy`, but still review the SRT against the finished audio before publishing. The service may change its metadata behavior, and punctuation or unusual pronunciations can require manual correction. The same online-service privacy and availability cautions as `/tts` apply.


## Burmese voice style presets

The current no-key Burmese TTS voice list provides two Burmese neural speaker identities: Nilar (female) and Thiha (male). NEXORA therefore offers selectable delivery-style presets, not additional native speakers. Presets adjust speaking rate and pitch while retaining one of those two base voices:

- female, male — standard voices
- narrator — measured story narration
- hero — brighter, quicker male delivery
- villain — slower, lower male delivery
- elder — slower male character style
- youth — brighter, quicker female delivery
- emotional — slower, softer female delivery
- energetic — faster action delivery
- mystery — slower, lower female delivery
- comedy — quicker, brighter female delivery
- calm — slower, lower male delivery

Use `/voices` in Telegram to list them. Then use `/tts <preset>` for MP3 or `/ttssrt <preset>` for MP3 plus timed SRT. These settings change rate and pitch only; they do not create separate actors or guarantee emotional acting. Listen and review before publishing.
\n\n## Scene-based Burmese voice tracks\n\nUse `/scenetts` to create separate MP3 and word-aligned SRT files for up to 8 scenes. Start each scene with a supported preset header such as `[narrator]`, `[hero]`, `[villain]`, `[emotional]`, or `[mystery]`, then put that scene's Burmese text on the following lines. Each scene is exported as its own MP3/SRT pair so the editor can arrange the tracks. The current free Edge TTS integration still has only two Burmese speaker identities (Nilar and Thiha); presets change delivery rate/pitch, not the underlying speaker identity.\n

## Optional AI-designed Burmese character voices

VoxCPM2 can design a fictional synthetic voice from a natural-language description and supports Burmese text. NEXORA exposes this as an optional backend through `/tts_design <voice_name>`, with these built-in fictional profiles: `story_male`, `story_female`, `young_male`, `young_female`, `elder_male`, `villain`, `comic`, and `mystery`. Put the Burmese narration on the next line. The command returns a WAV file. These are generated character voices, not real actors or cloned identities.

This backend is **off by default** and is not part of the standard Render build. It requires a compatible GPU host, Python 3.10–3.12, PyTorch 2.5+, CUDA 12+, and approximately 8 GB of VRAM for VoxCPM2. On that host, install `requirements-voxcpm.txt` and set `NEXORA_VOXCPM_ENABLED=1`. Do not enable it on Render Free; its hardware is not suitable for this 2B-parameter model. The model repository is Apache-2.0 licensed. See the upstream [VoxCPM2 documentation](https://github.com/OpenBMB/VoxCPM) for current runtime requirements.

For a preview of existing Edge TTS delivery styles, use `/voicedemo <preset>`. This uses only the two existing Burmese voices (Nilar and Thiha) and changes delivery settings; it does not create a new speaker identity. The optional VoxCPM2 voice-design path is separate.

## Custom voice recordings

Use /voiceprofile <name>, then send your own MP3/M4A/WAV/OGG recording (up to 20 MB). Use /voiceprofile list to view saved clips and /voiceprofile delete <name> to remove one. Clips are stored per Telegram user in SQLite. To keep them across Render redeploys, attach a Persistent Disk and configure VOICE_PROFILE_DB_PATH as described in the Persistent voice profile storage section. Without that mounted disk, the database remains on ephemeral container storage. This stores prerecorded audio only; it does not clone a voice or synthesize new words. Use only your own recordings or recordings with clear permission. Use /voiceprofile export to download a ZIP backup and /voiceprofile import to restore it; import merges and validates file names, types, sizes, and archive contents. Keep the backup private because it contains audio recordings.


### Use saved character voices in MP4

Start a render with `/render`, send your authorized still images, then add saved recordings in order with `/render voice narrator`, `/render voice hero`, `/render voice villain`, etc. Up to 12 audio clips are concatenated sequentially into one narration track. The combined audio is limited to 20 MB and 10 minutes. Finish with `/render finish`. A normal narration audio upload remains supported when no saved voice tracks are selected. 

## Character-role scene voice presets

Use `/scenetts` and give each scene a role header. Character aliases make scripts easier to organize:
- `[narrator]` — narrator
- `[protagonist]` or `[male_lead]` — hero delivery
- `[heroine]` or `[female_lead]` — standard female delivery
- `[antagonist]` — villain delivery
- `[supporting]` — calm delivery
- `[elder]`, `[child]`, `[comic]`, `[suspense]`, `[action]` — matching existing style presets

Example:
```text
/scenetts
[narrator]
ဇာတ်လမ်းကို မိတ်ဆက်ကြမယ်။
[protagonist]
ငါ ဒီအခက်အခဲကို ကျော်ဖြတ်မယ်။
[antagonist]
မင်း ငါ့ကို တားနိုင်မှာ မဟုတ်ဘူး။
[heroine]
ငါတို့ အတူတူ ဖြေရှင်းကြမယ်။
```

Each scene still produces its own MP3/SRT pair. These aliases select existing delivery presets only; the free Burmese TTS service has two speaker identities (Nilar and Thiha). They do not create new actors or clone a voice. For actual recorded character audio, use creator-owned or authorized recordings with `/voiceprofile`; those recordings are reused as-is, not converted into new spoken text.

The clips are concatenated, not automatically synchronized to character dialogue or subtitles.


### မြန်မာ Role ခေါင်းစဉ်များ

`/scenetts` တွင် English မရေးဘဲ မြန်မာလိုလည်း ခေါင်းစဉ်တပ်နိုင်သည်။

- `[ဇာတ်ကြောင်း]` — Narrator
- `[မင်းသား]` — Hero delivery
- `[မင်းသမီး]` — Female delivery
- `[ဗီလိန်]` — Villain delivery
- `[လူကြီး]` — Elder delivery
- `[ကလေး]` — Youth delivery
- `[ဟာသ]` — Comedy delivery
- `[လျှို့ဝှက်]` — Mystery delivery
- `[အက်ရှင်]` — Energetic delivery

မြန်မာ Role များသည် ရှိပြီးသား preset များသို့ ချိတ်ဆက်ထားခြင်းသာဖြစ်သည်။ သီးခြားအသံသရုပ်ဆောင်အသစ် သို့မဟုတ် Voice Cloning မဟုတ်ပါ။


## Optional local Burmese TTS experiment

NEXORA keeps the existing Edge TTS commands unchanged. An additional experimental `/tts-local` command can run MyanmarTTS inference inside the NEXORA process; the narration text is not sent to a hosted TTS inference API. The upstream package downloads its model assets from Hugging Face on first initialization, so the host needs outbound access for model files. This is not the third-party public Hugging Face Space.

This backend is **off by default** and is intentionally excluded from the default Render Free dependencies. To try it on a separate machine or a host with sufficient memory and CPU:

1. Install the optional dependencies with `pip install -r requirements-local-tts.txt`.
2. Set `NEXORA_LOCAL_TTS_ENABLED=1` in that host's environment.
3. Start NEXORA and send `/tts-local` followed by Burmese text on the next line.
4. To test the actual model independently of Telegram, run `NEXORA_LOCAL_TTS_ENABLED=1 python smoke_local_myanmar_tts.py` from the repository folder. On Windows PowerShell, use `$env:NEXORA_LOCAL_TTS_ENABLED="1"; python smoke_local_myanmar_tts.py`.
5. The smoke test writes `local_myanmar_tts_smoke.wav` locally and reports the WAV duration/sample rate. Play the file to review pronunciation and audio quality; delete it when finished if it is no longer needed.

The smoke test uses a short default Burmese phrase. To change it, set `NEXORA_LOCAL_TTS_SMOKE_TEXT` in the same shell. It requires the optional model dependencies and may download model assets on first run. It is an opt-in real-model check, not part of normal Render deployment or the lightweight unit-test workflow.

The first request may take longer while the model assets are downloaded and loaded. CPU inference can be slow; the default test limits scripts to 1,200 characters and exports WAV. The default Render Free service is not enabled for this feature because PyTorch/model memory and CPU requirements have not been validated there.

MyanmarTTS currently uses a single default reference voice in its simple package interface; it is **not** a library of multiple named character actors. Do not use another person's reference recording unless you have their clear permission. This optional experiment does not alter or replace Nilar/Thiha, does not change existing `/tts`, `/ttssrt`, or `/scenetts` behavior, and does not provide word-aligned SRT.

Model information and upstream license notes: [MyanmarTTS on PyPI](https://pypi.org/project/MyanmarTTS/) and [model card](https://huggingface.co/freococo/MyanmarTTS). The model weights and generated samples are CC0; supporting code and vocoder retain their stated MIT licenses. Review the upstream NOTICE before redistribution.


### Run the real-model smoke test with GitHub Actions

You can run the optional MyanmarTTS model test without installing the dependencies on your phone or changing Render:

1. Open the repository's **Actions** tab.
2. Select **Manual Local MyanmarTTS Smoke Test**.
3. Choose **Run workflow**. The default sample is a short generic Burmese sentence; do not enter private or personal text.
4. Wait for the job to finish. Open the completed run and download the `nexora-local-myanmar-tts-smoke` artifact.
5. Extract and play `local_myanmar_tts_smoke.wav` to review pronunciation and audio quality.

This workflow is manually triggered only. It installs the optional dependencies on a temporary GitHub-hosted runner, may download model assets from Hugging Face, and uploads the generated WAV as a short-lived artifact (3-day retention). It does not use repository secrets, change Render settings, or enable local TTS on the production bot. Runner memory/CPU limits may prevent the model from completing; a successful unit-test run does not prove that the real model has generated audio.

## Optional VoxCPM2 real-model smoke test

To verify actual synthetic Burmese audio on a separate compatible machine (not the Render Free service):

1. Install the optional dependencies with `pip install -r requirements-voxcpm.txt` in Python 3.10–3.12.
2. Make sure the machine has a compatible runtime and sufficient memory. For NVIDIA GPU inference, the upstream requirements include PyTorch 2.5+ and CUDA 12+; model VRAM use is approximately 8 GB.
3. Set `NEXORA_VOXCPM_ENABLED=1` in the local shell.
4. Run `python smoke_voxcpm_voice_design.py --voice story_female`.
5. Play `voxcpm_voice_design_smoke.wav` and review Burmese pronunciation and voice quality.

You can choose any name listed by `python smoke_voxcpm_voice_design.py --help`, pass a short script with `--text`, and change the output path with `--output`. The smoke test loads the model and generates a real sample; first startup may take time to download model weights. This script does not upload audio, change Render settings, or enable the bot backend. Keep the generated audio private if the script contains personal information.


## AI-designed voices per scene

Use `/scenedesign` and put each scene under an `[ai:voice_name]` header. Example:

```text
/scenedesign
[ai:story_female]
ဒီနေ့ ဇာတ်လမ်းကို စတင်မိတ်ဆက်ပါမယ်။
[ai:young_male]
ကျွန်တော် ဒီနေရာကို ပထမဆုံး ရောက်ဖူးတာပါ။
[ai:villain]
မင်း ဒီအကြောင်းကို ဘယ်သူ့ကိုမှ မပြောရဘူး။
[ai:mystery]
ဒါပေမဲ့ အဲဒီညမှာ ထူးဆန်းတဲ့အရာတစ်ခု ဖြစ်လာခဲ့တယ်။
```

The bot sends one WAV per scene. It accepts up to 4 scenes, up to 1,500 characters per scene and 6,000 characters total. This feature uses the optional VoxCPM2 backend and therefore requires a compatible GPU host with `NEXORA_VOXCPM_ENABLED=1`; it is not enabled on Render Free by default. These are fictional prompt-designed synthetic voices, not recordings or copies of real actors. Audio generation is sequential and may take time. This command does not create aligned SRT files; use the existing `/scenetts` command for the Edge TTS MP3 + SRT workflow.


## Recap editorial quality preflight

Use `/recapqa <category>|<title>` followed by the creator-written Burmese recap script on the next line(s). The command checks the selected category, excluded project titles, basic script length, presence of a hook/story/turning-point/ending/original-commentary structure, source URLs, repeated paragraphs, and a media-rights note. It returns a conservative checklist and flags missing elements before publication.

Supported categories: Anime, 3D Animation, Cartoon, Donghua, and International Movies. Indian-origin titles are excluded by the existing metadata research safeguards; this deterministic preflight also blocks the project's explicitly excluded title list.

**Important:** This is a structure-only preflight. It does not fact-check plot events, verify that URLs support claims, determine whether footage/music is legally reusable, translate text, or predict views/likes. A clean report means only that the checked editorial signals are present; human review remains required.


## Animated episode production pack

Use Telegram `/episodepack <exact animated series title>` to collect up to five highest-rated episodes from an exact TVmaze Animation-genre match, then search Wikimedia Commons for a strongly title-matched CC0, CC BY, CC BY-SA, or Public Domain video candidate. The pack includes episode rating, short synopsis lead, air date, TVmaze source, and any candidate file's license/creator/Commons page.

TVmaze ratings are community ratings, not views or popularity. This is an editorial research brief, not an automatically written recap or finished MP4. Commons title matching does not establish that a file depicts the actual episode scene; inspect it before use. Follow the specific license attribution/share-alike terms. TVmaze Animation genre does not distinguish 2D from 3D, so do not classify an item as 3D Animation from this command alone. Unknown country or India-origin titles are rejected by the existing TVmaze research guard.
