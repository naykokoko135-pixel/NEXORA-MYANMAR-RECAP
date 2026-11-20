import asyncio
import base64
import binascii
import time
import hmac
from io import BytesIO
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from telegram import InputFile, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from srt_builder import build_srt
from subtitle_builder import build_burmese_srt
from tts_builder import VOICE_PRESETS, synthesize_burmese_speech, synthesize_burmese_speech_with_srt, validate_tts_request
from local_myanmar_tts import synthesize_local_burmese_speech
from voxcpm_voice_design import VOICE_DESIGNS, synthesize_designed_burmese_voice
from scene_tts import parse_scene_script, parse_voice_design_scene_script
from voice_profiles import normalize_profile_name, store_voice_profile, delete_voice_profile
from voice_profile_storage import load_voice_profiles, save_voice_profiles
from voice_profile_backup import export_voice_profile_backup, import_voice_profile_backup, VoiceProfileBackupError, MAX_BACKUP_BYTES
from research_builder import generate_research_worksheet
from draft_builder import generate_draft_worksheet, generate_three_part_draft_worksheets
from auto_research import search_movie_sources, ResearchLookupError
from seriesguide_command import series_guide_cmd
from research_draft import matching_cached_research
from voiceover_builder import generate_voiceover_draft, generate_voiceover_part_files
from video_renderer import render_slideshow, render_scene_timeline, VideoRenderError
from clip_source_finder import search_licensed_video, ClipSourceError
from europeana_video_finder import search_europeana_licensed_video, EuropeanaSearchError, display_media_url
from youtube_cc_finder import search_youtube_cc_videos, YouTubeCCSearchError
from youtube_movie_recap_research import search_youtube_movie_recaps, format_youtube_movie_recaps, YouTubeRecapResearchError
from recap_studio import build_original_recap_notes
from licensed_video_pipeline import choose_matching_source, render_licensed_preview, LicensedClipError
from licensed_narrated_clip import render_licensed_narrated_preview, build_licensed_attribution_note, _subtitle_duration_seconds
from wikidata_metadata import fetch_wikidata_metadata
from recap_metadata_resolver import resolve_recap_metadata
from autofacts_narration import generate_burmese_facts_narration
from myanmar_plot_research import fetch_burmese_plot_section, PlotResearchError
from verified_plot_narration import generate_burmese_plot_narration
from anilist_synopsis import fetch_anilist_synopsis
from multi_source_research import research_anime_sources, format_anime_source_report
from tmdb_movie_research import research_movie_sources, format_movie_source_report
from tvmaze_synopsis import fetch_tvmaze_synopsis
from tvmaze_synopsis import fetch_tvmaze_episode_summaries, fetch_tvmaze_top_rated_episodes
from animated_episode_pack import format_animated_episode_pack
from episode_recap_outline import format_episode_recap_outline
from english_plot_research import fetch_english_plot_section, EnglishPlotError
from english_plot_recap import generate_burmese_recap_from_english_plot
from synopsis_preview import generate_burmese_synopsis_preview
from channel_growth_pack import generate_growth_pack
from recap_quality_gate import analyze_recap_script, format_recap_qa_report
from recap_voice_pack import parse_recap_voice_request
from recap_video_pack import parse_recap_video_request, validate_non_indian_wikidata_metadata, build_recap_video_sidecars, format_no_licensed_footage_message, format_original_visual_fallback_notice
from original_visual_recap import build_original_visual_cards

from script_writer import (generate_recap_outline, generate_all_platform_plan, PLATFORM_NAMES, PLATFORM_DURATIONS, DURATION_PRESETS, DEFAULT_DURATIONS)
from openai_script_provider import generate_burmese_recap_script, openai_script_status, AIScriptError
from gemini_script_provider import gemini_script_status
from error_reporter import report_error_to_github
from comment_autoreply import build_reply, platform_comment_capabilities, run_comment_autoreply_cycle
from web_console import CONSOLE_HTML, create_console_session, verify_console_session

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("nexora")

# HTTPX logs full Telegram API URLs at INFO level; those URLs contain the bot token.
# Keep request URLs out of Render logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")
telegram_app: Application | None = None
comment_autoreply_task: asyncio.Task | None = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "မင်္ဂလာပါ။ NEXORA Myanmar Recap Bot ပါ။\n\n"
            "/status - စနစ်အခြေအနေ\n"
            "/chatid - Daily Auto ပို့မည့် Chat ID ကြည့်ရန်\n"
            "/create <ခေါင်းစဉ်> - Free Recap template\n"
            "/research <ဇာတ်ကားအမည်> - Source စစ်ဆေးရန် worksheet\n"
            "/auto <ဇာတ်ကားအမည်> - အခမဲ့ ရင်းမြစ်ရှာရန်\n"
            "/seriesguide <ဇာတ်လမ်းတွဲအမည်> - Season/Episode လမ်းညွှန် စစ်ဆေးရန်\n"
            "ပြီးနောက် /draft3 <ဇာတ်ကားအမည်> - ရှာထားသော Notes ကို အလိုအလျောက်သုံးရန်\n"
            "/draft <ဇာတ်ကားအမည်> - Research Notes မှ Draft worksheet\n"
            "/draft3 <ဇာတ်ကားအမည်> - YouTube သုံးပိုင်း Draft worksheets\n"
            "/allplatforms <အမည်> - YouTube/Facebook/TikTok အပိုင်းနှင့် ကြာချိန်ခွဲပြရန်\n"
            "/voiceover <ဇာတ်ကားအမည်> - Notes မှ Voice-over မူကြမ်းဖိုင်ထုတ်ရန်\n"
            "/voiceover3 <ဇာတ်ကားအမည်> - Notes မှ Voice-over ဖိုင် ၃ ဖိုင်ထုတ်ရန်\n"
            "/clipsource <အမည်> - CC/Public Domain Video ရင်းမြစ်ရှာရန်\n"
            "/autoclip <အမည်> - လိုင်စင်ရှိ Video မှ MP4 Preview ထုတ်ရန်\n"
            "/autonarrateclip <အမည်> - Licensed footage + မြန်မာ narration/SRT Preview ထုတ်ရန်\n"
            "/autofactsclip <အမည်> - Wikidata အချက်အလက်မှ မြန်မာအသံ + Licensed footage Preview အလိုအလျောက်ထုတ်ရန်\n"
            "/growthpack <category>|<title>|<summary optional> - Channel ထုတ်ဝေမှု Pack ထုတ်ရန်\n"
            "/topratedepisodes <အမည်> - TVmaze rating အမြင့်ဆုံး Animation Episode များ ရှာရန်\n"
            "/episodepack <Series အမည်> - Episode + Licensed Footage Production Pack ထုတ်ရန်\n"
            "/episodeoutline <Series အမည်> - Episode တစ်ခုအတွက် Recap Script Worksheet ထုတ်ရန်\n"
            "/recapvoice [preset] - ကိုယ်ရေးထားသော Recap Script မှ MP3 + အသံနှင့်ကိုက်ညီသော SRT ထုတ်ရန်\n"
            "/recapvideo <title> - အလိုအလျောက် narration + Licensed Footage (မရှိပါက Original Visuals) + SRT ပါ MP4 ထုတ်ရန်\n"
            "/moviemultisourceresearch <ရုပ်ရှင်အမည်> - TMDB + Wikidata metadata စစ်ရန်\n"
            "/multisourceresearch <Anime အမည်> - AniList + Tenrai/MAL + Wikidata ကို တစ်ပြိုင်နက်စစ်ရန်\n"
            "/render - လက်ရှိ Platform အချိုးအစားဖြင့် ပုံ/အသံမှ MP4 ထုတ်ရန်\n"
            "/mode free|ai - Mode ရွေးရန်\n"
            "/srt - Timestamp ပါသော စာတန်းမှ SRT ဖိုင်ထုတ်ရန်\n"
            "/srtmy - မြန်မာစာသားမှ SRT ထုတ်ရန်\n"
            "/tts <preset> - မြန်မာ MP3 အသံထုတ်ရန်\n"
            "/voicedemo <preset> - ရှိပြီးသားအသံပုံစံနမူနာ MP3 နားထောင်ရန်\n"
            "/tts_design <voice_name> - AI စိတ်ကူးယဉ်ဇာတ်ကောင်အသံ WAV ဖန်တီးရန် (GPU host လိုအပ်)\n"
            "/scenedesign - ဇာတ်ဝင်ခန်းအလိုက် AI အသံ WAV များထုတ်ရန် (GPU host လိုအပ်)\n"
            "/ttssrt <preset> - MP3 နှင့် အချိန်ကိုက် SRT တွဲထုတ်ရန်\n"
            "/tts_local - Local MyanmarTTS WAV ထုတ်ရန် (စမ်းသပ်ဆဲ၊ host enable လိုအပ်)\n"
            "/voices - အသံပုံစံအားလုံးကြည့်ရန်\n"
            "/voiceprofile <name> - ကိုယ်ပိုင်အသံဖိုင် သိမ်းရန်\n"
            "/voiceprofile export|import - အသံ Profile Backup ထုတ်/ပြန်သွင်းရန်\n"
            "/platform youtube|tiktok|facebook - Platform ရွေးရန်\n"
            "/duration <ကြာချိန်> - Platform အလိုက် ကြာချိန်ရွေးရန်\n"
            "YouTube: 8-10, 12-15, 15-20, 20-30, 30-45, 46-60 မိနစ်\nFacebook: 46-60 မိနစ်\nTikTok: 4-7 မိနစ်\n"
            "/settings - လက်ရှိရွေးချယ်မှုကြည့်ရန်\n"
            "/commentstatus - Comment Auto-Reply အခြေအနေ\n"
            "/commentdraft <platform> <comment> - Reply Draft ထုတ်ရန်\n"
            "/help - အကူအညီ"
        )


async def chatid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current Telegram chat ID for daily delivery setup."""
    if not update.effective_chat or not update.message:
        return
    await update.message.reply_text(
        "နေ့စဉ် Auto ပို့ရန် Chat ID:\n"
        f"{update.effective_chat.id}\n\n"
        "ChatGPT → Telegram ချိတ်ဆက်ရန် ဒီနံပါတ်ကို Render Dashboard > "
        "nexora-myanmar-recap-bot > Environment ထဲရှိ CHATGPT_BRIDGE_CHAT_ID "
        "အဖြစ်သာ ထည့်ပါ။ ဒီနံပါတ်ကို ChatGPT စကားဝိုင်း၊ GitHub code သို့မဟုတ် "
        "အများမြင်နိုင်သောနေရာတွင် မပို့ပါနှင့်။ Telegram Bot Token ကိုလည်း မမျှဝေပါနှင့်။"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        ai_status = openai_script_status()
        if ai_status["configured"]:
            ai_line = f"OpenAI Script API: ချိတ်ထားသည် ({ai_status['model']})"
        else:
            ai_line = "OpenAI Script API: မချိတ်ရသေးပါ (Render တွင် OPENAI_API_KEY လိုအပ်သည်)"
        gemini_status = gemini_script_status()
        gemini_line = (
            f"Gemini Fallback: ချိတ်ထားသည် ({gemini_status['model']})"
            if gemini_status["configured"]
            else "Gemini Fallback: မချိတ်ရသေးပါ (OpenAI Quota ပြည့်လျှင် GEMINI_API_KEY လိုအပ်သည်)"
        )
        await update.message.reply_text(
            "NEXORA Bot: အလုပ်လုပ်နေပါတယ်။\n"
            f"{ai_line}\n"
            f"{gemini_line}\n"
            "AI Script: /aiscript <title> ပြီးနောက် Verified Research Notes ထည့်ပါ။\n"
            "လုပ်ဆောင်နိုင်မှု: Auto research + Worksheets + Voice-over TXT + TTS MP3 + အချိန်ကိုက် SRT + Image/Audio MP4 render\n"
            "Local MyanmarTTS WAV: Host setting ဖြင့်သာ ဖွင့်နိုင်ပြီး optional dependencies နှင့် သင့်တော်သော host လိုအပ်သည်။\n"
            "Daily Auto: GitHub Actions မှ မနက် ၅ နာရီ (ထိုင်းစံတော်ချိန်) Research ပို့နိုင်သည်။\n"
            "Social auto-upload: မပါဝင်သေးပါ။\n"
            "Comment Auto-Reply: YouTube/Facebook API ချိတ်ဆက်ပြီး Enable လုပ်မှ အလုပ်လုပ်မည်။ TikTok သည် Draft-only ဖြစ်သည်။ /commentstatus ဖြင့် စစ်ပါ။"
        )


async def comment_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    enabled = os.getenv("COMMENT_AUTOREPLY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    yt_ready = all(os.getenv(key, "").strip() for key in (
        "YOUTUBE_COMMENT_ACCESS_TOKEN", "YOUTUBE_CHANNEL_ID", "YOUTUBE_COMMENT_VIDEO_IDS"
    ))
    fb_ready = all(os.getenv(key, "").strip() for key in (
        "FACEBOOK_PAGE_ACCESS_TOKEN", "FACEBOOK_PAGE_ID", "FACEBOOK_POST_IDS"
    ))
    await update.message.reply_text(
        "NEXORA Comment စနစ်\n"
        f"Auto-Reply Master Switch: {'ON' if enabled else 'OFF'}\n"
        f"YouTube API Config: {'ပြင်ဆင်ပြီး' if yt_ready else 'မပြင်ဆင်ရသေး'}\n"
        f"Facebook Page API Config: {'ပြင်ဆင်ပြီး' if fb_ready else 'မပြင်ဆင်ရသေး'}\n"
        "TikTok: Reply စာသား Draft သာ (တရားဝင် Creator Reply API မရရှိသေး)\n\n"
        "မှတ်ချက်: Token တန်ဖိုးများကို Chat ထဲ မပို့ပါနှင့်။ Review လိုသော မေးခွန်း/တိုင်ကြားမှု/ကိုယ်ရေးအချက်အလက်ပါ Comment များကို အလိုအလျောက် မပြန်ပါ။"
    )


async def comment_draft_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    parts = update.message.text.split(maxsplit=2)
    if len(parts) < 3 or parts[1].lower() not in {"youtube", "facebook", "tiktok"}:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /commentdraft youtube Comment စာသား\n"
            "Platform: youtube | facebook | tiktok"
        )
        return
    platform, comment = parts[1].lower(), parts[2].strip()
    reply = build_reply(comment)
    if reply is None:
        await update.message.reply_text(
            f"{platform.upper()} Comment ကို လူကိုယ်တိုင် စစ်ဆေးရန် လိုအပ်ပါတယ်။\n"
            "အကြောင်းရင်း: မေးခွန်း၊ ဝေဖန်မှု၊ မရှင်းလင်းသောစာသား သို့မဟုတ် ကိုယ်ရေးအချက်အလက် ပါဝင်နိုင်သည်။\n"
            "အလိုအလျောက် ပြန်စာမပို့ထားပါ။"
        )
        return
    await update.message.reply_text(
        f"{platform.upper()} Reply Draft:\n{reply}\n\n"
        "ဤသည် Draft သာဖြစ်ပြီး Platform ပေါ်သို့ မပို့ရသေးပါ။"
    )


async def comment_autoreply_loop():
    """Poll enabled official API adapters at a bounded interval."""
    while True:
        try:
            result = await asyncio.to_thread(run_comment_autoreply_cycle)
            if result.get("enabled") and (result.get("youtube_sent") or result.get("facebook_sent")):
                log.info(
                    "Comment replies sent: YouTube=%s Facebook=%s",
                    result.get("youtube_sent", 0), result.get("facebook_sent", 0)
                )
        except Exception:
            # Do not log exception details; they may contain user content or request metadata.
            log.warning("Comment auto-reply cycle failed")
        try:
            interval = int(os.getenv("COMMENT_POLL_SECONDS", "300"))
        except ValueError:
            interval = 300
        await asyncio.sleep(max(120, min(interval, 3600)))


async def research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("အသုံးပြုပုံ: /research ဇာတ်ကားအမည်")
        return
    worksheet = generate_research_worksheet(topic)
    for start_at in range(0, len(worksheet), 3900):
        await update.message.reply_text(worksheet[start_at:start_at + 3900])



async def auto_research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("အသုံးပြုပုံ: /auto Avatar")
        return
    await update.message.reply_text("အခမဲ့ အများပြည်သူသုံး ရင်းမြစ်ကို ရှာဖွေနေပါတယ်...")
    try:
        result = await asyncio.to_thread(search_movie_sources, topic)
    except ResearchLookupError as exc:
        await update.message.reply_text(f"ရှာဖွေမှု မအောင်မြင်ပါ: {exc}")
        return
    if "ကိုက်ညီသော Wikipedia ဆောင်းပါး မတွေ့ပါ" not in result:
        context.user_data["last_auto_research_title"] = topic
        context.user_data["last_auto_research_result"] = result
        await update.message.reply_text(
            "Research ရလဒ်ကို ဒီ Telegram session အတွက် သိမ်းထားပါပြီ။ "
            "အခု /draft3 " + topic + " လို့ပို့ပြီး Worksheet သုံးပိုင်းထုတ်နိုင်ပါတယ်။"
        )
    for start_at in range(0, len(result), 3900):
        await update.message.reply_text(result[start_at:start_at + 3900])



async def allplatforms_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send an explicit three-part duration plan for all supported platforms."""
    if not update.message:
        return
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("အသုံးပြုပုံ: /allplatforms Anime အမည်")
        return
    plan = generate_all_platform_plan(topic)
    for start_at in range(0, len(plan), 3900):
        await update.message.reply_text(plan[start_at:start_at + 3900])


async def draft_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    first_line, separator, notes = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    topic = parts[1].strip() if len(parts) > 1 else ""
    if not topic or not separator or not notes.strip():
        await update.message.reply_text(
            "အသုံးပြုပုံ:\n/draft Avatar\nပြီးနောက် စာကြောင်းအသစ်မှ စစ်ဆေးထားသော Research Notes များ ထည့်ပါ။"
        )
        return
    platform = context.user_data.get("platform", "youtube")
    duration = context.user_data.get("duration", DEFAULT_DURATIONS[platform])
    try:
        worksheet = generate_draft_worksheet(topic, notes, platform=platform, duration=duration)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    for start_at in range(0, len(worksheet), 3900):
        await update.message.reply_text(worksheet[start_at:start_at + 3900])


async def draft3_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Build three separate YouTube planning worksheets from creator-checked notes."""
    if not update.message or not update.message.text:
        return
    first_line, separator, notes = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    topic = parts[1].strip() if len(parts) > 1 else ""
    if not topic:
        await update.message.reply_text("အသုံးပြုပုံ: /draft3 Avatar")
        return
    if not (separator and notes.strip()):
        notes = matching_cached_research(
            topic,
            context.user_data.get("last_auto_research_title", ""),
            context.user_data.get("last_auto_research_result", ""),
        )
        if not notes:
            await update.message.reply_text(
                "ဒီဇာတ်ကားအတွက် Auto Research မတွေ့သေးပါ။ အရင် /auto Avatar ပို့ပါ။ "
                "ပြီးရင် /draft3 Avatar လို့ ပို့ပါ။ သို့မဟုတ် /draft3 နောက်တစ်ကြောင်းမှာ "
                "စစ်ဆေးထားသော Research Notes ကို တိုက်ရိုက်ထည့်နိုင်ပါတယ်။"
            )
            return
        await update.message.reply_text("သိမ်းထားသော Auto Research ကို Draft ထဲ ထည့်နေပါတယ်...")
    duration = context.user_data.get("duration", DEFAULT_DURATIONS["youtube"])
    try:
        worksheet = generate_three_part_draft_worksheets(topic, notes, duration=duration)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    for start_at in range(0, len(worksheet), 3900):
        await update.message.reply_text(worksheet[start_at:start_at + 3900])


async def voiceover_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Format creator-checked notes as a downloadable Burmese voice-over draft."""
    if not update.message or not update.message.text:
        return
    first_line, separator, notes = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    topic = parts[1].strip() if len(parts) > 1 else ""
    if not topic or not separator or not notes.strip():
        await update.message.reply_text(
            "အသုံးပြုပုံ:\n/voiceover Avatar\n"
            "ပြီးနောက် ဇာတ်ကားနဲ့ ပြန်စစ်ထားတဲ့ ဖြစ်ရပ်များကို စာကြောင်းတစ်ကြောင်းစီ ထည့်ပါ။"
        )
        return
    try:
        draft = generate_voiceover_draft(topic, notes)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    file_obj = BytesIO(draft.encode("utf-8-sig"))
    file_obj.name = "nexora_voiceover_draft.txt"
    await update.message.reply_document(
        document=InputFile(file_obj, filename=file_obj.name),
        caption=(
            "Voice-over မူကြမ်းဖိုင်ပါ။ သင်ပေးထားသော Notes ကိုသာ စီစဉ်ထားပြီး "
            "AI ရေးသားခြင်း သို့မဟုတ် Fact-check လုပ်ခြင်း မဟုတ်ပါ။"
        ),
    )


async def voiceover3_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export the three voice-over sections as separate downloadable text files."""
    if not update.message or not update.message.text:
        return
    first_line, separator, notes = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    topic = parts[1].strip() if len(parts) > 1 else ""
    if not topic:
        await update.message.reply_text("အသုံးပြုပုံ: /voiceover3 Avatar")
        return
    if not (separator and notes.strip()):
        context.user_data["pending_voiceover"] = {"title": topic, "parts": 3}
        await update.message.reply_text(
            f"{topic} အတွက် စစ်ဆေးထားသော Notes အနည်းဆုံး ၆ ကြောင်းကို နောက်မက်ဆေ့ချ်တစ်ခုဖြင့် ပို့ပါ။\n"
            "တစ်ကြောင်းစီရေးပါ။ မလုပ်တော့ပါက /cancel ပို့နိုင်ပါတယ်။"
        )
        return
    try:
        drafts = generate_voiceover_part_files(topic, notes)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    for index, draft in enumerate(drafts, start=1):
        file_obj = BytesIO(draft.encode("utf-8-sig"))
        file_obj.name = f"nexora_{topic.replace(' ', '_')}_part_{index}.txt"
        await update.message.reply_document(
            document=InputFile(file_obj, filename=file_obj.name),
            caption=f"🎙️ {topic} — Part {index}/3"
        )


async def cancel_voiceover_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    pending = context.user_data.pop("pending_voiceover", None)
    pending_profile = context.user_data.pop("pending_voice_profile", None)
    pending_backup = context.user_data.pop("pending_voice_profile_import", None)
    if pending or pending_profile or pending_backup:
        await update.message.reply_text("စောင့်ဆိုင်းနေသော Voice-over/အသံဖိုင်တင်ခြင်းကို ပယ်ဖျက်ပြီးပါပြီ။")
    else:
        await update.message.reply_text("ပယ်ဖျက်ရန် စောင့်နေသော အလုပ်မရှိပါ။")


async def voiceover_notes_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    pending = context.user_data.get("pending_voiceover")
    if not pending:
        return
    title = pending.get("title", "")
    notes = update.message.text.strip()
    try:
        drafts = generate_voiceover_part_files(title, notes)
    except ValueError as exc:
        await update.message.reply_text(f"{exc}\nNotes ကို ပြန်စစ်ပြီး ထပ်ပို့ပါ။ မလုပ်တော့ပါက /cancel ပို့ပါ။")
        return
    for index, draft in enumerate(drafts, start=1):
        file_obj = BytesIO(draft.encode("utf-8-sig"))
        file_obj.name = f"nexora_{title.replace(' ', '_')}_part_{index}.txt"
        await update.message.reply_document(document=InputFile(file_obj, filename=file_obj.name), caption=f"🎙️ {title} — Part {index}/3")
    context.user_data.pop("pending_voiceover", None)



async def recapstudio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create an original Burmese recap draft informed by metadata-only competitor research."""
    if not update.message:
        return
    title = " ".join(context.args).strip()
    if not title:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /recapstudio <နိုင်ငံခြားရုပ်ရှင်အမည်>\n"
            "ဥပမာ: /recapstudio Parasite\n"
            "TMDB/Wikidata အချက်အလက်နှင့် နိုင်ငံခြား Recap Channel metadata ကို လေ့လာပြီး "
            "ကိုယ်ပိုင်မြန်မာ Recap Draft တည်ဆောက်ပေးပါမယ်။"
        )
        return
    platform = context.user_data.get("platform", "youtube")
    duration = context.user_data.get("duration", DEFAULT_DURATIONS.get(platform, "8-10"))
    await update.message.reply_text(
        "🎬 ရုပ်ရှင်အချက်အလက်၊ နိုင်ငံခြား Recap Channel trend metadata နှင့် "
        "မူရင်းမြန်မာဇာတ်ညွှန်းကို ပြင်ဆင်နေပါတယ်..."
    )
    try:
        movie_report = await asyncio.to_thread(research_movie_sources, title)
        examples = []
        try:
            examples = await asyncio.to_thread(search_youtube_movie_recaps, title, 8)
        except YouTubeRecapResearchError as exc:
            log.info("Optional foreign recap research unavailable: %s", exc)
        notes = build_original_recap_notes(movie_report, examples)
        script = await asyncio.to_thread(
            generate_burmese_recap_script, title, notes, platform, duration
        )
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    except AIScriptError as exc:
        await update.message.reply_text(
            "Research Notes ပြင်ဆင်ပြီးပါပြီ၊ သို့သော် AI Script မထုတ်နိုင်ပါ။\n" + str(exc)
        )
        return
    except Exception:
        log.exception("Original recap studio failed")
        await update.message.reply_text("Original Recap Studio မအောင်မြင်ပါ။")
        return
    output = (
        "🎬 NEXORA ORIGINAL MYANMAR RECAP DRAFT — " + title + "\n"
        + "Platform: " + platform + " | Duration: " + str(duration) + " minutes\n"
        + "နိုင်ငံခြား Channel များမှ metadata သာလေ့လာထားပြီး Script/အသံ/Footage ကို မကူးယူထားပါ။\n\n"
        + script
        + "\n\nသတိ: ရရှိသော catalogue synopsis ထက်ကျော်လွန်သည့် scene/ending များကို "
        "မူရင်း plot source ဖြင့် ထပ်မံစစ်ဆေးပါ။ ထုတ်ဝေမီ footage အသုံးပြုခွင့်နှင့် "
        "Attribution ကို စစ်ဆေးပါ။"
    )
    for start_at in range(0, len(output), 3900):
        await update.message.reply_text(output[start_at:start_at + 3900])


async def recapchannels_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Research English-language movie recap videos; metadata only, never reuse footage."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /recapchannels <နိုင်ငံခြားရုပ်ရှင်အမည်>\n"
            "ဥပမာ: /recapchannels Parasite\n"
            "English Movie Recap Channel များကို views နှင့် relevance ဖြင့် စုစည်းပေးပါမယ်။"
        )
        return
    await update.message.reply_text(
        "နိုင်ငံခြား YouTube Movie Recap Channel များကို ခေါင်းစဉ်ကိုက်ညီမှု၊ "
        "views နှင့် တင်သည့်ရက်အလိုက် စစ်ဆေးနေပါတယ်..."
    )
    try:
        items = await asyncio.to_thread(search_youtube_movie_recaps, query, 8)
        report = format_youtube_movie_recaps(query, items)
    except YouTubeRecapResearchError as exc:
        await update.message.reply_text(str(exc))
        return
    except Exception:
        log.exception("YouTube movie recap research failed")
        await update.message.reply_text("Movie Recap Channel Research မအောင်မြင်ပါ။")
        return
    for start_at in range(0, len(report), 3900):
        await update.message.reply_text(report[start_at:start_at + 3900], disable_web_page_preview=True)


async def clipsource_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Discover reusable video records from Commons and Europeana; never scrape streaming sites."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /clipsource <Anime/ရုပ်ရှင်/Scene အမည်>\n"
            "Wikimedia Commons၊ Europeana နှင့် YouTube CC BY မှတ်တမ်းများကို ရှာပေးမည်။ YouTube ရှာရန် YOUTUBE_DATA_API_KEY လိုအပ်သည်။"
        )
        return
    await update.message.reply_text("Commons၊ Europeana နှင့် (API key ရှိပါက) YouTube CC BY မှတ်တမ်းများကို ရှာနေပါတယ်...")
    results = []
    errors = []
    try:
        commons = await asyncio.to_thread(search_licensed_video, query, 6)
        results.extend(commons)
    except ClipSourceError as exc:
        errors.append("Commons: " + str(exc))
    try:
        # Use only title aliases returned by an exact Wikidata match. If metadata
        # is unavailable, keep the original query rather than guessing aliases.
        alternate_titles = []
        metadata = await asyncio.to_thread(fetch_wikidata_metadata, query)
        if metadata.get("found"):
            alternate_titles = [
                metadata.get("title", ""),
                metadata.get("title_my", ""),
                metadata.get("enwiki_title", ""),
                metadata.get("mywiki_title", ""),
            ]
        europeana = await asyncio.to_thread(
            search_europeana_licensed_video, query, 6, alternate_titles
        )
        results.extend(europeana)
    except EuropeanaSearchError as exc:
        errors.append("Europeana: " + str(exc))
    except Exception:
        # A metadata lookup failure must not prevent the basic title search.
        try:
            europeana = await asyncio.to_thread(search_europeana_licensed_video, query, 6)
            results.extend(europeana)
        except EuropeanaSearchError as exc:
            errors.append("Europeana: " + str(exc))
    try:
        youtube_sources = await asyncio.to_thread(search_youtube_cc_videos, query, 5)
        results.extend(youtube_sources)
    except YouTubeCCSearchError as exc:
        errors.append("YouTube CC: " + str(exc))
    if not results:
        detail = ("\n" + "\n".join(errors)) if errors else ""
        await update.message.reply_text(
            "ဒီခေါင်းစဉ်နဲ့ ကိုက်ညီပြီး ခွင့်ပြုနိုင်သော လိုင်စင် metadata ရှိသည့် Video မှတ်တမ်း မတွေ့ပါ။ "
            "မသက်ဆိုင်သော footage ကို အစားထိုးမရွေးပါ။" + detail
        )
        return
    for item in results[:10]:
        title = str(item.get("title", "Untitled")).replace("File:", "")
        source_name = item.get("source", "Wikimedia Commons")
        if source_name == "YouTube":
            download_note = (
                "YouTube CC BY metadata တွေ့ရှိသည်။ Uploader က footage/audio အားလုံး၏ အခွင့်အရေးပိုင်ရှင်ဖြစ်ကြောင်း "
                "နှင့် CC BY သက်ဆိုင်မှုကို လူကိုယ်တိုင်စစ်ပါ။ NEXORA သည် YouTube stream ကို download/extract မလုပ်ပါ။ "
                "Creator ထံမှ ခွင့်ပြုထားသော မူရင်းဖိုင်ရရှိမှသာ ထုတ်လုပ်မှုတွင် ထည့်သုံးပါ။"
            )
        elif item.get("download_enabled") is False:
            download_note = "Europeana မှတ်တမ်းသာဖြစ်သည်။ မီဒီယာကို အလိုအလျောက် ဒေါင်းလုဒ်မလုပ်ပါ။ Provider စာမျက်နှာရှိ ခွင့်ပြုချက်ကို ပြန်စစ်ပါ။"
        else:
            download_note = "ထုတ်ဝေမီ လိုင်စင်နှင့် Attribution စည်းကမ်းကို ပြန်စစ်ပါ။"
        await update.message.reply_text(
            f"🎞 [{source_name}] {title}\nလိုင်စင်: {item.get('license', 'မသိရှိ')}\n"
            f"ဖန်တီးသူ: {str(item.get('artist', 'Unknown'))[:250]}\n"
            f"အသုံးပြုမှု: {str(item.get('usage_terms', ''))[:250]}\n"
            f"ရင်းမြစ်: {item.get('source_page', '')}\n"
            f"Media URL: {display_media_url(item)}\n{download_note}",
            disable_web_page_preview=True,
        )
    if errors:
        await update.message.reply_text("တချို့ရင်းမြစ်များကို မရရှိပါ:\n" + "\n".join(errors)[:900])


async def autoclip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Find a strongly title-matching reusable Commons video and render a short preview."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("အသုံးပြုပုံ: /autoclip <အမည်>\nခွင့်ပြုထားသော Commons Video ကိုသာ ရှာပြီး MP4 Preview ထုတ်ပေးပါမယ်။")
        return
    await update.message.reply_text("လိုင်စင်ရှိသော Video ကို ရှာပြီး ခေါင်းစဉ်ကိုက်ညီမှု စစ်ဆေးနေပါတယ်...")
    try:
        sources = await asyncio.to_thread(search_licensed_video, query, 8)
        source = choose_matching_source(query, sources)
        if not source:
            await update.message.reply_text(
                "ခေါင်းစဉ်နှင့် ယုံကြည်စိတ်ချရလောက်အောင် ကိုက်ညီသော CC/Public Domain Video မတွေ့ပါ။ "
                "မကိုက်ညီသော Video ကို အလိုအလျောက် မရွေးထားပါ။ /clipsource ဖြင့် ရင်းမြစ်စာရင်းကို စစ်နိုင်ပါတယ်။"
            )
            return
        import tempfile
        platform = context.user_data.get("platform", "youtube")
        with tempfile.TemporaryDirectory(prefix="nexora_autoclip_") as temp:
            output = os.path.join(temp, "nexora_licensed_preview.mp4")
            await asyncio.to_thread(render_licensed_preview, source, output, platform)
            with open(output, "rb") as video_file:
                await update.message.reply_video(
                    video=InputFile(video_file, filename="nexora_licensed_preview.mp4"),
                    supports_streaming=True,
                    caption=(
                        f"NEXORA {platform.upper()} — 45 စက္ကန့်အထိ Licensed Preview\n"
                        f"ရင်းမြစ်: {source.get('source_page', '')}\n"
                        f"လိုင်စင်: {source.get('license', '')}\n"
                        f"ဖန်တီးသူ: {str(source.get('artist', 'Unknown'))[:180]}\n"
                        "ဤ Preview သည် မူရင်းဇာတ်လမ်းအခန်းကို အတည်ပြုထားခြင်းမဟုတ်ပါ။ "
                        "ထုတ်ဝေမီ လိုင်စင်နှင့် Attribution စည်းကမ်းကို ပြန်စစ်ပါ။"
                    ),
                    read_timeout=120,
                    write_timeout=120,
                )
    except (ClipSourceError, LicensedClipError) as exc:
        await update.message.reply_text(str(exc))
    except Exception:
        log.exception("Automatic licensed clip preview failed")
        await update.message.reply_text("Licensed Preview မထုတ်နိုင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")


async def recapvideo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Render a longer creator-narrated preview using a licensed Commons source."""
    if not update.message or not update.message.text:
        return
    try:
        query, voice, script = parse_recap_video_request(update.message.text, VOICE_PRESETS)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    await update.message.reply_text("Wikidata၊ TMDB၊ AniList/Tenrai ရင်းမြစ်များမှ ခေါင်းစဉ်နှင့် မူရင်းနိုင်ငံကို စစ်ပြီး ခွင့်ပြုထားသော Commons footage ကို ရှာနေပါတယ်...")
    try:
        metadata = await asyncio.to_thread(resolve_recap_metadata, query)
        countries = validate_non_indian_wikidata_metadata(metadata)
        platform = context.user_data.get("platform", "youtube")
        plot_source = "အသုံးပြုသူပေးထားသော narration"
        if not script:
            # Prefer the exact Wikidata-linked Burmese plot section. If it is
            # absent/unusable, fall back only to the exact English sitelink.
            plot_title = metadata.get("mywiki_title")
            try:
                if not plot_title:
                    raise PlotResearchError("Wikidata မှ မြန်မာ Wikipedia sitelink မရရှိပါ။")
                plot = await asyncio.to_thread(fetch_burmese_plot_section, plot_title)
                script = generate_burmese_plot_narration(metadata, plot)
                plot_source = str(plot.get("source") or "မြန်မာ Wikipedia")
            except (PlotResearchError, ValueError) as burmese_error:
                english_title = metadata.get("enwiki_title")
                def build_catalogue_synopsis_preview():
                    # A catalogue synopsis may support a short, clearly labelled
                    # series overview. It is never represented as an episode plot
                    # or a full recap, and it is not stretched to long-form duration.
                    synopsis = (
                        metadata.get("anime_synopsis")
                        or metadata.get("tmdb_overview")
                    )
                    synopsis_url = str(metadata.get("anime_synopsis_source") or metadata.get("source") or "")
                    if not synopsis or not synopsis_url:
                        raise ValueError(
                            "မြန်မာ/English Wikipedia Plot မရရှိပါ။ AniList/TMDB မှာလည်း "
                            "အသုံးပြုနိုင်သော Series synopsis မရှိပါ။ ဇာတ်ကွက်ကို မခန့်မှန်းထားပါ။"
                        )
                    preview, synopsis_source = generate_burmese_synopsis_preview(
                        metadata.get("title", query), synopsis, synopsis_url
                    )
                    source_label = (
                        "Series synopsis အခြေခံ 1–3 မိနစ် မိတ်ဆက် Preview သာဖြစ်ပြီး "
                        "Episode/Season full recap မဟုတ်ပါ — " + synopsis_source
                    )
                    return preview, source_label

                if not english_title:
                    # AniList/Tenrai exact catalogue matches often have no
                    # Wikidata Wikipedia sitelink. Do not exit before trying
                    # the already-verified catalogue synopsis fallback.
                    script, plot_source = build_catalogue_synopsis_preview()
                    await update.message.reply_text(
                        "သတိပြုရန် — Wikipedia Plot မရရှိပါ။ အတည်ပြုနိုင်သော catalogue synopsis ကိုသာ "
                        "အသုံးပြုပြီး 1–3 မိနစ် မိတ်ဆက် Preview ထုတ်ပေးပါမည်။ Full recap မဟုတ်ပါ။"
                    )
                else:
                    try:
                        english_plot = await asyncio.to_thread(fetch_english_plot_section, english_title)
                        script, plot_source = generate_burmese_recap_from_english_plot(
                            metadata.get("title", query), english_plot, platform
                        )
                    except EnglishPlotError:
                        script, plot_source = build_catalogue_synopsis_preview()
                        await update.message.reply_text(
                            "သတိပြုရန် — Plot အပြည့်မရရှိပါ။ အတည်ပြုနိုင်သော catalogue synopsis ကိုသာ "
                            "အသုံးပြုပြီး 1–3 မိနစ် မိတ်ဆက် Preview ထုတ်ပေးပါမည်။ Full recap မဟုတ်ပါ။"
                        )
        validate_tts_request(script, voice)
        search_titles = [
            metadata.get("title", ""),
            metadata.get("enwiki_title", ""),
            metadata.get("mywiki_title", ""),
        ]
        search_titles = list(dict.fromkeys(
            " ".join(str(title).split()) for title in search_titles
            if str(title).strip()
        ))
        source_search_failed = False
        try:
            sources = await asyncio.to_thread(
                search_licensed_video, query, 10, search_titles
            )
        except ClipSourceError:
            # Original visuals are a valid fallback when Commons is unavailable.
            sources = []
            source_search_failed = True
        source = choose_matching_source(query, sources, search_titles)
        max_duration = {"tiktok": 420, "facebook": 3600, "youtube": 3600}[platform]
        await update.message.reply_text("မြန်မာ Narration + အချိန်ကိုက် SRT ပြင်ဆင်နေပါတယ်...")
        audio, srt_text = await synthesize_burmese_speech_with_srt(script, voice)
        if _subtitle_duration_seconds(srt_text) > max_duration:
            raise ValueError(f"ဒီ Platform အတွက် Narration သည် {max_duration} စက္ကန့်ထက် မကျော်ရပါ။ Script ကို အတိုချုံ့ပါ။")
        import tempfile
        if not source:
            fallback_notice = format_original_visual_fallback_notice(
                metadata.get("title", query), search_failed=source_search_failed
            )
            await update.message.reply_text(fallback_notice)
            with tempfile.TemporaryDirectory(prefix="nexora_original_recap_") as temp:
                output = os.path.join(temp, "nexora_recap_original_visuals.mp4")
                cards = await asyncio.to_thread(build_original_visual_cards, metadata.get("title", query), 8)
                await asyncio.to_thread(
                    render_slideshow, cards, ("nexora_narration.mp3", audio), output,
                    platform, ("captions.srt", srt_text.encode("utf-8-sig"))
                )
                with open(output, "rb") as video_file:
                    await update.message.reply_video(
                        video=InputFile(video_file, filename="nexora_recap_original_visuals.mp4"),
                        supports_streaming=True,
                        caption=(
                            f"NEXORA {platform.upper()} — Original Visual Recap\n"
                            f"ခေါင်းစဉ်: {metadata.get('title', query)} | နိုင်ငံ: {', '.join(countries)}\n"
                            f"ဇာတ်လမ်းရင်းမြစ်: {plot_source}\n"
                            "Visuals: NEXORA မှ ကိုယ်တိုင်ဖန်တီးထားသော Abstract Graphics ဖြစ်ပြီး "
                            "မူရင်း Anime/Film ဇာတ်ဝင်ခန်းများ မဟုတ်ပါ။\n"
                            "မြန်မာ Narration နှင့် SRT ကို MP4 ထဲတွင် ထည့်သွင်းထားသည်။"
                        ),
                        read_timeout=900,
                        write_timeout=900,
                    )
                audio_bytes, subtitle_bytes = build_recap_video_sidecars(audio, srt_text)
                voice_file = BytesIO(audio_bytes)
                voice_file.name = "nexora_recap_voiceover.mp3"
                await update.message.reply_document(
                    document=InputFile(voice_file, filename=voice_file.name),
                    caption="MP4 တွင် အသုံးပြုထားသော မြန်မာ Narration MP3 မူရင်းဖိုင်ပါ။",
                )
                subtitle_file = BytesIO(subtitle_bytes)
                subtitle_file.name = "nexora_recap_subtitles.srt"
                await update.message.reply_document(
                    document=InputFile(subtitle_file, filename=subtitle_file.name),
                    caption="မြန်မာ SRT သီးခြားဖိုင်ပါ။",
                )
            return
        await update.message.reply_text("လိုင်စင်အမျိုးအစားနှင့် ခေါင်းစဉ်ကို စစ်ပြီး licensed footage + narration + SRT + MP4 ပြင်ဆင်နေပါတယ်...")
        with tempfile.TemporaryDirectory(prefix="nexora_recap_video_") as temp:
            output = os.path.join(temp, "nexora_recap_preview.mp4")
            await asyncio.to_thread(
                render_licensed_narrated_preview, source, audio, srt_text, output, platform, max_duration
            )
            with open(output, "rb") as video_file:
                await update.message.reply_video(
                    video=InputFile(video_file, filename="nexora_recap_preview.mp4"),
                    supports_streaming=True,
                    caption=(
                        f"NEXORA {platform.upper()} — Recap Video (အများဆုံး {3 if platform == 'tiktok' else 15 if platform == 'facebook' else 20} မိနစ်)\n"
                        f"ခေါင်းစဉ်: {metadata.get('title', query)} | နိုင်ငံ: {', '.join(countries)}\n"
                        f"ဇာတ်လမ်းရင်းမြစ်: {plot_source}\n"
                        f"Footage: {source.get('source_page', '')}\n"
                        f"လိုင်စင်: {source.get('license', '')} | ဖန်တီးသူ: {str(source.get('artist', 'Unknown'))[:160]}\n"
                        "မူရင်း footage ခေါင်းစဉ် metadata ကိုသာ ကိုက်ညီစစ်ထားပြီး ဇာတ်ဝင်ခန်းအကြောင်းအရာကို အတည်မပြုထားပါ။ "
                        "ထုတ်ဝေမီ video ကို ကိုယ်တိုင်ကြည့်စစ်ပြီး Attribution/Share-Alike စည်းကမ်းလိုက်နာပါ။"
                    ),
                    read_timeout=900,
                    write_timeout=900,
                )
            try:
                audio_bytes, subtitle_bytes = build_recap_video_sidecars(audio, srt_text)
                voice_file = BytesIO(audio_bytes)
                voice_file.name = "nexora_recap_voiceover.mp3"
                await update.message.reply_document(
                    document=InputFile(voice_file, filename=voice_file.name),
                    caption="MP4 တွင် အသုံးပြုထားသော မြန်မာ Narration MP3 မူရင်းဖိုင်ပါ။",
                )
                subtitle_file = BytesIO(subtitle_bytes)
                subtitle_file.name = "nexora_recap_subtitles.srt"
                await update.message.reply_document(
                    document=InputFile(subtitle_file, filename=subtitle_file.name),
                    caption="သီးခြားပြင်ဆင်/တင်နိုင်သော မြန်မာ SRT ဖိုင်ပါ။ MP4 ထဲတွင်လည်း subtitle track ပါဝင်ပါတယ်။",
                )
            except Exception:
                log.exception("Recap video audio/subtitle sidecar delivery failed")
                await update.message.reply_text(
                    "MP4 Preview ထုတ်ပြီးပါပြီ။ MP3/SRT သီးခြားဖိုင်ပို့ရာတွင် အမှားရှိသဖြင့် MP4 ထဲရှိ subtitle track ကို အသုံးပြုပါ။"
                )
            try:
                attribution = build_licensed_attribution_note(
                    source, metadata.get("title", query), metadata.get("source", "")
                )
                credit_file = BytesIO(attribution.encode("utf-8-sig"))
                credit_file.name = "nexora_footage_attribution.txt"
                await update.message.reply_document(
                    document=InputFile(credit_file, filename=credit_file.name),
                    caption="MP4 ထဲက Footage အတွက် Attribution/လိုင်စင်စစ်ဆေးရန် မှတ်တမ်းပါ။ ထုတ်ဝေမီ Commons မှ ပြန်စစ်ပါ။",
                )
            except Exception:
                log.exception("Recap video attribution note delivery failed")
                await update.message.reply_text(
                    "MP4 Preview ထုတ်ပြီးပါပြီ။ Attribution TXT ပို့မရသဖြင့် Commons Source Page မှ Creator/License စည်းကမ်းကို ကိုယ်တိုင်မှတ်တမ်းတင်ပါ။"
                )
    except (ClipSourceError, LicensedClipError, ValueError, RuntimeError) as exc:
        await update.message.reply_text(f"Recap Video မထုတ်နိုင်ပါ: {str(exc)[:500]}")
    except Exception:
        log.exception("Automatic licensed recap video failed")
        await update.message.reply_text("Recap Video မထုတ်နိုင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")


async def autonarrateclip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Render licensed Commons footage with a creator-supplied Burmese narration."""
    if not update.message or not update.message.text:
        return
    first_line, separator, body = update.message.text.partition("\n")
    title_parts = first_line.split(maxsplit=1)
    query = title_parts[1].strip() if len(title_parts) > 1 else ""
    if not separator or not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ:\n/autonarrateclip <အမည်>\nnarrator\nမြန်မာ narration စာသား..."
        )
        return
    lines = body.strip().splitlines()
    voice = "narrator"
    if lines and lines[0].strip().lower() in VOICE_PRESETS:
        voice = lines.pop(0).strip().lower()
    script = "\n".join(lines).strip()
    if not script or len(script) > 1200:
        await update.message.reply_text("Narration စာသားသည် 1 မှ 1,200 စာလုံးအတွင်း ဖြစ်ရပါမယ်။")
        return
    await update.message.reply_text("လိုင်စင်ရှိ footage ရှာပြီး မြန်မာအသံနှင့် SRT ပြင်ဆင်နေပါတယ်...")
    try:
        sources = await asyncio.to_thread(search_licensed_video, query, 8)
        source = choose_matching_source(query, sources)
        if not source:
            await update.message.reply_text(
                "ခေါင်းစဉ်နှင့် ကိုက်ညီမှုခိုင်မာသော CC/Public Domain Video မတွေ့ပါ။ "
                "မသက်ဆိုင်သော footage ကို အစားထိုးမရွေးထားပါ။"
            )
            return
        audio, srt_text = await synthesize_burmese_speech_with_srt(script, voice)
        import tempfile
        platform = context.user_data.get("platform", "youtube")
        with tempfile.TemporaryDirectory(prefix="nexora_narrated_clip_") as temp:
            output = os.path.join(temp, "nexora_narrated_preview.mp4")
            await asyncio.to_thread(
                render_licensed_narrated_preview, source, audio, srt_text, output, platform
            )
            with open(output, "rb") as video_file:
                await update.message.reply_video(
                    video=InputFile(video_file, filename="nexora_narrated_preview.mp4"),
                    supports_streaming=True,
                    caption=(
                        f"NEXORA {platform.upper()} — မြန်မာ Narration + SRT Preview\n"
                        f"ရင်းမြစ်: {source.get('source_page', '')}\n"
                        f"လိုင်စင်: {source.get('license', '')}\n"
                        f"ဖန်တီးသူ: {str(source.get('artist', 'Unknown'))[:180]}\n"
                        "မူရင်းဗီဒီယိုအသံကို ဖယ်ထားသည်။ ခေါင်းစဉ်ကိုက်ညီမှုသာ စစ်ထားပြီး "
                        "ဇာတ်ဝင်ခန်းအကြောင်းအရာကို အတည်ပြုထားခြင်းမဟုတ်ပါ။ "
                        "Narration ကို အသုံးပြုသူက ပေးထားသည်။ ထုတ်ဝေမီ Attribution စည်းကမ်းကို စစ်ပါ။"
                    ),
                    read_timeout=120,
                    write_timeout=120,
                )
    except (ClipSourceError, LicensedClipError, ValueError, RuntimeError) as exc:
        await update.message.reply_text(f"Video မထုတ်နိုင်ပါ: {str(exc)[:500]}")
    except Exception:
        log.exception("Automatic narrated licensed preview failed")
        await update.message.reply_text("Narrated Preview မထုတ်နိုင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")


async def autofactsclip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Automatically create a short factual intro from exact metadata and reusable footage."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /autofactsclip <Anime/ရုပ်ရှင်အမည်>\n"
            "ခေါင်းစဉ်တိတိကျကျကို Wikidata မှ စစ်ပြီး CC/Public Domain footage ရှာကာ "
            "အခြေခံအချက်အလက် မြန်မာအသံ + SRT Preview ထုတ်ပေးပါမယ်။"
        )
        return
    await update.message.reply_text(
        "Wikidata အချက်အလက်စစ်ပြီး ခွင့်ပြုထားသော video ရင်းမြစ်ကို အလိုအလျောက် ရှာနေပါတယ်..."
    )
    try:
        metadata = await asyncio.to_thread(fetch_wikidata_metadata, query)
        script = generate_burmese_facts_narration(metadata)
        sources = await asyncio.to_thread(search_licensed_video, query, 10)
        source = choose_matching_source(query, sources)
        if not source:
            await update.message.reply_text(
                "ခေါင်းစဉ်နဲ့ ကိုက်ညီပြီး ပြန်လည်အသုံးပြုခွင့်ရှိတဲ့ Commons video မတွေ့ပါ။ "
                "မသက်ဆိုင်တဲ့ footage ကို အစားထိုးမရွေးထားပါ။"
            )
            return
        audio, srt_text = await synthesize_burmese_speech_with_srt(script, "narrator")
        import tempfile
        platform = context.user_data.get("platform", "youtube")
        with tempfile.TemporaryDirectory(prefix="nexora_autofacts_") as temp:
            output = os.path.join(temp, "nexora_facts_preview.mp4")
            await asyncio.to_thread(
                render_licensed_narrated_preview, source, audio, srt_text, output, platform
            )
            with open(output, "rb") as video_file:
                await update.message.reply_video(
                    video=InputFile(video_file, filename="nexora_facts_preview.mp4"),
                    supports_streaming=True,
                    caption=(
                        f"NEXORA {platform.upper()} — အလိုအလျောက် အချက်အလက်မိတ်ဆက် Preview\n"
                        f"Wikidata: {metadata.get('source', '')}\n"
                        f"Commons: {source.get('source_page', '')}\n"
                        f"လိုင်စင်: {source.get('license', '')}\n"
                        f"ဖန်တီးသူ: {str(source.get('artist', 'Unknown'))[:160]}\n"
                        "မှတ်ချက်: ဇာတ်ကွက် recap မဟုတ်ပါ။ Wikidata metadata မှ ရရှိသော "
                        "အခြေခံအချက်အလက်များသာ အသံဖတ်ထားသည်။ မူရင်းဗီဒီယိုအသံကို ဖယ်ထားပြီး "
                        "အသုံးပြုမီ လိုင်စင် Attribution စည်းကမ်းကို စစ်ပါ။"
                    ),
                    read_timeout=120,
                    write_timeout=120,
                )
    except (ValueError, ClipSourceError, LicensedClipError, RuntimeError) as exc:
        await update.message.reply_text(f"အလိုအလျောက် Preview မထုတ်နိုင်ပါ: {str(exc)[:450]}")
    except Exception:
        log.exception("Automatic facts preview failed")
        await update.message.reply_text("အချက်အလက်မိတ်ဆက် Preview မထုတ်နိုင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")



async def autoplotclip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a short recap preview only from an exact Burmese Wikipedia plot section."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /autoplotclip <Anime/ရုပ်ရှင်အမည်>\n"
            "Wikidata အမည်တိတိကျကျနှင့် မြန်မာ Wikipedia ဇာတ်လမ်းအကျဉ်း ရှိမှသာ "
            "ခွင့်ပြုထားသော footage + မြန်မာအသံ + SRT Preview ထုတ်ပေးပါမယ်။"
        )
        return
    await update.message.reply_text(
        "ခေါင်းစဉ်၊ မြန်မာဇာတ်လမ်းရင်းမြစ်နဲ့ ပြန်သုံးခွင့်ရှိတဲ့ footage ကို စစ်ဆေးနေပါတယ်..."
    )
    try:
        metadata = await asyncio.to_thread(fetch_wikidata_metadata, query)
        if not metadata.get("found"):
            raise PlotResearchError(metadata.get("status", "Wikidata မှတ်တမ်း မရရှိပါ။"))
        mywiki_title = metadata.get("mywiki_title")
        if not mywiki_title:
            raise PlotResearchError("ဒီခေါင်းစဉ်အတွက် Wikidata မှာ မြန်မာ Wikipedia ဆောင်းပါးချိတ်ဆက်ထားခြင်း မတွေ့ပါ။")
        plot = await asyncio.to_thread(fetch_burmese_plot_section, mywiki_title)
        script = generate_burmese_plot_narration(metadata, plot)
        sources = await asyncio.to_thread(search_licensed_video, query, 10)
        source = choose_matching_source(query, sources)
        if not source:
            await update.message.reply_text(
                "ဇာတ်လမ်းရင်းမြစ် ရရှိပေမဲ့ ခေါင်းစဉ်နဲ့ ကိုက်ညီပြီး ပြန်သုံးခွင့်ရှိတဲ့ Commons footage မတွေ့ပါ။ "
                "မသက်ဆိုင်တဲ့ footage ကို အစားထိုးမရွေးထားပါ။"
            )
            return
        audio, srt_text = await synthesize_burmese_speech_with_srt(script, "narrator")
        import tempfile
        platform = context.user_data.get("platform", "youtube")
        with tempfile.TemporaryDirectory(prefix="nexora_autoplot_") as temp:
            output = os.path.join(temp, "nexora_plot_preview.mp4")
            await asyncio.to_thread(
                render_licensed_narrated_preview, source, audio, srt_text, output, platform
            )
            with open(output, "rb") as video_file:
                await update.message.reply_video(
                    video=InputFile(video_file, filename="nexora_plot_preview.mp4"),
                    supports_streaming=True,
                    caption=(
                        f"NEXORA {platform.upper()} — ရင်းမြစ်အခြေပြု ဇာတ်လမ်း Preview\n"
                        f"Wikidata: {metadata.get('source', '')}\n"
                        f"မြန်မာ Wikipedia: {plot.get('source', '')}\n"
                        f"Commons: {source.get('source_page', '')}\n"
                        f"လိုင်စင်: {source.get('license', '')}\n"
                        f"ဖန်တီးသူ: {str(source.get('artist', 'Unknown'))[:160]}\n"
                        "မှတ်ချက်: ဇာတ်လမ်းစာသားကို မြန်မာ Wikipedia မှ ရယူထားပြီး လူထုတည်းဖြတ်ရင်းမြစ်ဖြစ်သည်။ "
                        "Commons footage ခေါင်းစဉ်ကိုက်ညီမှုသာ စစ်ထားပြီး တကယ့်ဇာတ်ဝင်ခန်းဟုတ်မဟုတ် မအတည်ပြုနိုင်ပါ။ "
                        "မူရင်းဗီဒီယိုအသံကို ဖယ်ထားသည်။"
                    ),
                    read_timeout=120,
                    write_timeout=120,
                )
    except (ValueError, PlotResearchError, ClipSourceError, LicensedClipError, RuntimeError) as exc:
        await update.message.reply_text(f"ရင်းမြစ်အခြေပြု Preview မထုတ်နိုင်ပါ: {str(exc)[:450]}")
    except Exception:
        log.exception("Automatic plot preview failed")
        await update.message.reply_text("ဇာတ်လမ်း Preview မထုတ်နိုင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")




async def animesynopsis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show an exact-match AniList series overview as a research lead."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("အသုံးပြုပုံ: /animesynopsis <Anime အမည်>\nAniList မှ အမည်တိတိကျကျကိုက်ညီသော series synopsis ကို ရှာပေးပါမယ်။")
        return
    await update.message.reply_text("AniList မှ Anime ခေါင်းစဉ်နှင့် synopsis ကို စစ်ဆေးနေပါတယ်...")
    result = await asyncio.to_thread(fetch_anilist_synopsis, query)
    if not result.get("found"):
        await update.message.reply_text(result.get("status", "Synopsis မရရှိပါ။"))
        return
    message = (
        f"Anime Research — {result.get('title', query)}\n"
        f"အမျိုးအစား: {result.get('format') or 'မဖော်ပြထား'} | "
        f"နှစ်: {result.get('year') or 'မဖော်ပြထား'} | "
        f"အပိုင်း: {result.get('episodes') or 'မဖော်ပြထား'}\n\n"
        f"{result['synopsis'][:2600]}\n\n"
        f"ရင်းမြစ်: {result.get('provider_url', '')}\n"
        "သတိပြုရန်: ဒီစာသားသည် AniList ရဲ့ series အဆင့် မိတ်ဆက်စာသာဖြစ်ပြီး "
        "episode တစ်ခုချင်း ဇာတ်ကွက်မဟုတ်ပါ။ မြန်မာဘာသာပြန်/အချက်အလက်စစ်ဆေးမှု မလုပ်ရသေးသဖြင့် "
        "အလိုအလျောက် recap MP4 အဖြစ် မသုံးထားပါ။"
    )
    await update.message.reply_text(message, disable_web_page_preview=True)


async def multisourceresearch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compare exact-match AniList, Tenrai/MAL and Wikidata anime metadata."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /multisourceresearch <Anime အမည်>\n"
            "AniList + Tenrai/MyAnimeList + Wikidata ကို တစ်ပြိုင်နက် စစ်ဆေးပေးပါမယ်။"
        )
        return
    await update.message.reply_text(
        "AniList၊ Tenrai/MyAnimeList နှင့် Wikidata အရင်းအမြစ်များကို "
        "တိကျသောခေါင်းစဉ်ဖြင့် တစ်ပြိုင်နက် စစ်ဆေးနေပါတယ်..."
    )
    try:
        report = await asyncio.to_thread(research_anime_sources, query)
        output = format_anime_source_report(report)
    except Exception:
        log.exception("Multi-source anime research failed")
        await update.message.reply_text("Multi-Source Research မအောင်မြင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")
        return
    for start_at in range(0, len(output), 3900):
        await update.message.reply_text(output[start_at:start_at + 3900], disable_web_page_preview=True)


async def seriesresearch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show exact-match animation series overview from TVMaze; not episode plot."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /seriesresearch <Cartoon/Donghua အမည်>\n"
            "TVmaze မှ Animation genre ပါသော Series မိတ်ဆက်စာကို ရှာပေးပါမယ်။"
        )
        return
    await update.message.reply_text("TVmaze မှ ခေါင်းစဉ်နှင့် Animation Series ရင်းမြစ်ကို စစ်ဆေးနေပါတယ်...")
    result = await asyncio.to_thread(fetch_tvmaze_synopsis, query)
    if not result.get("found"):
        await update.message.reply_text(result.get("status", "Series ရင်းမြစ် မရရှိပါ။"))
        return
    if "animation" not in [str(x).casefold() for x in result.get("genres", [])]:
        await update.message.reply_text(
            "ဒီ TVmaze မှတ်တမ်းမှာ Animation genre ကို အတည်မပြုနိုင်ပါ။ "
            "Cartoon/Donghua အဖြစ် မခန့်မှန်းထားပါ။"
        )
        return
    message = (
        f"Animation Series Research — {result.get('title', query)}\n"
        f"Genre: {', '.join(result.get('genres') or [])}\n"
        f"ထုတ်လွှင့်သည့်နေ့: {result.get('premiered') or 'မဖော်ပြထား'} | "
        f"နိုင်ငံ: {result.get('country') or 'မဖော်ပြထား'}\n\n"
        f"{result['summary'][:2500]}\n\n"
        f"ရင်းမြစ်: {result.get('provider_url', '')}\n"
        "သတိပြုရန်: TVmaze သည် community-maintained ရင်းမြစ်ဖြစ်ပြီး ဒီစာသားသည် "
        "Series မိတ်ဆက်စာသာဖြစ်သည်။ Episode recap မဟုတ်ပါ။ 2D/3D အမျိုးအစားကို "
        "TVmaze genre တစ်ခုတည်းဖြင့် မဆုံးဖြတ်ထားပါ။"
    )
    await update.message.reply_text(message, disable_web_page_preview=True)


async def moviemultisourceresearch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compare exact-match TMDB and Wikidata movie metadata."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /moviemultisourceresearch <ရုပ်ရှင်အမည်>\n"
            "TMDB + Wikidata metadata ကို တစ်ပြိုင်နက်စစ်ပေးပါမယ်။ "
            "TMDB token မရှိလျှင် Wikidata ကိုသာ ပြသပါမယ်။"
        )
        return
    await update.message.reply_text("TMDB နှင့် Wikidata ရုပ်ရှင် metadata ကို စစ်ဆေးနေပါတယ်...")
    try:
        report = await asyncio.to_thread(research_movie_sources, query)
        output = format_movie_source_report(report)
    except Exception:
        log.exception("Multi-source movie research failed")
        await update.message.reply_text("Movie Multi-Source Research မအောင်မြင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")
        return
    for start_at in range(0, len(output), 3900):
        await update.message.reply_text(output[start_at:start_at + 3900], disable_web_page_preview=True)


async def movieplotresearch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show an exact Wikidata-linked English Wikipedia movie plot section."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /movieplotresearch <နိုင်ငံခြား Live-action ရုပ်ရှင်အမည်>\n"
            "Wikidata အမည်တိတိကျကျနှင့် ချိတ်ထားသော English Wikipedia Plot section ကို ရှာပေးပါမယ်။"
        )
        return
    await update.message.reply_text("Wikidata ခေါင်းစဉ်နှင့် English Wikipedia Plot ရင်းမြစ်ကို စစ်ဆေးနေပါတယ်...")
    try:
        metadata = await asyncio.to_thread(fetch_wikidata_metadata, query)
        if not metadata.get("found"):
            await update.message.reply_text(metadata.get("status", "Wikidata မှတ်တမ်း မရရှိပါ။"))
            return
        countries = [str(x).casefold() for x in metadata.get("countries", [])]
        if not countries:
            await update.message.reply_text("မူရင်းနိုင်ငံအချက်အလက် မရှိသေးပါ။ အိန္ဒိယခေါင်းစဉ် မဟုတ်ကြောင်း မအတည်ပြုနိုင်သဖြင့် ရပ်ထားပါတယ်။")
            return
        if any("india" in x or "အိန္ဒိယ" in x for x in countries):
            await update.message.reply_text("ဒီ Project မှာ အိန္ဒိယဇာတ်ကားများ မထည့်ထားပါ။")
            return
        genres = [str(x).casefold() for x in metadata.get("genres", [])]
        description = str(metadata.get("description", "")).casefold()
        movie_markers = ("film", "movie", "motion picture")
        animation_markers = ("animation", "animated", "cartoon")
        if (
            not genres
            or not (any(marker in description for marker in movie_markers)
                    or any("film" in genre or "movie" in genre for genre in genres))
            or any(marker in description for marker in animation_markers)
            or any(any(marker in genre for marker in animation_markers) for genre in genres)
        ):
            await update.message.reply_text(
                "ဒီခေါင်းစဉ်ကို Live-action နိုင်ငံခြားရုပ်ရှင်အဖြစ် မအတည်ပြုနိုင်ပါ။ "
                "Film/Genre အချက်အလက် မပြည့်စုံခြင်း သို့မဟုတ် Animation ဖြစ်နိုင်ခြေကြောင့် ရပ်ထားပါတယ်။"
            )
            return
        enwiki_title = metadata.get("enwiki_title")
        if not enwiki_title:
            await update.message.reply_text("Wikidata မှာ English Wikipedia ဆောင်းပါးချိတ်ဆက်ထားခြင်း မတွေ့ပါ။")
            return
        plot = await asyncio.to_thread(fetch_english_plot_section, enwiki_title)
        message = (
            f"International Movie Plot Research — {metadata.get('title', query)}\n"
            f"နှစ်: {metadata.get('year') or 'မဖော်ပြထား'} | "
            f"နိုင်ငံ: {', '.join(metadata.get('countries') or [])}\n"
            f"Genre: {', '.join(metadata.get('genres') or [])}\n\n"
            f"{plot['plot_text'][:3000]}\n\n"
            f"Wikidata: {metadata.get('source', '')}\n"
            f"English Wikipedia: {plot.get('source', '')}\n"
            "သတိပြုရန်: Wikipedia သည် လူထုတည်းဖြတ်ရင်းမြစ်ဖြစ်သည်။ "
            "ဒီအကြောင်းအရာကို မြန်မာဘာသာပြန်ထားခြင်း၊ ထုတ်လုပ်သူရင်းမြစ်ဖြင့် အတည်ပြုထားခြင်း "
            "သို့မဟုတ် Recap MP4 အဖြစ် အသုံးပြုထားခြင်း မရှိသေးပါ။ Live-action အမျိုးအစားကို "
            "မူရင်းရုပ်ရှင်နှင့် ထပ်မံစစ်ဆေးပါ။"
        )
        await update.message.reply_text(message, disable_web_page_preview=True)
    except EnglishPlotError as exc:
        await update.message.reply_text(f"Plot ရင်းမြစ် မရရှိပါ: {str(exc)[:350]}")
    except Exception:
        log.exception("Movie plot research failed")
        await update.message.reply_text("Movie Plot ရင်းမြစ်ကို ယခုဖတ်မရပါ။ နောက်မှ ထပ်စမ်းပါ။")


async def animationepisodes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show brief TVMaze episode synopsis excerpts for an exact animated series."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /animationepisodes <Cartoon/Donghua အမည်>\n"
            "TVmaze မှ Animation genre ပါသော Series ရဲ့ Episode summary အတိုများကို ရှာပေးပါမယ်။"
        )
        return
    await update.message.reply_text("Animation Series ကို အတည်ပြုပြီး Episode summary ရှာနေပါတယ်...")
    result = await asyncio.to_thread(fetch_tvmaze_episode_summaries, query, 5)
    if not result.get("found"):
        await update.message.reply_text(result.get("status", "Episode ရင်းမြစ် မရရှိပါ။"))
        return
    lines = [
        f"Episode Research — {result.get('title', query)}",
        f"နိုင်ငံ: {result.get('country') or 'မဖော်ပြထား'}",
        "TVmaze ရင်းမြစ်မှ Episode summary အတိုများ (တစ်ခုလျှင် စာလုံး ၂၄၀ အထိ)။",
        "",
    ]
    for episode in result.get("episodes", []):
        season = episode.get("season") or "?"
        number = episode.get("number") or "?"
        lines.append(
            f"S{season} E{number} — {episode.get('title', 'Untitled')} "
            f"({episode.get('airdate') or 'ရက်စွဲမရှိ'})"
        )
        lines.append(episode.get("summary_excerpt", ""))
        if episode.get("source"):
            lines.append("Source: " + episode["source"])
        lines.append("")
    lines.append(
        "သတိပြုရန်: ဒီအချက်အလက်တွေဟာ TVmaze ရဲ့ community-maintained Episode summary အတိုများသာဖြစ်ပြီး "
        "အပြည့်အစုံ Recap script၊ ဇာတ်ဝင်ခန်း transcript သို့မဟုတ် အတည်ပြုပြီးဖြစ်ရပ်မှန် မဟုတ်ပါ။"
    )
    await update.message.reply_text("\n".join(lines), disable_web_page_preview=True)


async def episodeoutline_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a creator-facing outline for the highest-rated verified episode."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /episodeoutline <Anime/Cartoon/Donghua Series အမည်>\n"
            "TVmaze မှ အမည်တိတိကျကျကိုက်ညီသော non-Indian Animation Series ၏ rating အမြင့်ဆုံး Episode တစ်ခုကို "
            "ရွေးပြီး မြန်မာ Recap Worksheet ထုတ်ပေးပါမယ်။"
        )
        return
    await update.message.reply_text("Episode အချက်အလက်နှင့် Source ကို စစ်ပြီး Recap Worksheet ပြင်ဆင်နေပါတယ်...")
    try:
        research = await asyncio.to_thread(fetch_tvmaze_top_rated_episodes, query, 1)
        if not research.get("found"):
            await update.message.reply_text(research.get("status", "Episode research မရရှိပါ။"))
            return
        platform = context.user_data.get("platform", "youtube")
        duration = context.user_data.get("duration")
        worksheet = format_episode_recap_outline(research, platform, duration)
        if len(worksheet) <= 3900:
            await update.message.reply_text(worksheet, disable_web_page_preview=True)
        else:
            file_obj = BytesIO(worksheet.encode("utf-8-sig"))
            file_obj.name = "nexora_episode_recap_outline.txt"
            await update.message.reply_document(
                document=InputFile(file_obj, filename=file_obj.name),
                caption="Episode Recap Worksheet — Script ကို ကိုယ်တိုင်ရေးပြီး /recapqa ဖြင့် စစ်ဆေးနိုင်ပါတယ်။",
            )
    except ValueError as exc:
        await update.message.reply_text(str(exc)[:500])
    except Exception:
        log.exception("Episode recap outline failed")
        await update.message.reply_text("Episode Recap Worksheet မထုတ်နိုင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")


async def episodepack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Build an animated episode research brief and seek a licensed footage candidate."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /episodepack <Anime/Cartoon/Donghua Series အမည်>\n"
            "TVmaze မှ rating အမြင့်ဆုံး Episode ၅ ခုနှင့် ကိုက်ညီနိုင်သော CC/Public Domain footage ကို ရှာပေးပါမယ်။"
        )
        return
    await update.message.reply_text("Episode rating၊ ဇာတ်လမ်းအကျဉ်းနှင့် လိုင်စင်ရှိ Footage ကို စစ်ဆေးနေပါတယ်...")
    try:
        research = await asyncio.to_thread(fetch_tvmaze_top_rated_episodes, query, 5)
        if not research.get("found"):
            await update.message.reply_text(research.get("status", "Episode research မရရှိပါ။"))
            return
        candidates = []
        for episode in research.get("episodes", [])[:3]:
            episode_title = str(episode.get("title") or "").strip()
            search_query = " ".join(x for x in (research.get("title"), episode_title) if x)
            if not search_query:
                continue
            try:
                found = await asyncio.to_thread(search_licensed_video, search_query, 5)
                candidate = choose_matching_source(search_query, found)
                if candidate:
                    candidates.append(candidate)
                    break
            except ClipSourceError:
                continue
        pack = format_animated_episode_pack(research, candidates[0] if candidates else None)
        if len(pack) <= 3900:
            await update.message.reply_text(pack, disable_web_page_preview=True)
        else:
            file_obj = BytesIO(pack.encode("utf-8-sig"))
            file_obj.name = "nexora_animated_episode_pack.txt"
            await update.message.reply_document(
                document=InputFile(file_obj, filename=file_obj.name),
                caption="Episode Production Pack — အသုံးမပြုမီ Episode နှင့် Footage ကို လူကိုယ်တိုင် ပြန်စစ်ပါ။",
            )
    except ValueError as exc:
        await update.message.reply_text(str(exc)[:500])
    except Exception:
        log.exception("Animated episode pack failed")
        await update.message.reply_text("Episode Production Pack မထုတ်နိုင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")


async def topratedepisodes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show highest TVMaze community-rated episodes, not view/popularity rankings."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /topratedepisodes <Anime/Cartoon/Donghua အမည်>\n"
            "TVmaze မှ Animation genre၊ နိုင်ငံအချက်အလက်နှင့် Episode rating ရှိသော Series ကိုသာ ရှာပါမယ်။"
        )
        return
    await update.message.reply_text("Series အမည်နဲ့ Episode rating များကို စစ်ဆေးနေပါတယ်...")
    result = await asyncio.to_thread(fetch_tvmaze_top_rated_episodes, query, 5)
    if not result.get("found"):
        await update.message.reply_text(result.get("status", "Episode rating ရင်းမြစ် မရရှိပါ။"))
        return
    lines = [
        f"⭐ TVmaze Highest-Rated Episodes — {result.get('title', query)}",
        f"နိုင်ငံ: {result.get('country') or 'မဖော်ပြထား'}",
        "အောက်ပါစာရင်းသည် TVmaze community rating အလိုက် စီထားခြင်းဖြစ်သည်။",
        "၎င်းသည် View count သို့မဟုတ် လူကြိုက်များမှုစာရင်း မဟုတ်ပါ။",
        "",
    ]
    for index, episode in enumerate(result.get("episodes", []), 1):
        season = episode.get("season") or "?"
        number = episode.get("number") or "?"
        lines.append(
            f"{index}. S{season} E{number} — {episode.get('title', 'Untitled')} "
            f"| Rating: {episode.get('rating', 'N/A')}/10"
        )
        if episode.get("airdate"):
            lines.append("ထုတ်လွှင့်ရက်: " + episode["airdate"])
        if episode.get("summary_excerpt"):
            lines.append(episode["summary_excerpt"])
        if episode.get("source"):
            lines.append("Source: " + episode["source"])
        lines.append("")
    lines.append(
        "သတိပြုရန်: TVmaze rating သည် community rating ဖြစ်ပြီး view count၊ audience size သို့မဟုတ် live popularity မဟုတ်ပါ။ "
        "Rating ပေးသူအရေအတွက် မရရှိနိုင်ပါက ရမှတ်တစ်ခုတည်းဖြင့် လူကြိုက်များမှုဟု မသတ်မှတ်ပါနှင့်။ "
        "အမျိုးအစားနှင့် နိုင်ငံကို metadata ဖြင့်သာ စစ်ထားပြီး 2D/3D ကို မခန့်မှန်းပါ။"
    )
    await update.message.reply_text("\n".join(lines), disable_web_page_preview=True)


async def render_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    action = context.args[0].lower() if context.args else "start"
    if action == "cancel":
        context.user_data.pop("video_render", None)
        await update.message.reply_text("Video ပြင်ဆင်မှုကို ပယ်ဖျက်ပြီးပါပြီ။")
        return
    if action == "finish":
        session = context.user_data.get("video_render")
        if not session:
            await update.message.reply_text("/render ဖြင့် Video session စတင်ပါ။")
            return
        is_timeline = session.get("mode") == "timeline"
        scenes = session.get("scenes", [])
        if is_timeline:
            if not scenes or any(not scene.get("image") or not scene.get("audio") for scene in scenes):
                await update.message.reply_text("Scene တစ်ခုစီမှာ ပုံနဲ့ အသံ နှစ်မျိုးလုံး ထည့်ပြီးမှ /render finish ပို့ပါ။")
                return
        elif not session.get("images") or not (session.get("audio") or session.get("audio_tracks")):
            await update.message.reply_text("ပုံအနည်းဆုံး ၁ ပုံနဲ့ အသံဖိုင်/Voice Profile အနည်းဆုံး ၁ ခု လိုပါတယ်။ /render ဖြင့် ပြန်စပါ။")
            return
        await update.message.reply_text("MP4 ထုတ်လုပ်နေပါတယ်။ ခဏစောင့်ပါ...")
        import tempfile
        try:
            with tempfile.TemporaryDirectory(prefix="nexora_video_") as temp:
                output = os.path.join(temp, "nexora_video.mp4")
                if is_timeline:
                    await asyncio.to_thread(render_scene_timeline, scenes, output, session.get("platform", "youtube"), session.get("subtitle"))
                else:
                    audio_input = session["audio_tracks"] if session.get("audio_tracks") else session["audio"]
                    await asyncio.to_thread(render_slideshow, session["images"], audio_input, output, session.get("platform", "youtube"), session.get("subtitle"))
                with open(output, "rb") as video_file:
                    await update.message.reply_video(
                        video=InputFile(video_file, filename="nexora_video.mp4"),
                        supports_streaming=True,
                        caption=f"NEXORA {session.get('platform', 'youtube').upper()} MP4 ပြီးပါပြီ။ " + ("မြန်မာစာတန်းထိုး ထည့်သွင်းထားပါတယ်။ " if session.get("subtitle") else "") + "အသုံးပြုခွင့်ရှိသော ပုံ/အသံများကိုသာ ထည့်သုံးပါ။",
                        read_timeout=120,
                        write_timeout=120,
                    )
        except VideoRenderError as exc:
            await update.message.reply_text(str(exc))
        except Exception:
            log.exception("Video render delivery failed")
            await update.message.reply_text("MP4 ပို့မရပါ။ ပိုသေးသောဖိုင်များဖြင့် ထပ်စမ်းပါ။")
        finally:
            context.user_data.pop("video_render", None)
        return
    if action == "timeline":
        platform = context.user_data.get("platform", "youtube")
        context.user_data["video_render"] = {"mode": "timeline", "scenes": [], "active_scene": None, "platform": platform}
        await update.message.reply_text(
            f"Scene Timeline စတင်ပါပြီ။ Platform: {PLATFORM_NAMES.get(platform, platform)}\n"
            "Scene အသစ်တစ်ခုစီအတွက် /render scene <အမည်> ပို့ပါ။ ပြီးလျှင် အဲဒီ Scene ရဲ့ ပုံတစ်ပုံနဲ့ Narration အသံဖိုင်တစ်ခုစီ ပို့ပါ။\n"
            "Scene များကို အစဉ်လိုက် ပေါင်းမည်။ Scene တစ်ခု၏ ပုံသည် ၎င်း Scene အသံကြာချိန်အတိုင်း ပြမည်။ အများဆုံး ၁၂ Scene။\n"
            "စာတန်းထိုးလိုပါက .srt ဖိုင်ပို့ပါ။ အားလုံးပြီးလျှင် /render finish ပို့ပါ။ /render cancel ဖြင့် ပယ်ဖျက်နိုင်သည်။"
        )
        return
    if action == "scene":
        session = context.user_data.get("video_render")
        title = " ".join(context.args[1:]).strip()
        if not session or session.get("mode") != "timeline":
            await update.message.reply_text("အရင်ဆုံး /render timeline ပို့ပါ။")
            return
        if not title:
            await update.message.reply_text("အသုံးပြုပုံ: /render scene <အခန်းအမည်>")
            return
        if len(session["scenes"]) >= 12:
            await update.message.reply_text("Scene ၁၂ ခု ပြည့်ပါပြီ။")
            return
        session["scenes"].append({"title": title[:80], "image": None, "audio": None})
        session["active_scene"] = len(session["scenes"]) - 1
        await update.message.reply_text(f"Scene {len(session['scenes'])}: {title[:80]} ဖန်တီးပြီးပါပြီ။ ဒီ Scene အတွက် ပုံတစ်ပုံနဲ့ အသံတစ်ခု ပို့ပါ။")
        return
    if action == "voice":
        session = context.user_data.get("video_render")
        if not session:
            await update.message.reply_text("အရင်ဆုံး /render ပို့ပြီး Video session စတင်ပါ။")
            return
        if len(context.args) < 2:
            await update.message.reply_text("အသုံးပြုပုံ: /render voice <profile အမည်>")
            return
        try:
            profile_name = normalize_profile_name(" ".join(context.args[1:]))
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return
        try:
            profiles = load_voice_profiles(update.effective_user.id)
            context.user_data["custom_voice_profiles"] = profiles
        except (OSError, ValueError) as exc:
            await update.message.reply_text(f"Voice Storage ကို ဖတ်မရပါ: {exc}")
            return
        profile = profiles.get(profile_name)
        if not profile:
            await update.message.reply_text("အဲဒီ Voice Profile မတွေ့ပါ။ /voiceprofile list ဖြင့် စစ်ပါ။")
            return
        if session.get("mode") == "timeline":
            active = session.get("active_scene")
            if active is None or session["scenes"][active].get("audio"):
                await update.message.reply_text("Voice Profile မထည့်မီ /render scene <အမည်> ဖြင့် Scene အသစ်ဖွင့်ပါ။")
                return
            session["scenes"][active]["audio"] = (profile["filename"], profile["audio"])
            await update.message.reply_text(f"Scene {active + 1} အတွက် Voice Profile အသံ ထည့်ပြီးပါပြီ။")
            return
        tracks = session.setdefault("audio_tracks", [])
        if len(tracks) >= 12:
            await update.message.reply_text("Voice Track ၁၂ ခု ပြည့်ပါပြီ။")
            return
        tracks.append((profile["filename"], profile["audio"]))
        await update.message.reply_text(f"{profile_name} အသံ Track ထည့်ပြီးပါပြီ။ လက်ရှိ Track {len(tracks)}/12။ ထပ်ထည့်ရန် /render voice <အမည်> ကို သုံးပါ။")
        return
    platform = context.user_data.get("platform", "youtube")
    context.user_data["video_render"] = {"images": [], "audio": None, "audio_tracks": [], "platform": platform}
    await update.message.reply_text(
        f"Video ဖန်တီးမှု စတင်ပါပြီ။\nPlatform: {PLATFORM_NAMES.get(platform, platform)}\n"
        "၁) ပုံ JPG/PNG/WEBP အများဆုံး ၁၂ ပုံ ပို့ပါ။\n"
        "၂) Narration အသံဖိုင် ပို့ပါ၊ သို့မဟုတ် /render voice <profile အမည်> ဖြင့် သိမ်းထားသော အသံ Track များရွေးပါ။\n"
        "၃) Voice Track များကို အစဉ်လိုက် ပေါင်းစပ်မည်။ Track စုစုပေါင်း ၂၀ MB/၁၀ မိနစ်အောက် ဖြစ်ရပါမယ်။\n"
        "၄) မြန်မာစာတန်းထိုးလိုပါက .srt ဖိုင် (၁ MB အောက်) ပို့ပါ။ MP4 ထဲတွင် ရွေးဖွင့်နိုင်သော Subtitle Track အဖြစ် ထည့်ပေးမည်။\n"
        "၅) ပြီးရင် /render finish ပို့ပါ။ မလုပ်တော့ပါက /render cancel ပို့ပါ။\n"
        "ကိုယ်ပိုင် သို့မဟုတ် အသုံးပြုခွင့်ရှိသော ပုံ/အသံကိုသာ သုံးပါ။"
    )


async def send_voice_profile_backup(update: Update, profiles: dict, reason: str):
    """Send a fresh ZIP to the user's Telegram chat as a free off-container backup."""
    if not update.message:
        return
    try:
        backup = export_voice_profile_backup(profiles)
        file_obj = BytesIO(backup)
        file_obj.name = "nexora_voice_profiles_latest.zip"
        await update.message.reply_document(
            document=InputFile(file_obj, filename=file_obj.name),
            caption=(
                "NEXORA Voice Profile အလိုအလျောက် Backup (" + reason + ")။\n"
                "Render Free မှာ ဒီ ZIP ကို Telegram ထဲ လုံခြုံစွာထားပါ။ "
                "Service restart/redeploy ပြီး Profile များမရှိတော့လျှင် "
                "/voiceprofile import ပို့ပြီး ဒီ ZIP ကို ပြန်ပို့ပါ။ "
                "အသံဖိုင်ပါဝင်သောကြောင့် အခြားသူများထံ မမျှဝေပါနှင့်။"
            ),
        )
    except (VoiceProfileBackupError, OSError) as exc:
        await update.message.reply_text(
            "Profile သိမ်းပြီးပါပြီ၊ သို့သော် Telegram Backup မပို့နိုင်ပါ။ "
            f"/voiceprofile export ဖြင့် ကိုယ်တိုင် Backup လုပ်ပါ။ ({exc})"
        )


async def voiceprofile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    args = context.args
    try:
        profiles = load_voice_profiles(update.effective_user.id)
    except (OSError, ValueError) as exc:
        await update.message.reply_text(f"Voice Storage ကို ဖတ်မရပါ: {exc}")
        return
    context.user_data["custom_voice_profiles"] = profiles
    if not args:
        await update.message.reply_text("အသုံးပြုပုံ: /voiceprofile <အမည်> ပြီးနောက် ကိုယ်ပိုင် MP3/M4A/WAV/OGG အသံဖိုင် ပို့ပါ။\n/voiceprofile list\n/voiceprofile delete <အမည်>\n/voiceprofile export\n/voiceprofile import")
        return
    if args[0].lower() == "export":
        try:
            backup = export_voice_profile_backup(profiles)
        except VoiceProfileBackupError as exc:
            await update.message.reply_text(str(exc))
            return
        file_obj = BytesIO(backup)
        file_obj.name = "nexora_voice_profiles.zip"
        await update.message.reply_document(
            document=InputFile(file_obj, filename=file_obj.name),
            caption="NEXORA Voice Profile Backup။ ကိုယ်ပိုင်အသံဖိုင်များပါဝင်သောကြောင့် လုံခြုံစွာ သိမ်းဆည်းပါ။"
        )
        return
    if args[0].lower() == "import":
        context.user_data["pending_voice_profile_import"] = True
        await update.message.reply_text("NEXORA မှ Export လုပ်ထားသော voice profile ZIP ဖိုင်ကို ပို့ပါ။ လက်ရှိ Profile များနှင့် ပေါင်းထည့်မည်။ မလုပ်တော့ပါက /cancel ပို့ပါ။")
        return
    if args[0].lower() == "list":
        names = list(profiles)
        await update.message.reply_text("သိမ်းထားသောအသံများ: " + (", ".join(names) if names else "မရှိသေးပါ") + "\nPersistent Disk ချိတ်ပြီး VOICE_PROFILE_DB_PATH သတ်မှတ်ထားမှ Restart ပြီးနောက်လည်း မပျောက်ပါ။ TTS voice cloning မဟုတ်ပါ။")
        return
    if args[0].lower() == "delete":
        try:
            name = normalize_profile_name(" ".join(args[1:]))
            delete_voice_profile(profiles, name)
            save_voice_profiles(update.effective_user.id, profiles)
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return
        await update.message.reply_text("အသံ Profile ကို ဖျက်ပြီးပါပြီ။")
        await send_voice_profile_backup(update, profiles, "ဖျက်ပြီးနောက်")
        return
    try:
        name = normalize_profile_name(" ".join(args))
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    context.user_data["pending_voice_profile"] = name
    await update.message.reply_text(f"{name} အတွက် ကိုယ်ပိုင်အသံ MP3/M4A/WAV/OGG ဖိုင် (၂၀ MB အောက်) ပို့ပါ။ မလုပ်တော့ပါက /cancel ပို့ပါ။")


async def video_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    message = update.message
    pending_backup = context.user_data.get("pending_voice_profile_import")
    if pending_backup and message.document:
        filename = message.document.file_name or ""
        if not filename.lower().endswith(".zip"):
            await message.reply_text("ZIP Backup ဖိုင်သာ လက်ခံပါတယ်။")
            return
        if (message.document.file_size or 0) > MAX_BACKUP_BYTES:
            await message.reply_text("Backup ZIP သည် ၄၁ MB အောက် ဖြစ်ရပါမယ်။")
            return
        media_file = await message.document.get_file()
        buffer = BytesIO()
        await media_file.download_to_memory(out=buffer)
        try:
            restored = import_voice_profile_backup(
                buffer.getvalue(),
                context.user_data.setdefault("custom_voice_profiles", {}),
            )
        except VoiceProfileBackupError as exc:
            await message.reply_text(str(exc))
            return
        try:
            save_voice_profiles(update.effective_user.id, restored)
        except (OSError, ValueError) as exc:
            await message.reply_text(f"Voice Profile ကို အမြဲတမ်းသိမ်းမရပါ: {exc}")
            return
        context.user_data["custom_voice_profiles"] = restored
        context.user_data.pop("pending_voice_profile_import", None)
        await message.reply_text(f"Voice Profile Backup ပြန်သွင်းပြီးပါပြီ။ လက်ရှိ Profile {len(restored)} ခု ရှိပါတယ်။")
        await send_voice_profile_backup(update, restored, "ပြန်သွင်းပြီးနောက်")
        return
    pending = context.user_data.get("pending_voice_profile")
    if pending and (message.audio or message.voice or message.document):
        media = message.audio or message.voice or message.document
        filename_in = getattr(media, "file_name", None) or ("voice_profile.ogg" if message.voice else "voice_profile.mp3")
        media_file = await media.get_file()
        if (getattr(media_file, "file_size", 0) or 0) > 20 * 1024 * 1024:
            await message.reply_text("အသံဖိုင်သည် ၂၀ MB အောက် ဖြစ်ရပါမယ်။")
            return
        buffer = BytesIO()
        await media_file.download_to_memory(out=buffer)
        filename = filename_in
        try:
            profiles = load_voice_profiles(update.effective_user.id)
            store_voice_profile(profiles, pending, filename, buffer.getvalue())
            save_voice_profiles(update.effective_user.id, profiles)
            context.user_data["custom_voice_profiles"] = profiles
        except ValueError as exc:
            await message.reply_text(str(exc))
            return
        context.user_data.pop("pending_voice_profile", None)
        await message.reply_text(f"{pending} အသံဖိုင် သိမ်းပြီးပါပြီ။ /voiceprofile list ဖြင့် ကြည့်နိုင်ပါတယ်။ ဒီဖိုင်သည် အသံသွင်းထားသော narration ကို တိုက်ရိုက်ပြန်သုံးရန်ဖြစ်ပြီး စာသားအသစ်ကို TTS ပြောင်းပေးခြင်း မဟုတ်ပါ။")
        await send_voice_profile_backup(update, profiles, "Profile အသစ်သိမ်းပြီးနောက်")
        return
    session = context.user_data.get("video_render")
    if session is None:
        return
    media_file = None
    filename = ""
    kind = ""
    if message.photo:
        media_file = await message.photo[-1].get_file()
        filename, kind = f"photo_{len(session['images']) + 1}.jpg", "image"
    elif message.audio:
        media_file = await message.audio.get_file()
        filename = message.audio.file_name or "narration.mp3"
        kind = "audio"
    elif message.voice:
        media_file = await message.voice.get_file()
        filename, kind = "narration.ogg", "audio"
    if media_file is None and message.document and (message.document.file_name or "").lower().endswith(".srt"):
        media_file = await message.document.get_file()
        filename, kind = message.document.file_name or "captions.srt", "subtitle"
    if media_file is None:
        return
    size = getattr(media_file, "file_size", 0) or 0
    limit = 20 * 1024 * 1024 if kind == "audio" else (1024 * 1024 if kind == "subtitle" else 8 * 1024 * 1024)
    if size > limit:
        await message.reply_text("ဖိုင်အရွယ်အစား ကြီးနေပါတယ်။ ပိုသေးတဲ့ဖိုင်သုံးပါ။")
        return
    buffer = BytesIO()
    await media_file.download_to_memory(out=buffer)
    data = buffer.getvalue()
    if kind == "subtitle":
        session["subtitle"] = (filename, data)
        await message.reply_text("မြန်မာစာတန်းထိုး SRT လက်ခံပြီးပါပြီ။ /render finish ဖြင့် MP4 ထုတ်နိုင်ပါပြီ။")
    elif kind == "image":
        if session.get("mode") == "timeline":
            active = session.get("active_scene")
            if active is None:
                await message.reply_text("အရင်ဆုံး /render scene <အမည်> ဖြင့် Scene ဖွင့်ပါ။")
                return
            if session["scenes"][active].get("image"):
                await message.reply_text("ဒီ Scene မှာ ပုံရှိပြီးပါပြီ။ နောက် Scene အတွက် /render scene <အမည်> ပို့ပါ။")
                return
            session["scenes"][active]["image"] = (filename, data)
            await message.reply_text(f"Scene {active + 1} ပုံ လက်ခံပြီးပါပြီ။")
            return
        if len(session["images"]) >= 12:
            await message.reply_text("ပုံ ၁၂ ပုံ ပြည့်ပါပြီ။ /render finish ပို့ပါ။")
            return
        session["images"].append((filename, data))
        await message.reply_text(f"ပုံ {len(session['images'])}/12 လက်ခံပြီးပါပြီ။")
    else:
        if len(data) > 20 * 1024 * 1024:
            await message.reply_text("အသံဖိုင်သည် ၂၀ MB အောက် ဖြစ်ရပါမယ်။")
            return
        if session.get("mode") == "timeline":
            active = session.get("active_scene")
            if active is None:
                await message.reply_text("အရင်ဆုံး /render scene <အမည်> ဖြင့် Scene ဖွင့်ပါ။")
                return
            if session["scenes"][active].get("audio"):
                await message.reply_text("ဒီ Scene မှာ အသံရှိပြီးပါပြီ။ နောက် Scene အတွက် /render scene <အမည်> ပို့ပါ။")
                return
            session["scenes"][active]["audio"] = (filename, data)
            await message.reply_text(f"Scene {active + 1} အသံ လက်ခံပြီးပါပြီ။ နောက် Scene အတွက် /render scene <အမည်> ပို့နိုင်ပါပြီ။")
            return
        session["audio"] = (filename, data)
        await message.reply_text("Narration အသံဖိုင် လက်ခံပြီးပါပြီ။ /render finish ပို့နိုင်ပါပြီ။")


async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /create ဇာတ်ကားအမည် သို့မဟုတ် အကြောင်းအရာ"
        )
        return
    platform = context.user_data.get("platform", "youtube")
    duration = context.user_data.get("duration", DEFAULT_DURATIONS[platform])
    if duration not in PLATFORM_DURATIONS[platform]:
        duration = DEFAULT_DURATIONS[platform]
        context.user_data["duration"] = duration
    outline = generate_recap_outline(topic, platform=platform, duration=duration)
    for start_at in range(0, len(outline), 3900):
        await update.message.reply_text(outline[start_at:start_at + 3900])




async def aiscript_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    first_line, separator, notes = update.message.text.partition("\n")
    title_parts = first_line.split(maxsplit=1)
    if len(title_parts) < 2 or not separator:
        await update.message.reply_text("အသုံးပြုပုံ: /aiscript <title> ပြီးနောက် စာကြောင်းအသစ်မှ Verified Research Notes ထည့်ပါ။")
        return
    title = title_parts[1].strip()
    platform = context.user_data.get("platform", "youtube")
    duration = context.user_data.get("duration", DEFAULT_DURATIONS.get(platform, "8-10"))
    await update.message.reply_text("OpenAI Script Draft တောင်းဆိုမှု လက်ခံပါပြီ။")
    try:
        script = await asyncio.to_thread(generate_burmese_recap_script, title, notes, platform, duration)
    except AIScriptError as exc:
        error_text = str(exc)
        if "Limit/Quota" in error_text:
            # A quota failure must not trigger another paid API call. Fall back to
            # the deterministic, non-AI worksheet using only creator-supplied notes.
            try:
                worksheet = generate_draft_worksheet(
                    title, notes, platform=platform, duration=duration
                )
            except ValueError as fallback_error:
                await update.message.reply_text(
                    error_text + "\n\nFree Builder သို့ အလိုအလျောက်ပြောင်းရန် မအောင်မြင်ပါ: "
                    + str(fallback_error)
                )
                return
            output = (
                "NEXORA Free Builder Worksheet — " + title + "\n\n"
                "OpenAI Quota ပြည့်နေသောကြောင့် အခပေး API ကို ထပ်မခေါ်ထားပါ။ "
                "အောက်ပါသည် AI ရေးသားထားသော Script မဟုတ်ဘဲ သင်ပေးထားသော Notes ကိုသာ "
                "အသုံးပြုသည့် အခမဲ့ အခန်းလိုက် Worksheet ဖြစ်သည်။\n\n"
                + worksheet
            )
            for start_at in range(0, len(output), 3900):
                await update.message.reply_text(output[start_at:start_at + 3900])
            return
        await update.message.reply_text(error_text)
        return
    except Exception:
        log.exception("OpenAI script generation failed")
        await update.message.reply_text("AI Script ထုတ်လုပ်မှု မအောင်မြင်ပါ။")
        return
    output = "NEXORA AI Script Draft — " + title + "\n\n" + script + "\n\nထုတ်ဝေမီ Source များကို ပြန်စစ်ပါ။"
    for start_at in range(0, len(output), 3900):
        await update.message.reply_text(output[start_at:start_at + 3900])


async def platform_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    choice = context.args[0].lower() if context.args else ""
    if choice not in PLATFORM_NAMES:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /platform youtube | tiktok | facebook"
        )
        return
    context.user_data["platform"] = choice
    current = context.user_data.get("duration")
    if current not in PLATFORM_DURATIONS[choice]:
        context.user_data["duration"] = DEFAULT_DURATIONS[choice]
    options = ", ".join(PLATFORM_DURATIONS[choice])
    await update.message.reply_text(
        f"Platform ကို {PLATFORM_NAMES[choice]} အဖြစ် ရွေးပြီးပါပြီ။\n"
        f"ရနိုင်သောကြာချိန်: {options}\n"
        f"Default: {DEFAULT_DURATIONS[choice]} မိနစ်"
    )


async def duration_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    platform = context.user_data.get("platform", "youtube")
    choice = context.args[0] if context.args else ""
    if choice not in PLATFORM_DURATIONS[platform]:
        options = ", ".join(PLATFORM_DURATIONS[platform])
        await update.message.reply_text(
            f"အသုံးပြုပုံ: /duration 15-20\n{PLATFORM_NAMES[platform]} အတွက် ရနိုင်သောကြာချိန်: {options}"
        )
        return
    context.user_data["duration"] = choice
    await update.message.reply_text(
        f"ရည်မှန်းကြာချိန် {DURATION_PRESETS[choice]} မိနစ်ကို ရွေးပြီးပါပြီ။"
    )


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    platform = context.user_data.get("platform", "youtube")
    duration = context.user_data.get("duration", DEFAULT_DURATIONS[platform])
    await update.message.reply_text(
        f"လက်ရှိရွေးချယ်မှု\nPlatform: {PLATFORM_NAMES[platform]}\n"
        f"ကြာချိန်: {DURATION_PRESETS.get(duration, duration)} မိနစ်\n"
        "ပြောင်းရန် /platform နှင့် /duration ကို အသုံးပြုပါ။"
    )

async def mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    choice = context.args[0].lower() if context.args else ""
    if choice not in {"free", "ai"}:
        await update.message.reply_text("အသုံးပြုပုံ: /mode free သို့မဟုတ် /mode ai")
        return
    context.user_data["mode"] = choice
    if choice == "ai":
        await update.message.reply_text(
            "AI Mode ကို ရွေးထားပါတယ်။ လက်ရှိမှာ သတ်မှတ်ချက်နှင့်ကိုက်ညီသော AI ဝန်ဆောင်မှု မချိတ်ထားသေးပါ။ "
            "အခပေး API ကို အလိုအလျောက် မသုံးပါ။ /create ကို Free Builder ဖြင့် ဆက်လုပ်နိုင်ပါတယ်။"
        )
    else:
        await update.message.reply_text("Free Mode ဖွင့်ပြီးပါပြီ။ API key မလိုပါ။")


async def srt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    raw = update.message.text.partition("\n")[2].strip()
    if not raw:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /srt ပြီးနောက် စာကြောင်းတစ်ကြောင်းစီ ထည့်ပါ။\n"
            "00:00:00,000 --> 00:00:05,000 | Welcome to the story.\n"
            "00:00:05,000 --> 00:00:10,000 | The journey begins."
        )
        return
    try:
        srt_text = build_srt(raw)
    except ValueError as exc:
        await update.message.reply_text(f"စာတန်းထိုးပုံစံ မမှန်ပါ: {exc}")
        return
    file_obj = BytesIO(srt_text.encode("utf-8-sig"))
    file_obj.name = "nexora_english_subtitles.srt"
    await update.message.reply_document(
        document=InputFile(file_obj, filename=file_obj.name),
        caption="NEXORA English Subtitle SRT ဖိုင်"
    )

async def tts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a Burmese MP3 using the online neural TTS service."""
    if not update.message or not update.message.text:
        return
    first_line, separator, script = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    voice = parts[1].strip().lower() if len(parts) > 1 else ""
    if not separator or not script.strip() or voice not in VOICE_PRESETS:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /tts narrator သို့ /tts hero\n"
            "အသံပုံစံစာရင်းအတွက် /voices ကို သုံးပါ။"
        )
        return
    try:
        validate_tts_request(script, voice)
        await update.message.reply_text("မြန်မာ MP3 အသံဖိုင် ဖန်တီးနေပါတယ်။ ခဏစောင့်ပါ...")
        audio = await synthesize_burmese_speech(script, voice)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    except RuntimeError as exc:
        await update.message.reply_text(str(exc))
        return
    file_obj = BytesIO(audio)
    file_obj.name = "nexora_burmese_voiceover.mp3"
    await update.message.reply_document(
        document=InputFile(file_obj, filename=file_obj.name),
        caption=(
            "မြန်မာ Voice-over MP3 ဖိုင်ပါ။ မထုတ်ဝေမီ အသံထွက်၊ အမည်အသံထွက်နှင့် "
            "အသံအရည်အသွေးကို ပြန်စစ်ပါ။"
        ),
        read_timeout=60,
        write_timeout=60,
    )



async def voicedemo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a short audition clip for one available Burmese delivery preset."""
    if not update.message or not update.message.text:
        return
    parts = update.message.text.split(maxsplit=1)
    preset = parts[1].strip().lower() if len(parts) > 1 else ""
    if preset not in VOICE_PRESETS:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /voicedemo <preset>\n"
            "ဥပမာ: /voicedemo narrator\n"
            "ရွေးချယ်စရာများ: " + ", ".join(VOICE_PRESETS) +
            "\nအသံအခြေခံ Nilar/Thiha နှစ်မျိုးသာဖြစ်ပြီး preset သည် ပြောဟန်ပြောင်းပေးခြင်းသာ ဖြစ်ပါတယ်။"
        )
        return
    sample = (
        "ဒီနေ့ ဇာတ်လမ်းထဲမှာ မမျှော်လင့်ထားတဲ့ အဖြစ်အပျက်တစ်ခု ဖြစ်လာတော့မယ်။ "
        "သူတို့ရဲ့ ဆုံးဖြတ်ချက်က အရာအားလုံးကို ပြောင်းလဲသွားစေနိုင်ပါတယ်။"
    )
    try:
        await update.message.reply_text(
            f"{VOICE_PRESETS[preset]['label']} အသံပုံစံကို စမ်းသပ်ဖန်တီးနေပါတယ်..."
        )
        audio = await synthesize_burmese_speech(sample, preset)
    except (ValueError, RuntimeError) as exc:
        await update.message.reply_text(f"အသံနမူနာ မဖန်တီးနိုင်ပါ: {exc}")
        return
    file_obj = BytesIO(audio)
    file_obj.name = f"nexora_voice_demo_{preset}.mp3"
    await update.message.reply_audio(
        audio=InputFile(file_obj, filename=file_obj.name),
        title=f"NEXORA Voice Demo — {preset}",
        caption=(
            f"Preset: {preset} — {VOICE_PRESETS[preset]['label']}\n"
            f"Base voice: {'Nilar' if VOICE_PRESETS[preset]['voice'] == 'female' else 'Thiha'}။ "
            "ဤသည် အသံပုံစံစမ်းသပ်နမူနာဖြစ်ပြီး သရုပ်ဆောင်အသစ်တစ်ဦး၏ အသံမဟုတ်ပါ။"
        ),
    )



async def ttsdesign_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a fictional Burmese character voice with optional VoxCPM2."""
    if not update.message or not update.message.text:
        return
    first_line, separator, script = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    voice = parts[1].strip().lower() if len(parts) > 1 else ""
    if not separator or not script.strip() or voice not in VOICE_DESIGNS:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /tts_design <voice_name> ပြီးနောက် စာကြောင်းအသစ်မှ ဇာတ်ညွှန်းထည့်ပါ။\n"
            "Voice အသစ်ဒီဇိုင်းများ: " + ", ".join(VOICE_DESIGNS) + "\n"
            "ဤအသံများသည် AI ဖန်တီးထားသော စိတ်ကူးယဉ်အသံများဖြစ်ပြီး တကယ့်လူတစ်ဦး၏အသံကို မကူးယူပါ။"
        )
        return
    await update.message.reply_text(
        f"{VOICE_DESIGNS[voice]['label']} AI အသံကို ဖန်တီးနေပါတယ်။ ပထမဆုံးအကြိမ်တွင် model download လုပ်ရနိုင်ပါတယ်..."
    )
    try:
        audio = await synthesize_designed_burmese_voice(script, voice)
    except (ValueError, RuntimeError) as exc:
        await update.message.reply_text(str(exc))
        return
    file_obj = BytesIO(audio)
    file_obj.name = f"nexora_designed_voice_{voice}.wav"
    await update.message.reply_document(
        document=InputFile(file_obj, filename=file_obj.name),
        caption=(
            f"AI Voice Design: {VOICE_DESIGNS[voice]['label']}\n"
            "စိတ်ကူးယဉ် synthetic voice ဖြစ်ပြီး တကယ့်အသံရှင်တစ်ဦးကို ကိုယ်စားမပြုပါ။"
        ),
        read_timeout=120,
        write_timeout=120,
    )


async def ttslocal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a WAV using the optional local MyanmarTTS model."""
    if not update.message or not update.message.text:
        return
    script = update.message.text.partition("\n")[2].strip()
    if not script:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /tts_local ပြီးနောက် မြန်မာစာသားကို စာကြောင်းအသစ်မှ ထည့်ပါ။\n"
            "ဒီစနစ်သည် စမ်းသပ်ဆဲ Local TTS ဖြစ်ပြီး စာသား ၁,၂၀၀ အောက်သာ လက်ခံပါတယ်။"
        )
        return
    await update.message.reply_text(
        "Local MyanmarTTS ဖြင့် WAV အသံဖန်တီးနေပါတယ်။ ပထမဆုံးအကြိမ်မှာ မော်ဒယ်ဖိုင်များကို host ထဲ download လုပ်ရနိုင်ပြီး ခဏကြာနိုင်ပါတယ်..."
    )
    try:
        audio = await synthesize_local_burmese_speech(script)
    except (ValueError, RuntimeError) as exc:
        await update.message.reply_text(str(exc))
        return
    file_obj = BytesIO(audio)
    file_obj.name = "nexora_local_myanmar_tts.wav"
    await update.message.reply_document(
        document=InputFile(file_obj, filename=file_obj.name),
        caption="Local MyanmarTTS မှ ထုတ်ထားသော WAV ဖိုင်ပါ။ အသံထွက်နှင့် အရည်အသွေးကို ပြန်စစ်ပါ။"
    )


async def ttssrt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate Burmese MP3 and word-aligned SRT together."""
    if not update.message or not update.message.text:
        return
    first_line, separator, script = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    voice = parts[1].strip().lower() if len(parts) > 1 else ""
    if not separator or not script.strip() or voice not in VOICE_PRESETS:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /ttssrt narrator သို့ /ttssrt hero\n"
            "အသံပုံစံစာရင်းအတွက် /voices ကို သုံးပါ။"
        )
        return
    try:
        validate_tts_request(script, voice)
        await update.message.reply_text("MP3 အသံနှင့် အချိန်ကိုက် SRT ကို တစ်ပြိုင်နက် ဖန်တီးနေပါတယ်...")
        audio, srt_text = await synthesize_burmese_speech_with_srt(script, voice)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    except RuntimeError as exc:
        await update.message.reply_text(str(exc))
        return
    audio_file = BytesIO(audio)
    audio_file.name = "nexora_burmese_voiceover.mp3"
    await update.message.reply_document(
        document=InputFile(audio_file, filename=audio_file.name),
        caption="မြန်မာ Voice-over MP3 ဖိုင်ပါ။"
    )
    subtitle_file = BytesIO(srt_text.encode("utf-8-sig"))
    subtitle_file.name = "nexora_burmese_aligned_subtitles.srt"
    await update.message.reply_document(
        document=InputFile(subtitle_file, filename=subtitle_file.name),
        caption="အသံထုတ်လုပ်စဉ်ရရှိသော WordBoundary အချိန်မှတ်တမ်းဖြင့် ချိန်ညှိထားသည့် SRT ဖိုင်ပါ။ ထုတ်ဝေမီ ပြန်စစ်ပါ။"
    )


async def recapvoice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create one Burmese narration MP3 and its word-aligned SRT from a creator script."""
    if not update.message or not update.message.text:
        return
    try:
        preset, script = parse_recap_voice_request(update.message.text, VOICE_PRESETS)
        validate_tts_request(script, preset)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    await update.message.reply_text(
        f"မြန်မာ narration ကို {VOICE_PRESETS[preset]['label']} preset ဖြင့် ဖန်တီးပြီး "
        "အသံနှင့်အချိန်ကိုက် SRT ကိုပါ ပြင်ဆင်နေပါတယ်..."
    )
    try:
        audio, srt_text = await synthesize_burmese_speech_with_srt(script, preset)
    except (ValueError, RuntimeError) as exc:
        await update.message.reply_text(f"Recap အသံ/စာတန်း ဖန်တီးမရပါ: {exc}")
        return
    except Exception:
        log.exception("/recapvoice synthesis failed")
        await update.message.reply_text("Recap အသံ/စာတန်း ဖန်တီးရာတွင် မမျှော်လင့်ထားသော အမှားရှိပါတယ်။")
        return

    audio_file = BytesIO(audio)
    audio_file.name = "nexora_recap_voiceover.mp3"
    await update.message.reply_document(
        document=InputFile(audio_file, filename=audio_file.name),
        caption=(
            f"🎙️ Burmese Recap Voice-over — {VOICE_PRESETS[preset]['label']}\n"
            "ကိုယ်တိုင်ရေးထားသော Script မှ ဖန်တီးထားသည်။ အသံထွက်နှင့် အမည်များကို ပြန်စစ်ပါ။"
        ),
        read_timeout=120,
        write_timeout=120,
    )
    subtitle_file = BytesIO(srt_text.encode("utf-8-sig"))
    subtitle_file.name = "nexora_recap_subtitles_aligned.srt"
    await update.message.reply_document(
        document=InputFile(subtitle_file, filename=subtitle_file.name),
        caption="အသံထုတ်လုပ်စဉ် WordBoundary အချိန်မှတ်တမ်းဖြင့် ချိန်ညှိထားသော မြန်မာ SRT ဖြစ်သည်။ ထုတ်ဝေမီ ပြန်စစ်ပါ။",
    )


async def scenetts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate separate MP3 and aligned SRT files for each tagged scene."""
    if not update.message or not update.message.text:
        return
    script = update.message.text.partition("\n")[2].strip()
    try:
        scenes = parse_scene_script(script)
    except ValueError as exc:
        await update.message.reply_text(
            f"{exc}\n\n"
            "အရေးကြီး: Command နဲ့ ဇာတ်ဝင်ခန်းစာသားကို Telegram message တစ်စောင်တည်းမှာ "
            "ထည့်ပို့ပါ။ /scenetts ကို သီးခြားပို့ပြီး စာသားကို နောက် message တစ်စောင်အဖြစ် "
            "ပို့ပါက လက်ရှိစနစ်က မဖတ်နိုင်ပါ။\n\n"
            "ဥပမာ:\n/scenetts\n[narrator]\nဒီနေ့ ဇာတ်လမ်းကို စတင်မိတ်ဆက်ပါမယ်။"
            "\n\n[hero]\nကျွန်တော် ဒီနေရာကို ပထမဆုံး ရောက်ဖူးတာပါ။"
            "\n\n[villain]\nမင်း ဒီအကြောင်းကို ဘယ်သူ့ကိုမှ မပြောရဘူး။"
        )
        return

    await update.message.reply_text(
        f"ဇာတ်ဝင်ခန်း {len(scenes)} ခန်းကို အသံပုံစံအလိုက် သီးခြားဖန်တီးနေပါတယ်။"
    )
    for index, scene in enumerate(scenes, start=1):
        try:
            audio, srt_text = await synthesize_burmese_speech_with_srt(
                scene["text"], scene["preset"]
            )
        except (ValueError, RuntimeError) as exc:
            await update.message.reply_text(
                f"အခန်း {index} ({scene['preset']}) မှာ ရပ်သွားပါတယ်: {exc}\n"
                "အရင်အခန်းဖိုင်များကို ရရှိပြီးပါက ဆက်လက်အသုံးပြုနိုင်ပါတယ်။"
            )
            return

        audio_name = f"nexora_scene_{index}_{scene['preset']}.mp3"
        audio_file = BytesIO(audio)
        audio_file.name = audio_name
        await update.message.reply_document(
            document=InputFile(audio_file, filename=audio_name),
            caption=f"🎙️ အခန်း {index}/{len(scenes)} — Role: {scene['role']} | Preset: {scene['preset']} ({VOICE_PRESETS[scene['preset']]['label']})"
        )
        srt_name = f"nexora_scene_{index}_{scene['preset']}.srt"
        subtitle_file = BytesIO(srt_text.encode("utf-8-sig"))
        subtitle_file.name = srt_name
        await update.message.reply_document(
            document=InputFile(subtitle_file, filename=srt_name),
            caption=f"အခန်း {index} အတွက် အသံနှင့်အချိန်ကိုက် SRT"
        )


async def scenedesign_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate separate fictional VoxCPM2 WAV files for tagged scenes."""
    if not update.message or not update.message.text:
        return

    log.info("Received /scenedesign update")
    # Acknowledge immediately so users can distinguish handler delivery from
    # a later parsing/model/runtime failure.
    await update.message.reply_text(" /scenedesign လက်ခံရရှိပါပြီ။ စာသားနဲ့ AI အသံခေါင်းစဉ်များကို စစ်ဆေးနေပါတယ်။")

    try:
        script = update.message.text.partition("\n")[2].strip()
        scenes = parse_voice_design_scene_script(script)
        await update.message.reply_text(
            f"AI ဇာတ်ဝင်ခန်း {len(scenes)} ခန်းကို သီးခြား WAV ထုတ်နေပါတယ်။ "
            "GPU host ပေါ်တွင် အခန်းတစ်ခန်းချင်းစီ အချိန်ယူနိုင်ပါတယ်..."
        )
        for index, scene in enumerate(scenes, start=1):
            voice = scene["voice"]
            try:
                audio = await synthesize_designed_burmese_voice(scene["text"], voice)
            except Exception as exc:
                log.exception("Scene design synthesis failed (scene=%s, voice=%s)", index, voice)
                await update.message.reply_text(
                    f"AI အခန်း {index} ({voice}) မအောင်မြင်ပါ: {type(exc).__name__}: {exc}"
                )
                return

            audio_name = f"nexora_ai_scene_{index}_{voice}.wav"
            audio_file = BytesIO(audio)
            audio_file.name = audio_name
            await update.message.reply_document(
                document=InputFile(audio_file, filename=audio_name),
                caption=(
                    f"AI အခန်း {index}/{len(scenes)} — {VOICE_DESIGNS[voice]['label']}\n"
                    "စိတ်ကူးယဉ် synthetic voice ဖြစ်ပြီး တကယ့်လူတစ်ဦး၏အသံကို မကူးယူပါ။"
                ),
                read_timeout=120,
                write_timeout=120,
            )
    except Exception as exc:
        log.exception("/scenedesign handler failed")
        try:
            await update.message.reply_text(
                f"/scenedesign လုပ်ဆောင်ရာတွင် အမှားရှိပါတယ်: {type(exc).__name__}: {exc}"
            )
        except Exception:
            log.exception("Could not send /scenedesign error reply")


async def voices_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List Burmese voice identities and delivery-style presets."""
    if not update.message:
        return
    lines = [
        "NEXORA မြန်မာအသံပုံစံများ",
        "Online Neural Voice အစစ်မှာ Nilar (အမျိုးသမီး) နှင့် Thiha (အမျိုးသား) နှစ်မျိုးသာရှိပါတယ်။ ကျန်ရွေးချယ်မှုတွေက အသံအသစ်မဟုတ်ဘဲ ပြောနှုန်း/အသံအနိမ့်အမြင့် Preset များဖြစ်ပါတယ်။",
        "Local MyanmarTTS ကို သီးခြား install + NEXORA_LOCAL_TTS_ENABLED=1 ဖွင့်ထားမှ /tts_local ဖြင့် စမ်းနိုင်ပါတယ်။ ဒီမော်ဒယ်မှာ default reference voice တစ်မျိုးသာပါပြီး scene အလိုက် သရုပ်ဆောင်အသစ်များ မပါပါ။"
    ]
    for key, preset in VOICE_PRESETS.items():
        lines.append(f"/tts {key} — {preset['label']}")
    lines.append("MP3 + SRT တွဲလိုပါက /ttssrt <preset> ကို သုံးပါ။ အသံကို အရင်နားထောင်လိုပါက /voicedemo <preset> ကို သုံးပါ။")
    lines.append("AI Voice Design အသစ်များ: " + ", ".join(VOICE_DESIGNS) + " — /tts_design <voice_name> ဖြင့် WAV ထုတ်နိုင်သည် (VoxCPM2 GPU host လိုအပ်သည်)။")
    lines.append("ဇာတ်ဝင်ခန်းတစ်ခန်းစီအတွက် AI အသံမတူစေလိုပါက /scenedesign နှင့် [ai:story_female] ကဲ့သို့ ခေါင်းစဉ်သုံးပါ။ အခန်း ၄ ခန်းအထိ၊ တစ်ခန်းစာလုံး ၁,၅၀၀ အထိ။")
    lines.append("မြန်မာ Role များ: [ဇာတ်ကြောင်း], [မင်းသား], [မင်းသမီး], [ဗီလိန်], [လူကြီး], [ကလေး], [ဟာသ], [လျှို့ဝှက်], [အက်ရှင်]")
    lines.append("English Role များ: [narrator], [protagonist], [heroine], [antagonist], [supporting], [elder], [child], [comic], [suspense], [action]")
    lines.append("Role များသည် ရှိပြီးသား preset များသို့ ချိတ်ဆက်ထားခြင်းသာဖြစ်ပြီး Nilar/Thiha အသံအခြေခံကို မပြောင်းပါ။")
    lines.append("ဇာတ်ဝင်ခန်းတစ်ခုစီအတွက် မတူသော role/preset သုံးရန် /scenetts ကို သုံးပါ။")
    lines.append("မှတ်ချက်: Nilar/Thiha အသံပိုင်ရှင် ၂ မျိုးကိုသာ အသုံးပြုပြီး preset များက သရုပ်ဆောင်အသံအသစ် မဟုတ်ပါ။")
    await update.message.reply_text("\n".join(lines))


async def srtmy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create Burmese captions with estimated timing from a supplied script."""
    if not update.message or not update.message.text:
        return
    script = update.message.text.partition("\n")[2].strip()
    if not script:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /srtmy ပြီးနောက် မြန်မာ Voice-over စာသားကို စာကြောင်းအသစ်မှ ထည့်ပါ။\n"
            "မှတ်ချက်: အချိန်ကို စာလုံးအရေအတွက်ဖြင့် ခန့်မှန်းထားခြင်းဖြစ်ပြီး အသံနှင့် ကိုက်ညီအောင် ပြန်ညှိပါ။"
        )
        return
    try:
        srt_text = build_burmese_srt(script)
    except ValueError as exc:
        await update.message.reply_text(f"မြန်မာစာတန်းထိုး မထုတ်နိုင်ပါ: {exc}")
        return
    file_obj = BytesIO(srt_text.encode("utf-8-sig"))
    file_obj.name = "nexora_burmese_subtitles.srt"
    await update.message.reply_document(
        document=InputFile(file_obj, filename=file_obj.name),
        caption="မြန်မာစာတန်းထိုး SRT ဖိုင်ပါ။ အချိန်များကို ခန့်မှန်းထားသောကြောင့် အသံနှင့် ပြန်ညှိပါ။"
    )


async def growthpack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a source-aware publishing pack without inventing plot or popularity data."""
    if not update.message or not update.message.text:
        return
    raw = update.message.text.split(maxsplit=1)
    if len(raw) < 2:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /growthpack Anime|Frieren: Beyond Journey's End|ဇာတ်လမ်းအကျဉ်း (optional)\n"
            "Category: Anime | 3D Animation | Cartoon | Donghua | International Movies\n"
            "Summary မထည့်ပါက ဇာတ်ကွက်ကို မခန့်မှန်းဘဲ ဖြည့်ရန်နေရာ ထားပေးမည်။"
        )
        return
    fields = raw[1].split("|", 2)
    if len(fields) < 2:
        await update.message.reply_text(
            "Category နဲ့ ခေါင်းစဉ်ကို | ဖြင့် ခွဲပါ။\n"
            "ဥပမာ: /growthpack Donghua|Soul Land|အတည်ပြုထားသော ဇာတ်လမ်းအကျဉ်း"
        )
        return
    category, title = fields[0].strip(), fields[1].strip()
    summary = fields[2].strip() if len(fields) > 2 else ""
    platform = context.user_data.get("platform", "youtube")
    try:
        pack = generate_growth_pack(title, category, platform, summary)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    if len(pack) <= 3900:
        await update.message.reply_text(pack)
        return
    file_obj = BytesIO(pack.encode("utf-8"))
    file_obj.name = "nexora_channel_growth_pack.txt"
    await update.message.reply_document(
        document=InputFile(file_obj, filename=file_obj.name),
        caption="NEXORA Channel Growth Pack — ထုတ်ဝေမှုမတိုင်မီ အချက်အလက်နှင့် မီဒီယာလိုင်စင်ကို ပြန်စစ်ပါ။"
    )


async def recapqa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run deterministic editorial checks on a creator-supplied recap script."""
    if not update.message or not update.message.text:
        return
    parts = update.message.text.split("\n", 1)
    header = parts[0].split(maxsplit=1)
    if len(header) < 2 or len(parts) < 2:
        await update.message.reply_text(
            "အသုံးပြုပုံ:\n/recapqa Anime|Frieren: Beyond Journey's End\n"
            "ပြီးနောက် Script ကို စာကြောင်းအသစ်မှ ထည့်ပါ။\n"
            "Category: Anime | 3D Animation | Cartoon | Donghua | International Movies"
        )
        return
    fields = header[1].split("|", 1)
    if len(fields) != 2:
        await update.message.reply_text("Category|Title ပုံစံဖြင့် ထည့်ပါ။ ဥပမာ: /recapqa Donghua|Soul Land")
        return
    report = analyze_recap_script(fields[0], fields[1], parts[1])
    output = format_recap_qa_report(report)
    await update.message.reply_text(output[:3900])

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "Commands:\n/start\n/status\n/create <topic>\n/mode free|ai\n/srt\n/srtmy\n/tts female|male\n/platform youtube|tiktok|facebook\n/duration <minutes>\n/settings\n/help\n\n"
            "YouTube: 8-10, 12-15, 15-20, 20-30, 30-45, 46-60\nTikTok: 1-3, 3-5, 4-7\nFacebook: 3-5, 5-7, 8-10, 10-15, 46-60\n"
            "\n"
            "/auto သည် Wikipedia မှ source lead များရှာပေးသည်၊ အချက်အလက်ကို ကိုယ်တိုင်ပြန်စစ်ပါ။\n"
            "/multisourceresearch <Anime အမည်> သည် AniList + Tenrai/MAL + Wikidata metadata ကို တစ်ပြိုင်နက်စစ်ပေးသည်။\n"
            "/moviemultisourceresearch <ရုပ်ရှင်အမည်> သည် TMDB + Wikidata metadata ကို စစ်ပေးသည်။\n"
            "/draft သည် ပေးထားသော Research Notes ကို worksheet အဖြစ် စီစဉ်ပေးသည်။\n"
            "/draft3 သည် YouTube အတွက် သီးခြား worksheet သုံးခု ထုတ်ပေးသည်။\n"
            "/allplatforms သည် YouTube/Facebook/TikTok အတွက် အပိုင်းနှင့် ကြာချိန် သီးခြားခွဲပြသည်။\n"
            "/voiceover <အမည်> နှင့် /voiceover3 <အမည်> သည် သင်ပေးသော စစ်ဆေးပြီး Notes ကို TXT ဖိုင်အဖြစ် စီစဉ်ပေးသည်။\n"
            "Voice-over အတွက် ဇာတ်ကားနှင့် ပြန်စစ်ထားသော Notes အနည်းဆုံး ၆ ကြောင်း လိုအပ်သည်။\n"
            "အသုံးပြုပုံ: /voiceover3 Avatar ပြီးနောက် စာကြောင်းအသစ်မှ ဖြစ်ရပ်မှန် Notes များ ထည့်ပါ။\n"
            "Wikipedia /auto ရလဒ်တိုများကို တိုက်ရိုက်သုံးရန် မလုံလောက်ပါ။ Source link များကို ပြန်စစ်ပြီး ကိုယ်တိုင် Notes ရေးပါ။\n"
            "/auto Avatar ပြီးနောက် /draft3 Avatar ပို့လျှင် ရှာထားသော Notes ကို အလိုအလျောက် ထည့်ပေးသည်။\n"
            "/seriesguide <title> ဖြင့် TVmaze ကို အရင်စစ်ပါမည်။ Anime စာရင်းထဲမှ ခေါင်းစဉ်များကို AniList ဖြင့် ထပ်စစ်ပြီး နောက်ဆုံးတွင် Wikidata ကို စစ်ပါမည်။ ရင်းမြစ်မတွေ့ပါက အရေအတွက်ကို မခန့်မှန်းပါ။\n"
            "/platform youtube|facebook|tiktok ကို အရင်ရွေးပါ။ /render ဖြင့် Slideshow၊ /render timeline ဖြင့် Scene တစ်ခုစီ ပုံ/အသံ အချိန်ကိုက် MP4 ထုတ်နိုင်သည်။ /render scene <အမည်> ဖြင့် Scene ဖွင့်ပါ။ .srt ပို့လျှင် ရွေးဖွင့်နိုင်သော Track ထည့်မည်။ /render finish ဖြင့် ပြီးစီးစေပါ။\n"
            "/clipsource နှင့် /autoclip ဖြင့် လိုင်စင်ရှိ Video ရင်းမြစ်ရှာပြီး Preview MP4 ထုတ်နိုင်သည်။\n"
            "/autonarrateclip <title>\n<preset>\n<script> ဖြင့် narration နှင့် selectable SRT track ထည့်နိုင်သည်။ ဇာတ်လမ်းအချက်အလက်ကို စစ်ပြီးမှ ထည့်ပါ။\n"
            "/autofactsclip <title> သည် Wikidata အချက်အလက်နှင့် ခွင့်ပြုထားသော footage ကိုသုံးပြီး မိတ်ဆက် Video အလိုအလျောက်ထုတ်သည်။ ဇာတ်ကွက် recap မဟုတ်ပါ။\n"
            "/autoplotclip <title> သည် မြန်မာ Wikipedia ဇာတ်လမ်းအကျဉ်း ရှိမှသာ ရင်းမြစ်အခြေပြု narration preview ထုတ်သည်။\n"
            "/animesynopsis <title> သည် AniList မှ Anime series synopsis ကို research အဖြစ်ပြသည်။ Episode recap မဟုတ်ပါ။\n"
            "/seriesresearch <title> သည် TVmaze မှ Animation genre ပါသော Cartoon/Donghua series overview ကို ပြသည်။ Episode recap မဟုတ်ပါ။\n"
            "/animationepisodes <title> သည် TVmaze မှ Animation Series Episode summary အတိုများကို ရင်းမြစ်နှင့်ပြသည်။\n"
            "/movieplotresearch <title> သည် exact Wikidata-English Wikipedia ချိတ်ဆက်ထားသော နိုင်ငံခြားရုပ်ရှင် Plot section ကို research အဖြစ်ပြသည်။\n"
            "/growthpack <category>|<title>|<summary optional> သည် title၊ description၊ thumbnail၊ Hook နှင့် retention checklist ပြင်ဆင်ပေးသည်။ Live views/trends ကို မခန့်မှန်းပါ။\n"
            "/topratedepisodes <title> သည် TVmaze community rating အမြင့်ဆုံး Animation Episode များကိုပြသည်။ View count မဟုတ်ပါ။\n"
            "/episodeoutline <title> သည် အမြင့်ဆုံး rating ရှိ Episode တစ်ခုအတွက် Recap Script Worksheet ပြင်ဆင်ပေးသည်။\n"
            "/commentstatus ဖြင့် YouTube/Facebook Auto-Reply အခြေအနေကြည့်ပါ။ /commentdraft ဖြင့် Reply စာသားစမ်းနိုင်သည်။\n"
            "Free Mode သည် API မလိုပါ။ AI Mode သည် provider မချိတ်ရသေးပါ။ "
            "/srt ဖြင့် timestamp ပါသော စာတန်းမှ .srt ဖိုင်ထုတ်နိုင်သည်။ /srtmy ဖြင့် မြန်မာစာသားမှ ခန့်မှန်းအချိန် SRT ထုတ်နိုင်သည်။ /tts ဖြင့် မြန်မာ MP3 အသံဖန်တီးနိုင်သည်။ /voicedemo <preset> ဖြင့် အသံပုံစံနမူနာ နားထောင်နိုင်သည်။ /tts_design <voice_name> ဖြင့် VoxCPM2 AI စိတ်ကူးယဉ်အသံ WAV ဖန်တီးနိုင်သည် (GPU host + သီးခြား install + NEXORA_VOXCPM_ENABLED=1 လိုအပ်သည်)။ /tts_local ဖြင့် optional local MyanmarTTS WAV စမ်းနိုင်သည် (သီးခြား install + NEXORA_LOCAL_TTS_ENABLED=1 လိုအပ်သည်။)"
        )


async def on_telegram_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    # Do not log exception text: request errors can contain credential-bearing URLs.
    error = context.error
    error_name = type(error).__name__ if error else "UnknownError"
    log.error("Telegram update handler failed (%s)", error_name)
    if error is not None:
        try:
            reported = await asyncio.to_thread(
                report_error_to_github,
                error,
                update_kind="telegram_update",
            )
            if reported:
                log.info("Privacy-safe error report created in GitHub Issues")
        except Exception:
            # Reporting must never cause another handler failure.
            log.warning("GitHub error reporting could not be completed")


@asynccontextmanager
async def lifespan(web_app: FastAPI):
    global telegram_app, comment_autoreply_task
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    if not WEBHOOK_SECRET:
        raise RuntimeError("TELEGRAM_WEBHOOK_SECRET is missing")
    if not PUBLIC_URL:
        raise RuntimeError("RENDER_EXTERNAL_URL is missing")

    telegram_app = Application.builder().token(TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("status", status))
    telegram_app.add_handler(CommandHandler("chatid", chatid_cmd))
    telegram_app.add_handler(CommandHandler("create", create))
    telegram_app.add_handler(CommandHandler("aiscript", aiscript_cmd))
    telegram_app.add_handler(CommandHandler("research", research_cmd))
    telegram_app.add_handler(CommandHandler("auto", auto_research_cmd))
    telegram_app.add_handler(CommandHandler("seriesguide", series_guide_cmd))
    telegram_app.add_handler(CommandHandler("draft", draft_cmd))
    telegram_app.add_handler(CommandHandler("draft3", draft3_cmd))
    telegram_app.add_handler(CommandHandler("allplatforms", allplatforms_cmd))
    telegram_app.add_handler(CommandHandler("voiceover", voiceover_cmd))
    telegram_app.add_handler(CommandHandler("voiceover3", voiceover3_cmd))
    telegram_app.add_handler(CommandHandler("clipsource", clipsource_cmd))
    telegram_app.add_handler(CommandHandler("recapchannels", recapchannels_cmd))
    telegram_app.add_handler(CommandHandler("recapstudio", recapstudio_cmd))
    telegram_app.add_handler(CommandHandler("autoclip", autoclip_cmd))
    telegram_app.add_handler(CommandHandler("autonarrateclip", autonarrateclip_cmd))
    telegram_app.add_handler(CommandHandler("autofactsclip", autofactsclip_cmd))
    telegram_app.add_handler(CommandHandler("autoplotclip", autoplotclip_cmd))
    telegram_app.add_handler(CommandHandler("animesynopsis", animesynopsis_cmd))
    telegram_app.add_handler(CommandHandler("multisourceresearch", multisourceresearch_cmd))
    telegram_app.add_handler(CommandHandler("seriesresearch", seriesresearch_cmd))
    telegram_app.add_handler(CommandHandler("animationepisodes", animationepisodes_cmd))
    telegram_app.add_handler(CommandHandler("topratedepisodes", topratedepisodes_cmd))
    telegram_app.add_handler(CommandHandler("episodepack", episodepack_cmd))
    telegram_app.add_handler(CommandHandler("episodeoutline", episodeoutline_cmd))
    telegram_app.add_handler(CommandHandler("recapvoice", recapvoice_cmd))
    telegram_app.add_handler(CommandHandler("recapvideo", recapvideo_cmd))
    telegram_app.add_handler(CommandHandler("moviemultisourceresearch", moviemultisourceresearch_cmd))
    telegram_app.add_handler(CommandHandler("movieplotresearch", movieplotresearch_cmd))
    telegram_app.add_handler(CommandHandler("growthpack", growthpack_cmd))
    telegram_app.add_handler(CommandHandler("recapqa", recapqa_cmd))
    telegram_app.add_handler(CommandHandler("render", render_cmd))
    telegram_app.add_handler(MessageHandler(filters.PHOTO | filters.AUDIO | filters.VOICE | filters.Document.ALL, video_media_message))
    telegram_app.add_handler(CommandHandler("cancel", cancel_voiceover_cmd))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, voiceover_notes_message))
    telegram_app.add_handler(CommandHandler("mode", mode_cmd))
    telegram_app.add_handler(CommandHandler("srt", srt_cmd))
    telegram_app.add_handler(CommandHandler("srtmy", srtmy_cmd))
    telegram_app.add_handler(CommandHandler("tts", tts_cmd))
    telegram_app.add_handler(CommandHandler("voicedemo", voicedemo_cmd))
    telegram_app.add_handler(CommandHandler("tts_design", ttsdesign_cmd))
    telegram_app.add_handler(CommandHandler("scenedesign", scenedesign_cmd))
    telegram_app.add_handler(CommandHandler("tts_local", ttslocal_cmd))
    telegram_app.add_handler(CommandHandler("ttssrt", ttssrt_cmd))
    telegram_app.add_handler(CommandHandler("scenetts", scenetts_cmd))
    telegram_app.add_handler(CommandHandler("voiceprofile", voiceprofile_cmd))
    telegram_app.add_handler(CommandHandler("voices", voices_cmd))
    telegram_app.add_handler(CommandHandler("platform", platform_cmd))
    telegram_app.add_handler(CommandHandler("duration", duration_cmd))
    telegram_app.add_handler(CommandHandler("settings", settings_cmd))
    telegram_app.add_handler(CommandHandler("commentstatus", comment_status_cmd))
    telegram_app.add_handler(CommandHandler("commentdraft", comment_draft_cmd))
    telegram_app.add_handler(CommandHandler("help", help_cmd))
    telegram_app.add_error_handler(on_telegram_error, block=False)

    await telegram_app.initialize()
    await telegram_app.start()
    if os.getenv("COMMENT_AUTOREPLY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}:
        comment_autoreply_task = asyncio.create_task(comment_autoreply_loop())
    try:
        await telegram_app.bot.set_webhook(
            url=f"{PUBLIC_URL.rstrip('/')}/telegram-webhook",
            secret_token=WEBHOOK_SECRET,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
        )
        log.info("NEXORA Telegram webhook started")
        yield
    finally:
        # Keep the Telegram webhook registered when Render stops or sleeps the service.
        # Telegram can retry pending updates after the service starts again.
        if comment_autoreply_task is not None:
            comment_autoreply_task.cancel()
            try:
                await comment_autoreply_task
            except asyncio.CancelledError:
                pass
            comment_autoreply_task = None
        await telegram_app.stop()
        await telegram_app.shutdown()
        telegram_app = None


web_app = FastAPI(title="NEXORA Myanmar Recap Bot", lifespan=lifespan)


@web_app.get("/")
async def home():
    return {"app": "NEXORA Myanmar Recap Bot", "status": "online"}


@web_app.get("/health")
async def health():
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not ready")
    return {"status": "ok", "telegram": True}


@web_app.get("/console", response_class=HTMLResponse)
async def web_command_console():
    """Mobile-friendly command console; bridge secrets never reach the browser."""
    return HTMLResponse(CONSOLE_HTML)


def _console_origin_is_same(request: Request) -> bool:
    origin = request.headers.get("origin", "")
    return bool(origin) and origin.rstrip("/") == str(request.base_url).rstrip("/")


def _console_is_authorized(request: Request) -> bool:
    password = os.getenv("NEXORA_CONSOLE_PASSWORD", "")
    token = request.cookies.get("nexora_console", "")
    return verify_console_session(token, password)


@web_app.post("/console/login")
async def web_console_login(request: Request):
    if not _console_origin_is_same(request):
        raise HTTPException(status_code=403, detail="Same-origin request required")
    password = os.getenv("NEXORA_CONSOLE_PASSWORD", "")
    if len(password) < 16:
        raise HTTPException(status_code=503, detail="Web console password is not configured (minimum 16 characters)")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    supplied = payload.get("password", "") if isinstance(payload, dict) else ""
    if not isinstance(supplied, str) or not hmac.compare_digest(supplied, password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    response = JSONResponse({"ok": True})
    response.set_cookie(
        "nexora_console",
        create_console_session(password),
        max_age=8 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/console",
    )
    return response


@web_app.get("/console/session")
async def web_console_session(request: Request):
    return {"authenticated": _console_is_authorized(request)}


@web_app.post("/console/logout")
async def web_console_logout(request: Request):
    if not _console_origin_is_same(request):
        raise HTTPException(status_code=403, detail="Same-origin request required")
    response = JSONResponse({"ok": True})
    response.delete_cookie("nexora_console", path="/console", secure=True, httponly=True, samesite="strict")
    return response


@web_app.post("/console/command")
async def web_console_command(request: Request):
    if not _console_origin_is_same(request):
        raise HTTPException(status_code=403, detail="Same-origin request required")
    if not _console_is_authorized(request):
        raise HTTPException(status_code=401, detail="Console login required")
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not ready")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    command = str(payload.get("command", "")).strip().lower().lstrip("/")
    argument = str(payload.get("argument", "")).strip()
    if command not in BRIDGE_ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Command is not allowed")
    if len(argument) > 3500 or "\n" in argument or "\r" in argument:
        raise HTTPException(status_code=400, detail="Argument is too long or invalid")
    try:
        chat_id = int(os.getenv("CHATGPT_BRIDGE_CHAT_ID", ""))
    except ValueError:
        raise HTTPException(status_code=503, detail="Telegram destination is not configured")
    if chat_id <= 0:
        raise HTTPException(status_code=503, detail="Configure a private positive Telegram chat ID")
    text = "/" + command + ((" " + argument) if argument else "")
    synthetic_update = Update.de_json({
        "update_id": time.time_ns() % 2_000_000_000,
        "message": {
            "message_id": int(time.time()) % 2_000_000_000,
            "date": int(time.time()),
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "is_bot": False, "first_name": "NEXORA Web Console"},
            "text": text,
            "entities": [{"type": "bot_command", "offset": 0, "length": len("/" + command)}],
        },
    }, telegram_app.bot)
    await telegram_app.process_update(synthetic_update)
    return {"ok": True, "command": command, "delivered_to_telegram": True}


@web_app.get("/chatgpt/bridge-health")
async def chatgpt_bridge_health():
    """Expose configuration presence only; never return secret values or chat IDs."""
    try:
        chat_id_configured = int(os.getenv("CHATGPT_BRIDGE_CHAT_ID", "")) > 0
    except ValueError:
        chat_id_configured = False
    return {
        "status": "ok",
        "telegram": telegram_app is not None,
        "bridge_api_key_configured": bool(os.getenv("CHATGPT_BRIDGE_API_KEY")),
        "bridge_chat_id_configured": chat_id_configured,
        "bridge_ready": bool(os.getenv("CHATGPT_BRIDGE_API_KEY")) and chat_id_configured and telegram_app is not None,
    }


@web_app.post("/telegram-webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if not WEBHOOK_SECRET or not hmac.compare_digest(
        x_telegram_bot_api_secret_token or "", WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=403, detail="Forbidden")
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Bot is starting")
    payload = await request.json()
    update = Update.de_json(payload, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return {"ok": True}


# Optional authenticated bridge for a Custom GPT Action. Configure both values in
# Render Environment; never commit either secret or put them in chat.
CHATGPT_BRIDGE_API_KEY = os.getenv("CHATGPT_BRIDGE_API_KEY")
CHATGPT_BRIDGE_CHAT_ID = os.getenv("CHATGPT_BRIDGE_CHAT_ID")
BRIDGE_ALLOWED_COMMANDS = {
    "status", "help", "auto", "seriesguide", "create", "research", "draft3",
    "allplatforms", "voiceover3", "render", "animesynopsis", "multisourceresearch",
    "seriesresearch", "animationepisodes", "topratedepisodes", "episodepack",
    "episodeoutline", "recapvideo", "movieplotresearch", "moviemultisourceresearch",
    "growthpack", "clipsource", "autoplotclip", "autoclip", "autonarrateclip",
    "autofactsclip",
}


def _bridge_authorized(request: Request) -> bool:
    supplied = request.headers.get("x-nexora-bridge-key", "")
    return (
        isinstance(CHATGPT_BRIDGE_API_KEY, str)
        and len(CHATGPT_BRIDGE_API_KEY) >= 32
        and hmac.compare_digest(supplied, CHATGPT_BRIDGE_API_KEY)
    )


@web_app.post("/chatgpt/send-message")
async def chatgpt_bridge_send_message(request: Request):
    """Send plain text from an authenticated ChatGPT Action to the owner's private Telegram chat."""
    if not _bridge_authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not ready")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    message = payload.get("message")
    if not isinstance(message, str):
        raise HTTPException(status_code=400, detail="Message must be text")
    message = message.strip()
    if not message or len(message) > 3500:
        raise HTTPException(status_code=400, detail="Message must be between 1 and 3500 characters")
    try:
        chat_id = int(CHATGPT_BRIDGE_CHAT_ID or "")
    except ValueError:
        raise HTTPException(status_code=503, detail="CHATGPT_BRIDGE_CHAT_ID is not configured")
    if chat_id <= 0:
        raise HTTPException(status_code=503, detail="Configure a private positive Telegram chat ID")
    sent = await telegram_app.bot.send_message(
        chat_id=chat_id,
        text=message,
        read_timeout=30,
        write_timeout=30,
    )
    return {"ok": True, "message_id": sent.message_id, "delivered_to_telegram": True}


@web_app.post("/chatgpt/command")
async def chatgpt_bridge_command(request: Request):
    """Run one allow-listed NEXORA bot command in the owner's configured private chat."""
    if not _bridge_authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not ready")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    command = str(payload.get("command", "")).strip().lower().lstrip("/")
    argument = str(payload.get("argument", "")).strip()
    if command not in BRIDGE_ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Command is not allowed")
    if len(argument) > 3500 or "\n" in argument or "\r" in argument:
        raise HTTPException(status_code=400, detail="Argument is too long or invalid")
    try:
        chat_id = int(CHATGPT_BRIDGE_CHAT_ID or "")
    except ValueError:
        raise HTTPException(status_code=503, detail="CHATGPT_BRIDGE_CHAT_ID is not configured")
    if chat_id <= 0:
        raise HTTPException(status_code=503, detail="Configure a private positive Telegram chat ID")
    text = "/" + command + ((" " + argument) if argument else "")
    synthetic_update = Update.de_json({
        "update_id": time.time_ns() % 2_000_000_000,
        "message": {
            "message_id": int(time.time()) % 2_000_000_000,
            "date": int(time.time()),
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "is_bot": False, "first_name": "NEXORA Bridge"},
            "text": text,
            "entities": [{"type": "bot_command", "offset": 0, "length": len("/" + command)}],
        },
    }, telegram_app.bot)
    await telegram_app.process_update(synthetic_update)
    return {"ok": True, "command": command, "delivered_to_telegram": True}


@web_app.post("/chatgpt/send-file")
async def chatgpt_bridge_send_file(request: Request):
    """Send a small base64-encoded creator-owned file to the configured private chat."""
    if not _bridge_authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not ready")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    filename = str(payload.get("filename", ""))
    encoded = payload.get("content_base64", "")
    allowed_suffixes = {".mp3", ".wav", ".ogg", ".jpg", ".jpeg", ".png", ".webp", ".mp4", ".txt", ".srt"}
    suffix = os.path.splitext(filename)[1].lower()
    if not filename or len(filename) > 100 or suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="Unsupported filename or file type")
    if not isinstance(encoded, str) or len(encoded) > 28_000_000:
        raise HTTPException(status_code=413, detail="File is too large")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid base64 file content")
    if not content or len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File must be between 1 byte and 20 MB")
    try:
        chat_id = int(CHATGPT_BRIDGE_CHAT_ID or "")
    except ValueError:
        raise HTTPException(status_code=503, detail="CHATGPT_BRIDGE_CHAT_ID is not configured")
    if chat_id <= 0:
        raise HTTPException(status_code=503, detail="Configure a private positive Telegram chat ID")
    file_obj = BytesIO(content)
    file_obj.name = os.path.basename(filename)
    await telegram_app.bot.send_document(
        chat_id=chat_id,
        document=InputFile(file_obj, filename=file_obj.name),
        caption="ဖိုင်ကို ChatGPT Bridge မှ ပို့ထားပါတယ်။ အသုံးပြုခွင့်ရှိသော မီဒီယာကိုသာ အသုံးပြုပါ။",
        read_timeout=60,
        write_timeout=60,
    )
    return {"ok": True, "filename": file_obj.name, "bytes_sent": len(content)}
