# NEXORA — Animation Recap for YouTube, Facebook and TikTok

NEXORA is being prepared for four animation categories:
1. Anime
2. 3D Animation
3. Cartoon
4. Donghua

The daily research rotation contains curated titles across all four categories. It is an evergreen candidate catalogue, not a real-time popularity ranking. A title must be checked against current platform interest (recent views, upload date, search interest, and audience response) before being labelled trending or popular. The existing free research lookup provides Wikipedia leads only; it does not measure current views.

## Three-platform episode structure

These are recommended starting durations. Adjust them to the length and scope of the film, season, or story arc.

| Platform | Parts | Each part | Total |
|---|---:|---:|---:|
| YouTube | 3 | 8–10 minutes | 24–30 minutes |
| Facebook | 3 | 3–5 minutes | 9–15 minutes |
| TikTok | 3 | 1–3 minutes | 3–9 minutes |

### Part-by-part coverage

- Part 1: hook, title/scope, world and character introduction, inciting event.
- Part 2: central conflict, character decisions, turning points, consequences.
- Part 3: climax and resolution within the stated film/season/arc, followed by original commentary.

Each platform needs its own edit, pacing, title, caption, cover, and suitable aspect ratio. Do not simply upload the same long video unchanged to every platform.

## Telegram commands

1. `/allplatforms <title>` — prints the three-platform, three-part duration plan.
2. `/auto <title>` — searches public Wikipedia pages for research leads.
3. `/draft3 <title>` — creates three YouTube planning worksheets using cached research, or checked notes supplied with the command.
4. `/voiceover3 <title>` followed by at least six creator-checked fact lines — exports three voice-over text files.
5. `/srt` — formats timestamped English subtitle text as SRT; it does not translate.
6. `/render` — makes a basic 720p slideshow from 1–12 creator-supplied authorized images and one narration audio file (audio must be under 10 minutes and 20 MB). Render each part as a separate project/video.

For platform-specific worksheets, use `/platform youtube|facebook|tiktok` and a supported `/duration` value. YouTube presets: 8–10, 12–15, 15–20, 20–30, 30–45, 45–60 minutes. Facebook: 3–5, 5–7, 8–10, 10–15 minutes. TikTok: 1–3, 3–5 minutes.

## Popular/trending title selection

Before choosing a title as currently popular, manually check recent platform evidence such as:
- recent official/trailer/episode uploads and their view counts;
- recent audience response and discussion;
- current search interest;
- whether the title is currently releasing episodes or has a new season/film.

Record the source links and the date checked. Do not call a title “trending now” based only on a static catalogue or Wikipedia. Automatic live trend detection is not yet part of the bot.

## Editorial and rights checklist

- Clearly name the exact film, season, episode range, or story arc being covered.
- Add spoiler warnings where appropriate.
- Verify chronology, character names, and plot facts against the source material and reliable references.
- Use original Burmese narration, analysis, and commentary. Do not reproduce long dialogue, scripts, or another creator's recap.
- Use only original, licensed, or otherwise authorized visuals, clips, music, and audio. A recap label does not itself grant permission to reuse footage.
- Review every part and subtitle before publishing.

## Current capability limits

The daily workflow sends source leads and a planning worksheet; it does not generate a complete fact-checked script or determine live popularity. The current renderer creates a slideshow from images and narration supplied by the creator. It does not generate animation scenes, AI voice, or upload videos automatically to YouTube, Facebook, or TikTok. Publishing is manual until official platform integrations, permissions, and account setup are added and tested.
