# NEXORA Anime Recap — YouTube workflow

This profile configures the daily 05:00 Asia/Bangkok research rotation for anime films and series. It does not add an AI provider or automatically create finished scripts/videos.

## Recommended YouTube defaults

- Platform: `/platform youtube`
- Duration: `/duration 15-20`
- Format: three separate recap parts, with original Burmese narration and commentary.
- Scope: identify the exact film, season, or arc. Do not combine different seasons or arcs without clearly saying so.

## Telegram workflow

1. Send `/auto <anime title>` to collect public Wikipedia research leads.
2. Open the returned source links and verify names, chronology, season/episode scope, and plot facts against reliable sources and the anime itself.
3. Send `/draft3 <anime title>` to create three YouTube planning worksheets. Or add your checked notes on new lines after the command.
4. Send `/voiceover3 <anime title>` followed by at least six verified fact lines to export three editable voice-over text files.
5. Prepare English subtitle text with timestamps and use `/srt` to export an SRT file. SRT export formats text; it does not translate.
6. Send `/render`, upload 1–12 images you own or are licensed to use and one narration audio file, then send `/render finish` to create a 720p slideshow MP4.

## Anime-specific editorial checklist

- State the anime title and whether the recap covers a film, season, or named story arc.
- Add a spoiler warning when discussing major plot developments or the ending.
- Keep character names and Japanese/Chinese terms consistent; check romanization and official spellings.
- Distinguish confirmed canon from interpretation, fan theories, and uncertain details.
- Add original analysis, themes, character motivations, and commentary rather than reproducing dialogue or substituting for the original viewing experience.
- Do not copy full episodes, long scene sequences, official promotional art, soundtrack, or other copyrighted assets without permission. Use original, licensed, or otherwise authorized visuals and audio.
- Review the final narration, subtitles, and video manually before publishing.

## Current capability boundaries

The daily workflow searches Wikipedia for source leads and sends a three-part outline. It does not independently fact-check an anime, write a complete factual script, generate narration, select anime scenes, or upload to YouTube. The MP4 renderer currently makes a slideshow from creator-supplied images and narration audio.
