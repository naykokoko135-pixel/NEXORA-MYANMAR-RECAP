import asyncio
import base64
import binascii
import time
import hmac
from io import BytesIO
import logging
import os
import re
import tempfile
import secrets
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from telegram import InputFile, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from srt_builder import build_srt
from subtitle_builder import build_burmese_srt
from tts_builder import VOICE_PRESETS, synthesize_burmese_speech, synthesize_burmese_speech_with_srt, validate_tts_request
from local_myanmar_tts import synthesize_local_burmese_speech
from voxcpm_voice_design import VOICE_DESIGNS, synthesize_designed_burmese_voice
from voxcpm_voice_clone import synthesize_cloned_burmese_voice
from creator_voice_recap import synthesize_recap_in_creator_voice, combine_creator_voice_parts
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
from video_renderer import render_slideshow, render_scene_timeline, VideoRenderError, classify_render_document
from source_video_renderer import render_user_source_video, SourceVideoRenderError
from recap_partitioner import render_three_part_longform, RecapPartitionError
from automatic_longform_pipeline import render_licensed_longform_parts
from clip_source_finder import search_licensed_video, ClipSourceError
from europeana_video_finder import search_europeana_licensed_video, EuropeanaSearchError, display_media_url
from youtube_cc_finder import search_youtube_cc_videos, search_official_trailer_references, YouTubeCCSearchError
from internet_archive_video_finder import search_internet_archive_licensed_video, InternetArchiveSearchError
from internet_archive_pipeline import render_internet_archive_longform_parts, render_internet_archive_narrated_preview
from youtube_movie_recap_research import search_youtube_movie_recaps, format_youtube_movie_recaps, YouTubeRecapResearchError
from recap_studio import build_original_recap_notes
from licensed_video_pipeline import choose_matching_source, render_licensed_preview, download_licensed_source, LicensedClipError
from licensed_narrated_clip import render_licensed_narrated_preview, build_licensed_attribution_note, _subtitle_duration_seconds
from wikidata_metadata import fetch_wikidata_metadata
from kitsu_anime_research import fetch_kitsu_episode_summaries
from recap_metadata_resolver import resolve_recap_metadata
from autofacts_narration import generate_burmese_facts_narration
from myanmar_plot_research import fetch_burmese_plot_section, PlotResearchError
from verified_plot_narration import generate_burmese_plot_narration
from anilist_synopsis import fetch_anilist_synopsis
from multi_source_research import research_anime_sources, format_anime_source_report, research_all_media_sources, format_all_media_source_report
from tmdb_movie_research import research_movie_sources, format_movie_source_report
from tvmaze_synopsis import fetch_tvmaze_synopsis
from tvmaze_synopsis import fetch_tvmaze_episode_summaries, fetch_tvmaze_top_rated_episodes
from episode_plot_collection import collect_episode_plots, format_episode_plot_collection
from episode_plot_verification import verify_episode_plot_sources, format_episode_plot_verification
from animated_episode_pack import format_animated_episode_pack
from episode_recap_outline import format_episode_recap_outline
from english_plot_research import fetch_english_plot_section, EnglishPlotError
from english_plot_recap import generate_burmese_recap_from_english_plot
from synopsis_preview import generate_burmese_synopsis_preview
from channel_growth_pack import generate_growth_pack
from recap_quality_gate import analyze_recap_script, format_recap_qa_report
from production_qa import analyze_production_package, format_production_qa_report, parse_production_package
from audio_duration_qa import inspect_audio_file, evaluate_audio_duration, evaluate_audio_parts, format_audio_qa_report, format_audio_parts_qa_report, MAX_AUDIO_BYTES
from recap_voice_pack import parse_recap_voice_request, parse_recap_voice_parts_request
from recap_video_pack import parse_recap_video_request, validate_non_indian_wikidata_metadata, build_recap_video_sidecars, format_no_licensed_footage_message, format_original_visual_fallback_notice, validate_platform_recap_duration
from script_writer import (generate_recap_outline, generate_all_platform_plan, PLATFORM_NAMES, PLATFORM_DURATIONS, DURATION_PRESETS, DEFAULT_DURATIONS)
from openai_script_provider import openai_script_status, AIScriptError
from script_provider_router import generate_burmese_recap_script, script_provider_status
from gemini_script_provider import gemini_script_status
from error_reporter import report_error_to_github
from comment_autoreply import build_reply, platform_comment_capabilities, run_comment_autoreply_cycle
from web_console import CONSOLE_HTML, create_console_session, verify_console_session
from cost_controls import paid_ai_allowed

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("nexora")

# Opaque, short-lived links for rendered MP4 files. Metadata is process-local;
# links intentionally expire and are invalidated by a service restart.
DOWNLOAD_LINKS: dict[str, dict[str, object]] = {}
DOWNLOAD_LINK_TTL_SECONDS = 24 * 60 * 60
MAX_DOWNLOAD_LINKS = 100

# HTTPX logs full Telegram API URLs at INFO level; those URLs contain the bot token.
# Keep request URLs out of Render logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")
telegram_app: Application | None = None
comment_autoreply_task: asyncio.Task | None = None
daily_recap_task: asyncio.Task | None = None
daily_recap_state: dict[str, object] = {"status": "idle"}


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
            "/episodeplots <Series အမည်> - TVmaze/Kitsu/Bangumi Episode ဇာတ်ကွက်များကို သီးခြားစုရန်\n"
            "/episodeverify <Series အမည်> - Catalogue ရင်းမြစ်များအကြား Episode ခေါင်းစဉ်/နံပါတ် ကိုက်ညီမှု စစ်ရန်\n"
            "/episodepack <Series အမည်> - Episode + Licensed Footage Production Pack ထုတ်ရန်\n"
            "/episodeoutline <Series အမည်> - Episode တစ်ခုအတွက် Recap Script Worksheet ထုတ်ရန်\n"
            "/productionqa <Category>|<Title>|<Platform> - Script အပိုင်း၊ ကြာချိန်နှင့် SRT စစ်ရန်\n"
            "/audioqa <Platform> ကို Audio ဖိုင်အား reply လုပ်၍ တကယ့်ကြာချိန် စစ်ရန်\n"
            "/recapvoice [preset|myvoice] - တစ်ဖိုင်တည်း narration MP3 + SRT ထုတ်ရန်\n"
            "/recapvoice3 [preset|myvoice] - YouTube/Facebook Script ၃ ပိုင်းမှ MP3/SRT ၃ စုံထုတ်ပြီး Audio ကြာချိန် QA စစ်ရန်\n"
            "/recapvideo <title> - အလိုအလျောက် narration + ခွင့်ပြုထားသော Footage မရှိပါက ရပ်မည်; သင့် Video ကို /sourcevideo ဖြင့် MP4 ထုတ်ရန်\n"
            "/dailyrecap [youtube|facebook|tiktok|all] - ယနေ့ Daily Report ရွေးထားသော ခေါင်းစဉ်များကို Licensed Recap pipeline ဖြင့် စတင်ရန် (default all)\n"
            "/sourcevideo - ကိုယ်ပိုင်/ခွင့်ပြုထားသော Video + မြန်မာအသံ + SRT မှ MP4 ထုတ်ရန်\n"
            "/licensedownload <title> - Commons + Archive မှ ခွင့်ပြုထားသော မူရင်း Video ကို အလိုအလျောက် ရှာ/Download လုပ်ရန်\n"
            "/autoedit [category] - Genre အလိုက် Effect/Audio/Transition အလိုအလျောက်ရွေးရန်\n"
            "/effect [preset] - Visual Look ၂၀ မျိုး ရွေးရန်\n"
            "/audiofx [preset] - Voice/Cinematic/Podcast/Soft Audio Mastering ရွေးရန်\n"
            "/transition [preset] - Fade/Wipe/Slide/Circle/Dissolve အကူးအပြောင်း ရွေးရန်\n"
            "/motion [preset] - Camera Push-in/Pull-out/Pan/Drift Motion ရွေးရန်\n"
            "/bgm - Background Music ဖိုင်ထည့်ရန်; /bgm off - ဖယ်ရန်\n"
            "/bgmvolume 0.18 - Background Music အသံအတိုးအကျယ် ၀ မှ ၁ အထိ သတ်မှတ်ရန်\n"
            "/bgmduck on|off - Narration ပြောနေချိန် Music ကို အလိုအလျောက်လျှော့/မလျှော့ ရွေးရန်\n"
            "/logo - Brand Logo တင်ရန်; /logo position top-left; /logo off\n"
            "/substyle [preset] - Subtitle အရောင်/အရွယ်/Outline ရွေးရန်\n"
            "/subburn on|off - Subtitle ကို Video ထဲ Burn လုပ်/Soft Subtitle ပြန်ထားရန်\n"
            "/fade 0.6|off - Video/Audio အစနှင့်အဆုံး Fade ထည့်ရန်/ပိတ်ရန်\n"
            "/editstatus - လက်ရှိ Auto Edit ဆက်တင်အားလုံးကြည့်ရန်\n"
            "/quality 720p|1080p - MP4 Output Resolution ရွေးရန်\n"
            "/moviemultisourceresearch <ရုပ်ရှင်အမည်> - TMDB + Wikidata metadata စစ်ရန်\n"
            "/multisourceresearch <Anime/Cartoon/Donghua/Movie/TV Series အမည်> - အမျိုးအစားအားလုံးကို သီးခြားစစ်ရန်\n"
            "/render - Video Footage + မြန်မာ Narration + SRT မှ MP4 ထုတ်ရန်\n"
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
            "/myvoice start|confirm|status|delete - ကိုယ်ပိုင်အသံ Setup Tool\n"
            "/voiceclone <name> - သိမ်းထားသော ကိုယ်ပိုင်အသံဖြင့် မြန်မာစာ TTS ထုတ်ရန် (GPU host လိုအပ်)\n"
            "/recapvoiceclone [profile] - ကိုယ်ပိုင်အသံ Narration WAV + ခန့်မှန်း SRT ကို Source Video Render ထဲချိတ်ရန်\n"
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
        if not paid_ai_allowed():
            ai_line = "OpenAI Script API: Free-only mode ကြောင့် ပိတ်ထားသည် (အခကြေးငွေရှိနိုင်သော API မခေါ်ပါ)"
        elif ai_status["configured"]:
            ai_line = f"OpenAI Script API: ချိတ်ထားသည် ({ai_status['model']})"
        else:
            ai_line = "OpenAI Script API: မချိတ်ရသေးပါ (Render တွင် OPENAI_API_KEY လိုအပ်သည်)"
        gemini_status = gemini_script_status()
        script_status = script_provider_status()
        script_line = (
            f"AI Script Primary: {script_status['provider'].upper()} ({script_status['model']})"
            if script_status["configured"]
            else f"AI Script Primary: {script_status['provider'].upper()} မပြင်ဆင်ရသေးပါ"
        )
        gemini_line = (
            "Gemini API: Free-only mode ကြောင့် ပိတ်ထားသည်"
            if not paid_ai_allowed()
            else f"Gemini API: ချိတ်ထားသည် ({gemini_status['model']})"
            if gemini_status["configured"]
            else "Gemini API: မချိတ်ရသေးပါ (GEMINI_API_KEY နှင့် Paid AI ခွင့်ပြုချက် လိုအပ်သည်)"
        )
        await update.message.reply_text(
            "NEXORA Bot: အလုပ်လုပ်နေပါတယ်။\n"
            f"{ai_line}\n"
            f"{script_line}\n"
            f"{gemini_line}\n"
            "AI Script: /aiscript <title> ပြီးနောက် Verified Research Notes ထည့်ပါ။\n"
            "လုပ်ဆောင်နိုင်မှု: Auto research + Worksheets + Voice-over TXT + TTS MP3 + အချိန်ကိုက် SRT + Licensed Video Footage + Narration/SRT MP4 render\n"
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
    pending_consent = context.user_data.pop("pending_voice_profile_consent", None)
    pending_backup = context.user_data.pop("pending_voice_profile_import", None)
    if pending or pending_profile or pending_consent or pending_backup:
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
            "Wikimedia Commons၊ Europeana၊ Internet Archive နှင့် YouTube CC BY မှတ်တမ်းများကို ရှာပေးမည်။ YouTube ရှာရန် YOUTUBE_DATA_API_KEY လိုအပ်သည်။"
        )
        return
    await update.message.reply_text("Commons၊ Europeana၊ Internet Archive နှင့် (API key ရှိပါက) YouTube CC BY/Trailer ရည်ညွှန်းလင့်ခ်များကို ရှာနေပါတယ်...")
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
    try:
        archive_sources = await asyncio.to_thread(search_internet_archive_licensed_video, query, 5)
        results.extend(archive_sources)
    except InternetArchiveSearchError as exc:
        errors.append("Internet Archive: " + str(exc))
    try:
        trailer_refs = await asyncio.to_thread(search_official_trailer_references, query, 4)
        results.extend(trailer_refs)
    except YouTubeCCSearchError as exc:
        errors.append("YouTube trailer references: " + str(exc))
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
        if source_name == "YouTube Trailer Reference":
            download_note = (
                "Trailer/Clip ရည်ညွှန်းလင့်ခ်သာဖြစ်သည်။ Channel သည် တရားဝင် Official ဖြစ်ကြောင်း အတည်မပြုထားပါ။ "
                "YouTube stream ကို download/extract မလုပ်ပါ။ MP4 ထဲထည့်ရန် Creator/rights holder ထံမှ သီးခြားခွင့်ပြုချက်နှင့် မူရင်းဖိုင်လိုအပ်သည်။"
            )
        elif source_name == "YouTube":
            download_note = (
                "YouTube CC BY metadata တွေ့ရှိသည်။ Uploader က footage/audio အားလုံး၏ အခွင့်အရေးပိုင်ရှင်ဖြစ်ကြောင်း "
                "နှင့် CC BY သက်ဆိုင်မှုကို လူကိုယ်တိုင်စစ်ပါ။ NEXORA သည် YouTube stream ကို download/extract မလုပ်ပါ။ "
                "Creator ထံမှ ခွင့်ပြုထားသော မူရင်းဖိုင်ရရှိမှသာ ထုတ်လုပ်မှုတွင် ထည့်သုံးပါ။"
            )
        elif source_name == "Internet Archive":
            download_note = str(item.get("notice") or "Uploader ထည့်သွင်းထားသော လိုင်စင်ကို မူရင်းအခွင့်အရေးပိုင်ရှင်ထံမှ အတည်ပြုပါ။ Auto-download ပိတ်ထားသည်။")
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


async def licensedownload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search Commons, then Internet Archive, for an exact-title reusable source."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /licensedownload <ခေါင်းစဉ်>\n"
            "Wikimedia Commons မှ CC0/CC BY/CC BY-SA/Public Domain နှင့် "
            "Internet Archive မှ CC0/Public Domain Mark ကိုသာ စစ်ပြီး Download လုပ်ပါမယ်။"
        )
        return
    await update.message.reply_text(
        "Wikimedia Commons ကို ဦးစားပေးရှာပြီး မရပါက Internet Archive မှ "
        "CC0/Public Domain Mark မူရင်း Video ကို စစ်ဆေး Download လုပ်နေပါတယ်..."
    )
    try:
        from licensed_source_router import (
            LicensedSourceRouterError,
            discover_and_download_licensed_source,
        )

        work_root = Path(os.getenv("NEXORA_WORK_DIR", "/tmp/nexora-work"))
        work_root.mkdir(parents=True, exist_ok=True)
        chat_id = str(update.effective_chat.id if update.effective_chat else "unknown")
        safe_chat = re.sub(r"[^0-9-]", "", chat_id)
        session_dir = work_root / safe_chat
        session_dir.mkdir(parents=True, exist_ok=True)

        output, source, provider = await asyncio.to_thread(
            discover_and_download_licensed_source, query, session_dir
        )
        prior = context.user_data.get("video_render") or {}
        defaults = context.user_data.get("video_edit_defaults") or {}
        selected_effect = str(prior.get("effect_preset", defaults.get("effect_preset", "cinematic")))
        selected_audio = str(prior.get("audio_preset", defaults.get("audio_preset", "voice")))
        selected_transition = str(prior.get("transition", defaults.get("transition", "fade")))
        selected_motion = str(prior.get("motion_preset", defaults.get("motion_preset", "none")))
        selected_subtitle_style = str(prior.get("subtitle_style", defaults.get("subtitle_style", "classic")))
        selected_burn_subtitles = bool(prior.get("burn_subtitles", defaults.get("burn_subtitles", False)))
        selected_fade_seconds = float(prior.get("fade_seconds", defaults.get("fade_seconds", 0.6)))
        selected_quality = str(prior.get("quality_preset", defaults.get("quality_preset", "720p")))
        artist = str(source.get("artist", "Unknown"))
        attribution = str(source.get("attribution") or artist)
        context.user_data["video_render"] = {
            "mode": "source_video",
            "platform": context.user_data.get("platform", "youtube"),
            "effect_preset": selected_effect,
            "audio_preset": selected_audio,
            "transition": selected_transition,
            "motion_preset": selected_motion,
            "subtitle_style": selected_subtitle_style,
            "burn_subtitles": selected_burn_subtitles,
            "fade_seconds": selected_fade_seconds,
            "quality_preset": selected_quality,
            "source_video_path": str(output),
            "source_metadata": {
                "title": str(source.get("title", "")),
                "license": str(source.get("license", "")),
                "license_uri": str(source.get("license_uri", "")),
                "artist": artist,
                "attribution": attribution,
                "source_page": str(source.get("source_page", "")),
                "provider": provider,
            },
            "narration_audio": None,
            "subtitles": None,
        }
        archive_warning = (
            "\n\nသတိပြုရန်: Internet Archive လိုင်စင်အချက်အလက်သည် uploader ထည့်ထားသော metadata ဖြစ်သည်။ "
            "မထုတ်ဝေမီ မူရင်းအခွင့်အရေး/Attribution ကို ထပ်မံစစ်ဆေးပါ။"
            if provider.startswith("Internet Archive") else ""
        )
        await update.message.reply_text(
            f"Server-side Download အောင်မြင်ပါပြီ။\nProvider: {provider}\n"
            f"ခေါင်းစဉ်: {source.get('title', '')}\n"
            f"လိုင်စင်: {source.get('license', '')}\n"
            f"ဖန်တီးသူ: {artist[:160]}\n"
            f"Attribution: {attribution[:300]}\n"
            f"Source: {source.get('source_page', '')}\n\n"
            "ဒီဖိုင်ကို Telegram မှ ပြန်ပို့စရာမလိုပါ။ မြန်မာ Narration MP3 နှင့် UTF-8 SRT ကို ပို့ပြီး "
            "/sourcevideo finish လုပ်ပါ။" + archive_warning +
            "\n\nမှတ်ချက်: Render Free ရဲ့ /tmp ဖိုင်တွေဟာ restart/deploy လုပ်ရင် ပျောက်နိုင်ပါတယ်။ Persistent Disk မချိတ်ရသေးပါ။"
        )
    except Exception as exc:
        from licensed_source_router import LicensedSourceRouterError
        if isinstance(exc, LicensedSourceRouterError):
            await update.message.reply_text(str(exc)[:3000])
            return
        log.exception("Licensed source video download failed")
        await update.message.reply_text("ခွင့်ပြုထားသော Video ကို Download မလုပ်နိုင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")


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


async def dailyrecap_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run the existing licensed recap pipeline for today's three distinct Daily Auto picks."""
    if not update.message:
        return
    requested = (context.args[0].strip().lower() if context.args else "all")
    platforms = ("youtube", "facebook", "tiktok") if requested == "all" else (requested,)
    if any(platform not in {"youtube", "facebook", "tiktok"} for platform in platforms):
        await update.message.reply_text(
            "အသုံးပြုပုံ: /dailyrecap [youtube|facebook|tiktok|all]\n"
            "မရေးထားပါက ယနေ့ရွေးထားသော Platform သုံးခုလုံးကို အစဉ်လိုက် စမ်းသပ်ထုတ်လုပ်ပါမယ်။"
        )
        return

    await update.message.reply_text(
        "ယနေ့ Daily Report မှ Platform သီးခြားခေါင်းစဉ်များကို ပြန်တွက်ပြီး Metadata၊ ဇာတ်လမ်းရင်းမြစ်၊ "
        "မြန်မာ MP3/SRT နှင့် ခွင့်ပြုထားသော footage ရှိ/မရှိကို စစ်ဆေးနေပါတယ်။\n"
        "အရေးကြီးချက်: Daily Auto သည် ရွေးချယ်မှုနှင့် research ကို အလိုအလျောက်လုပ်နိုင်သော်လည်း "
        "YouTube/Facebook ၄၆–၆၀ မိနစ် MP4 သုံးပိုင်းကို အလိုအလျောက်ပြီးစီးမည်ဟု မဆိုလိုပါ။ "
        "အရှည်အပြည့် မူပိုင်ခွင့်ခွင့်ပြုထားသော မူရင်း Video မရှိလျှင် MP4 မထုတ်ဘဲ draft/MP3/SRT အဆင့်တွင်သာ ရပ်ပါမယ်။\n"
        "Netflix/Crunchyroll သို့မဟုတ် အခြားကာကွယ်ထားသော Streaming Service မှ Full Movie ကို မဆွဲယူပါ။ "
        "မကိုက်ညီသော footage ကို အစားထိုးမသုံးပါ။"
    )
    try:
        from datetime import datetime
        from types import SimpleNamespace
        from zoneinfo import ZoneInfo
        from daily_auto import TITLE_CATEGORIES, select_daily_platform_titles
        from pageview_trends import fetch_category_pageviews

        local_today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
        pageviews = await asyncio.to_thread(fetch_category_pageviews, TITLE_CATEGORIES)
        selected = select_daily_platform_titles(local_today, pageviews)
        chosen = [selected[platform] for platform in platforms]
        if len({item.get("title") for item in chosen}) != len(chosen):
            await update.message.reply_text(
                "ယနေ့ရွေးချယ်မှုတွင် ခေါင်းစဉ်ထပ်နေမှုရှိသဖြင့် မှားယွင်းသော Recap မထုတ်ရန် ရပ်ထားပါတယ်။"
            )
            return

        previous_platform = context.user_data.get("platform", "youtube")
        try:
            for platform in platforms:
                item = selected[platform]
                await update.message.reply_text(
                    f"▶️ {platform.upper()} စတင်ပါပြီ — {item.get('category')}: {item.get('title')}"
                )
                context.user_data["platform"] = platform
                proxy_message = SimpleNamespace(
                    text=f"/recapvideo {item.get('title', '')}",
                    reply_text=update.message.reply_text,
                    reply_video=update.message.reply_video,
                    reply_document=update.message.reply_document,
                )
                await recapvideo_cmd(SimpleNamespace(message=proxy_message), context)
        finally:
            context.user_data["platform"] = previous_platform
    except Exception:
        log.exception("Daily platform recap runner failed")
        await update.message.reply_text(
            "Daily Recap စတင်မှု မအောင်မြင်ပါ။ /status နှင့် ရင်းမြစ်/API အခြေအနေကို စစ်ဆေးပါ။"
        )


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
        duration_seconds = _subtitle_duration_seconds(srt_text)
        duration_gate = validate_platform_recap_duration(platform, duration_seconds)
        if not duration_gate["ok"]:
            # Do not produce an MP4 from an under-length synopsis or narration.
            minimum = duration_gate.get("minimum_seconds", 0) // 60
            maximum = duration_gate.get("maximum_seconds", 0) // 60
            actual = round(duration_seconds / 60, 1)
            await update.message.reply_text(
                f"{platform.upper()} အတွက် Movie MP4 မထုတ်နိုင်သေးပါ။ Narration ကြာချိန် {actual} မိနစ်သာ ရှိပါတယ်။ "
                f"လိုအပ်ချက်မှာ {minimum}–{maximum} မိနစ် ဖြစ်ပါတယ်။\n"
                "မပြည့်မီသေးသော Narration ကို အတင်းဖြည့်ခြင်း၊ ဇာတ်ကွက်ဖန်တီးဖြည့်ခြင်း မလုပ်ထားပါ။ "
                "Verified Plot Notes ပိုမိုရရှိမှသာ Long-form ကို ဆက်ထုတ်ပါမယ်။"
            )
            return
        import tempfile
        fallback_source_notes = []
        fallback_source_errors = []
        archive_source = None
        if not source:
            # Try independent discovery providers when Commons has no exact reusable match.
            # Internet Archive CC0/Public Domain Mark exact-title files can be rendered; other providers remain discovery-only.
            try:
                archive_leads = await asyncio.to_thread(
                    search_internet_archive_licensed_video, query, 4
                )
                archive_source = next((item for item in archive_leads if item.get("download_enabled") and item.get("files")), None)
                for item in archive_leads[:3]:
                    files = ", ".join(
                        f"{entry.get('name')} ({round((entry.get('duration_seconds') or 0) / 60, 1)} min)"
                        for entry in item.get("files", [])[:2]
                    )
                    fallback_source_notes.append(
                        f"Internet Archive: {item.get('title', 'Untitled')} | {item.get('license', 'rights unknown')} | "
                        f"{item.get('source_page', '')} | Files: {files} "
                        ("(CC0/Public Domain Mark)" if item.get("download_enabled") else "(rights metadata မပြည့်စုံ)")
                    )
            except Exception as exc:
                fallback_source_errors.append("Internet Archive: " + str(exc)[:140])
            # Additional institutional film libraries for this exact title.
            # These are search pages only; NEXORA never bypasses access controls
            # or downloads files until a direct reusable-rights record is available.
            from urllib.parse import quote_plus
            fallback_source_notes.extend([
                "Library of Congress Film & Video search: https://www.loc.gov/film-and-videos/?q="
                + quote_plus(metadata.get("title", query)),
                "US National Archives Catalog search: https://catalog.archives.gov/search?q="
                + quote_plus(metadata.get("title", query)),
                "Prelinger Archives collection: https://archive.org/details/prelinger",
            ])
            try:
                europeana_leads = await asyncio.to_thread(
                    search_europeana_licensed_video, query, 4, search_titles
                )
                for item in europeana_leads[:3]:
                    page = str(item.get("source_page") or "").strip()
                    if page:
                        fallback_source_notes.append(
                            f"Europeana: {item.get('title', 'Untitled')} | {item.get('license', 'rights unknown')} | {page} "
                            "(Provider media ကို အလိုအလျောက် download မလုပ်ပါ)"
                        )
            except Exception as exc:
                fallback_source_errors.append("Europeana: " + str(exc)[:140])
            try:
                youtube_leads = await asyncio.to_thread(search_youtube_cc_videos, query, 4)
                for item in youtube_leads[:3]:
                    watch_url = str(item.get("url") or "").strip()
                    if watch_url:
                        fallback_source_notes.append(
                            f"YouTube CC: {item.get('title', 'Untitled')} | {item.get('license', 'CC metadata')} | {watch_url} "
                            "(Uploader ထံမှ original file/rights ကို အတည်ပြုရမည်; stream download မလုပ်ပါ)"
                        )
            except Exception as exc:
                fallback_source_errors.append("YouTube CC: " + str(exc)[:140])

        if not source and not archive_source:
            # Do not send audio-only deliverables when the requested movie footage is unavailable.
            await update.message.reply_text(
                f"{metadata.get('title', query)} အတွက် ခေါင်းစဉ်နှင့် ကိုက်ညီပြီး "
                "ပြန်လည်အသုံးပြုခွင့်ကို အတည်ပြုနိုင်သော မူရင်းဗီဒီယို မရရှိပါ။\n"
                "မသက်ဆိုင်သော footage ဖြင့် MP4 မထုတ်ထားပါ။ MP3/SRT ကို ပို့ပေးထားပါတယ်။\n\n"
                "ကိုယ်ပိုင် သို့မဟုတ် လိုင်စင်ရ Video ရှိပါက /sourcevideo workflow မှာ အသုံးပြုနိုင်ပါတယ်။"
                + (
                    "\n\n🔎 အခြားရင်းမြစ်များမှ တွေ့ရှိသော ခွင့်ပြုချက်စစ်ဆေးရန် Leads:\n"
                    + "\n".join(fallback_source_notes[:5])
                    if fallback_source_notes else
                    "\n\nအခြားရင်းမြစ်များတွင်လည်း အသုံးပြုခွင့်ရှိသော အလိုအလျောက် Download လုပ်နိုင်သည့် မူရင်းဖိုင် မတွေ့ပါ။"
                )
                + (
                    "\n\nProvider စစ်ဆေးမှုမှတ်ချက်: " + " | ".join(fallback_source_errors)
                    if fallback_source_errors else ""
                )
            )
            return
        if platform in {"youtube", "facebook"}:
            audio_bytes, subtitle_bytes = build_recap_video_sidecars(audio, srt_text)
            public = urlparse(str(PUBLIC_URL or ""))
            rendered_paths = []
            render_failure = ""
            if (source or archive_source) and public.scheme == "https" and public.netloc:
                try:
                    work_root = Path(os.getenv("NEXORA_WORK_DIR", "/tmp/nexora-work"))
                    chat_id = str(update.effective_chat.id if update.effective_chat else "unknown")
                    safe_chat = re.sub(r"[^0-9-]", "", chat_id) or "unknown"
                    output_dir = work_root / safe_chat / "exports"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    batch_dir = output_dir / ("nexora_auto_" + secrets.token_hex(8))
                    await update.message.reply_text(
                        ("Commons" if source else "Internet Archive Public Domain/CC0")
                        + " မှ ခေါင်းစဉ်ကိုက်ညီသော Video ရင်းမြစ် ရရှိပါပြီ။ Server ပေါ်သို့ Download လုပ်ပြီး "
                        "မူရင်း footage ကြာချိန် လုံလောက်မှုကို စစ်ကာ သုံးပိုင်း MP4 Render လုပ်နေပါတယ်..."
                    )
                    render_longform = render_licensed_longform_parts if source else render_internet_archive_longform_parts
                    rendered_paths = await asyncio.to_thread(
                        render_longform,
                        source if source else archive_source,
                        ("nexora_recap_voiceover.mp3", audio_bytes),
                        ("nexora_recap_subtitles.srt", subtitle_bytes),
                        batch_dir,
                        platform,
                    )
                    if len(rendered_paths) != 3:
                        raise RecapPartitionError("သုံးပိုင်း MP4 အပြည့်အစုံ မရရှိပါ။")
                except Exception as exc:
                    for rendered_path in rendered_paths:
                        Path(rendered_path).unlink(missing_ok=True)
                    rendered_paths = []
                    log.exception("Automatic three-part licensed longform render failed")
                    render_failure = str(exc)[:350]
            elif source or archive_source:
                render_failure = "Render download link အတွက် HTTPS Public URL မသတ်မှတ်ရသေးပါ။"

            if rendered_paths:
                voice_file = BytesIO(audio_bytes)
                voice_file.name = "nexora_recap_voiceover.mp3"
                await update.message.reply_document(
                    document=InputFile(voice_file, filename=voice_file.name),
                    caption="အလိုအလျောက်ထုတ်ထားသော Recap Narration MP3 မူရင်းဖိုင်ပါ။",
                )
                subtitle_file = BytesIO(subtitle_bytes)
                subtitle_file.name = "nexora_recap_subtitles.srt"
                await update.message.reply_document(
                    document=InputFile(subtitle_file, filename=subtitle_file.name),
                    caption="အလိုအလျောက်ထုတ်ထားသော အချိန်ကိုက် မြန်မာ SRT မူရင်းဖိုင်ပါ။",
                )
                attribution = (
                    build_licensed_attribution_note(source, metadata.get("title", query), metadata.get("source", ""))
                    if source else (
                        f"Title: {metadata.get('title', query)}\nSource: {archive_source.get('source_page', '')}\n"
                        f"License: {archive_source.get('license', '')} ({archive_source.get('license_uri', '')})\n"
                        f"Uploader/Creator: {archive_source.get('artist', 'Unknown')}\n"
                    )
                )
                credit_file = BytesIO(attribution.encode("utf-8-sig"))
                credit_file.name = "nexora_footage_attribution.txt"
                await update.message.reply_document(
                    document=InputFile(credit_file, filename=credit_file.name),
                    caption="အသုံးပြုထားသော footage ၏ Source၊ License နှင့် Creator မှတ်တမ်းပါ။",
                )

                now = time.time()
                for old_token, record in list(DOWNLOAD_LINKS.items()):
                    if float(record.get("expires_at", 0)) <= now:
                        Path(str(record.get("path", ""))).unlink(missing_ok=True)
                        DOWNLOAD_LINKS.pop(old_token, None)
                while len(DOWNLOAD_LINKS) + len(rendered_paths) > MAX_DOWNLOAD_LINKS:
                    if not DOWNLOAD_LINKS:
                        break
                    oldest = min(
                        DOWNLOAD_LINKS,
                        key=lambda key: float(DOWNLOAD_LINKS[key].get("created_at", 0)),
                    )
                    old_record = DOWNLOAD_LINKS.pop(oldest)
                    Path(str(old_record.get("path", ""))).unlink(missing_ok=True)
                links = []
                created_tokens = []
                for index, rendered_path in enumerate(rendered_paths, 1):
                    token = secrets.token_urlsafe(32)
                    created_tokens.append(token)
                    DOWNLOAD_LINKS[token] = {
                        "path": str(rendered_path),
                        "filename": f"nexora_{platform}_part_{index}.mp4",
                        "created_at": now,
                        "expires_at": now + DOWNLOAD_LINK_TTL_SECONDS,
                    }
                    links.append(f"Part {index}: {PUBLIC_URL.rstrip('/')}/download/{token}")
                try:
                    await update.message.reply_text(
                        "ပြီးပါပြီ — YouTube/Facebook အတွက် ၁၅–၂၀ မိနစ်စီ သုံးပိုင်း MP4 ထုတ်ပြီးပါပြီ။ "
                        "အပိုင်းတစ်ခုစီတွင် သီးခြား narration၊ SRT နှင့် မူရင်း licensed footage အပိုင်းမတူ ပါဝင်ပါတယ်။\n"
                        + "\n".join(links)
                        + "\nDownload Link များသည် ၂၄ နာရီသာ အသုံးပြုနိုင်ပြီး Render restart/deploy လုပ်ပါက ပျက်နိုင်ပါတယ်။"
                    )
                except Exception:
                    for token in created_tokens:
                        DOWNLOAD_LINKS.pop(token, None)
                    for rendered_path in rendered_paths:
                        Path(rendered_path).unlink(missing_ok=True)
                    raise
                return

            # The user requested a movie MP4, not an audio-only fallback.
            if not source and not archive_source:
                await update.message.reply_text(
                    "Commons တွင် ခေါင်းစဉ်ကိုက်ညီသော ပြန်လည်အသုံးပြုခွင့်ရှိသည့် Video မတွေ့ပါ။ "
                    "Europeana/YouTube CC ရှာဖွေမှုများသည် မှတ်တမ်း/Provider link သာဖြစ်ပြီး အလိုအလျောက် Download ခွင့်မပြုသောကြောင့် "
                    "မူရင်းဖိုင်ကို Creator ထံမှ ခွင့်ပြုချက်ဖြင့် ရယူရန်လိုပါတယ်။ /clipsource ဖြင့် အခြားရင်းမြစ်များကို စစ်နိုင်ပါတယ်။ "
                    "MP4 ကို မထုတ်ထားပါ။"
                )
            else:
                await update.message.reply_text(
                    "ခွင့်ပြုထားသော Video ရင်းမြစ်ကို တွေ့သော်လည်း ၄၆–၆၀ မိနစ် အပြည့်အဝ မလုံလောက်ခြင်း၊ "
                    "သို့မဟုတ် Render/Download အမှားကြောင့် သုံးပိုင်း MP4 မထုတ်နိုင်ပါ။ "
                    "အတိုဗီဒီယိုကို loop မလုပ်ဘဲ MP3/SRT မူကြမ်းအဖြစ်သာ ထားပါတယ်။"
                    + (f"\nအကြောင်းရင်း: {render_failure}" if render_failure else "")
                )
            return
        await update.message.reply_text("လိုင်စင်အမျိုးအစားနှင့် ခေါင်းစဉ်ကို စစ်ပြီး licensed footage + narration + SRT + MP4 ပြင်ဆင်နေပါတယ်...")
        with tempfile.TemporaryDirectory(prefix="nexora_recap_video_") as temp:
            output = os.path.join(temp, "nexora_recap_preview.mp4")
            render_source = source if source else archive_source
            await asyncio.to_thread(
                (render_licensed_narrated_preview if source else render_internet_archive_narrated_preview),
                render_source, audio, srt_text, output, platform, max_duration
            )
            with open(output, "rb") as video_file:
                await update.message.reply_video(
                    video=InputFile(video_file, filename="nexora_recap_preview.mp4"),
                    supports_streaming=True,
                    caption=(
                        f"NEXORA {platform.upper()} — Recap Preview (ကြာချိန် ၄–၇ မိနစ်)\n"
                        f"ခေါင်းစဉ်: {metadata.get('title', query)} | နိုင်ငံ: {', '.join(countries)}\n"
                        f"ဇာတ်လမ်းရင်းမြစ်: {plot_source}\n"
                        f"Footage: {render_source.get('source_page', '')}\n"
                        f"လိုင်စင်: {render_source.get('license', '')} | ဖန်တီးသူ: {str(render_source.get('artist', 'Unknown'))[:160]}\n"
                        "Footage Source၊ License နှင့် Creator အချက်အလက်ကို ဖော်ပြထားပါတယ်။"
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
    """Research titles across anime, movies and TV-series catalogues independently."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /multisourceresearch <Anime/Cartoon/Donghua/Movie/TV Series အမည်>\n"
            "Anime (AniList + Tenrai/MAL + Wikidata), Movie (TMDB + Wikidata + Gemini), "
            "TV Series (TVmaze) ကို တစ်ပြိုင်နက် သီးခြားစစ်ဆေးပေးပါမယ်။"
        )
        return
    await update.message.reply_text(
        "Anime/Animation၊ Movie နဲ့ TV Series ရင်းမြစ်တွေကို သီးခြားခွဲပြီး "
        "တစ်ပြိုင်နက် စစ်ဆေးနေပါတယ်..."
    )
    try:
        report = await asyncio.to_thread(research_all_media_sources, query)
        output = format_all_media_source_report(report)
    except Exception:
        log.exception("Universal multi-source research failed")
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
    provider = "TVmaze"
    if not result.get("found"):
        # Kitsu is a free fallback; require independent non-Indian origin verification.
        from multi_source_research import research_anime_sources
        verified = await asyncio.to_thread(research_anime_sources, query)
        anime = verified.get("anilist") or {}
        wikidata = verified.get("wikidata") or {}
        countries = wikidata.get("countries") or []
        country_code = str(anime.get("country") or "").upper()
        country_text = " ".join(str(x) for x in countries).casefold()
        if verified.get("india_excluded") or country_code == "IN" or "india" in country_text:
            await update.message.reply_text("အိန္ဒိယမူရင်းဖြစ်ကြောင်း တွေ့ရှိသဖြင့် ဒီ Project အတွက် Episode ရင်းမြစ်ကို ပယ်ချထားပါတယ်။")
            return
        if not countries and not country_code:
            await update.message.reply_text("TVmaze Episode မရရှိပါ။ Kitsu ကို ဆက်စစ်ရန် မူရင်းနိုင်ငံ အတည်ပြုချက် လိုအပ်ပါတယ်။")
            return
        result = await asyncio.to_thread(fetch_kitsu_episode_summaries, query, 5)
        provider = "Kitsu"
        if not result.get("found"):
            # Bangumi is a third free fallback for episode metadata. Country verification
            # above remains mandatory; no plot is invented when Bangumi has no description.
            from bangumi_episode_research import fetch_bangumi_episode_summaries
            result = await asyncio.to_thread(fetch_bangumi_episode_summaries, query, 5)
            provider = "Bangumi"
            if not result.get("found"):
                await update.message.reply_text(
                    "TVmaze၊ Kitsu နှင့် Bangumi တို့မှ အသုံးပြုနိုင်သော Episode အချက်အလက် မရရှိပါ။\n"
                    + str(result.get("status") or "")
                )
                return
        result["country"] = ", ".join(str(x) for x in countries) if countries else country_code
    lines = [
        f"Episode Research — {result.get('title', query)}",
        f"နိုင်ငံ: {result.get('country') or 'မဖော်ပြထား'}",
        f"{provider} ရင်းမြစ်မှ Episode summary အတိုများ (တစ်ခုလျှင် စာလုံး ၂၄၀ အထိ)။",
        "",
    ]
    for episode in result.get("episodes", []):
        season = episode.get("season") or "?"
        number = episode.get("number") or "?"
        lines.append(
            f"S{season} E{number} — {episode.get('title', 'Untitled')} "
            f"({episode.get('airdate') or 'ရက်စွဲမရှိ'})"
        )
        if episode.get("summary_excerpt"):
            lines.append(episode["summary_excerpt"])
        elif provider == "Bangumi":
            lines.append("Episode အကျဉ်း: Bangumi မှ မဖော်ပြထားပါ (ခေါင်းစဉ်/နံပါတ်/ရက်စွဲသာ ရရှိသည်)။")
        if episode.get("source"):
            lines.append("Source: " + episode["source"])
        lines.append("")
    lines.append(
        f"သတိပြုရန်: ဒီအချက်အလက်တွေဟာ {provider} ရဲ့ Episode summary အတိုများသာဖြစ်ပြီး "
        "အပြည့်အစုံ Recap script၊ ဇာတ်ဝင်ခန်း transcript သို့မဟုတ် အတည်ပြုပြီးဖြစ်ရပ်မှန် မဟုတ်ပါ။"
    )
    await update.message.reply_text("\n".join(lines), disable_web_page_preview=True)


async def episodeplots_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect episode-level plot leads from free catalogues without merging sources."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /episodeplots <Anime/Cartoon/Donghua Series အမည်>\n"
            "TVmaze၊ Kitsu နှင့် Bangumi တို့မှ ရရှိနိုင်သော Episode ဇာတ်ကွက်အကျဉ်းများကို "
            "ရင်းမြစ်တစ်ခုချင်းစီ သီးခြားစုစည်းပေးပါမယ်။"
        )
        return
    await update.message.reply_text(
        "Episode-level Plot များကို အခမဲ့ Catalogue သုံးခုမှ စုဆောင်းပြီး မူရင်းနိုင်ငံနှင့် ရင်းမြစ်ကို စစ်နေပါတယ်..."
    )
    try:
        report = await asyncio.to_thread(collect_episode_plots, query, 10)
        output = format_episode_plot_collection(report)
        if len(output) <= 3900:
            await update.message.reply_text(output, disable_web_page_preview=True)
        else:
            file_obj = BytesIO(output.encode("utf-8-sig"))
            file_obj.name = "nexora_episode_plot_collection.txt"
            await update.message.reply_document(
                document=InputFile(file_obj, filename=file_obj.name),
                caption=(
                    "Episode Plot Collection — ရင်းမြစ်တစ်ခုချင်းစီ သီးခြားစုထားသည်။ "
                    "ဇာတ်ကွက်မရှိသောအပိုင်းကို မခန့်မှန်းထားပါ။"
                ),
            )
    except Exception:
        log.exception("Episode plot collection failed")
        await update.message.reply_text("Episode Plot Collection မထုတ်နိုင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")


async def episodeverify_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compare episode alignment across public catalogues; never claim factual verification."""
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /episodeverify <Anime/Cartoon/Donghua Series အမည်>\n"
            "Episode နံပါတ်နှင့် ခေါင်းစဉ် ကိုက်ညီမှု၊ ရင်းမြစ်အလိုက် ကွာခြားမှုကို စစ်ပေးပါမယ်။"
        )
        return
    await update.message.reply_text("Episode Plot ရင်းမြစ်များကို စုဆောင်းပြီး တစ်ခုချင်းစီ တိုက်စစ်နေပါတယ်...")
    try:
        collection = await asyncio.to_thread(collect_episode_plots, query, 10)
        verification = verify_episode_plot_sources(collection)
        output = format_episode_plot_verification(verification)
        if len(output) <= 3900:
            await update.message.reply_text(output, disable_web_page_preview=True)
        else:
            file_obj = BytesIO(output.encode("utf-8-sig"))
            file_obj.name = "nexora_episode_plot_verification.txt"
            await update.message.reply_document(
                document=InputFile(file_obj, filename=file_obj.name),
                caption="Episode cross-source check — candidate match နှင့် discrepancy များကိုသာ ပြထားသည်။",
            )
    except Exception:
        log.exception("Episode plot verification failed")
        await update.message.reply_text("Episode Plot Cross-Source Check မထုတ်နိုင်ပါ။ နောက်မှ ထပ်စမ်းပါ။")


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


async def autoedit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Choose a genre-aware automatic edit profile before starting a render."""
    if not update.message:
        return
    from auto_edit_profile import build_auto_edit_profile, list_auto_edit_categories
    category = context.args[0].strip().lower() if context.args else "default"
    if category in {"list", "help"}:
        await update.message.reply_text(
            "🤖 NEXORA Auto Edit\nအသုံးပြုပုံ: /autoedit <category>\n"
            + "\n".join("• " + name for name in list_auto_edit_categories())
            + "\nDefault: cinematic movie profile\n"
            "ရွေးထားသော Profile ကို နောက် /sourcevideo workflow တွင် အလိုအလျောက်သုံးပါမယ်။"
        )
        return
    platform = context.user_data.get("platform", "youtube")
    profile = build_auto_edit_profile(category, platform)
    defaults = context.user_data.setdefault("video_edit_defaults", {})
    defaults.update(profile)
    session = context.user_data.get("video_render")
    if session is not None:
        session.update({k: profile[k] for k in ("effect_preset", "audio_preset", "transition", "motion_preset", "subtitle_style", "fade_seconds", "quality_preset")})
    await update.message.reply_text(
        "✨ Auto Edit Profile ရွေးပြီးပါပြီ\n"
        f"Category: {profile['category']}\n"
        f"Visual: {profile['effect_preset']} | Audio: {profile['audio_preset']} | Transition: {profile['transition']} | Motion: {profile['motion_preset']}\n"
        f"Subtitle Style: {profile['subtitle_style']}\n"
        "ဒီရွေးချယ်မှုတွေကို MP4 Render မှာ အလိုအလျောက်ထည့်ပါမယ်။"
    )


async def effect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List or select an automatic visual-effect preset for the active recap session."""
    if not update.message:
        return
    from video_effects import EFFECT_PRESETS
    selected = context.args[0].strip().lower() if context.args else ""
    if not selected or selected == "list":
        lines = ["🎬 NEXORA Auto Effects", "အသုံးပြုပုံ: /effect <preset>", ""]
        lines.extend(f"• {name}" for name in sorted(EFFECT_PRESETS))
        lines.append("Default: cinematic")
        await update.message.reply_text("\n".join(lines))
        return
    if selected not in EFFECT_PRESETS:
        await update.message.reply_text("မသိသော Effect ဖြစ်ပါတယ်။ /effect list ဖြင့် ရနိုင်တာတွေကြည့်ပါ။")
        return
    session = context.user_data.get("video_render")
    if session is None:
        context.user_data["video_render"] = {"effect_preset": selected}
    else:
        session["effect_preset"] = selected
    await update.message.reply_text(
        f"Effect ရွေးပြီးပါပြီ: {selected}\n/sourcevideo finish လုပ်တဲ့အခါ MP4 မှာ အလိုအလျောက်ထည့်ပါမယ်။"
    )


async def audiofx_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select a narration audio-mastering preset for the active source-video edit."""
    if not update.message:
        return
    from audio_mastering import AUDIO_PRESETS
    selected = context.args[0].strip().lower() if context.args else ""
    if not selected or selected == "list":
        await update.message.reply_text(
            "🎧 NEXORA Audio Mastering\nအသုံးပြုပုံ: /audiofx <preset>\n"
            + "\n".join("• " + name for name in sorted(AUDIO_PRESETS))
            + "\nDefault: voice"
        )
        return
    if selected not in AUDIO_PRESETS:
        await update.message.reply_text("မသိသော Audio preset ဖြစ်ပါတယ်။ /audiofx list ဖြင့် ကြည့်ပါ။")
        return
    session = context.user_data.get("video_render")
    if session is None:
        context.user_data["video_render"] = {"audio_preset": selected}
    else:
        session["audio_preset"] = selected
    await update.message.reply_text(
        f"Audio preset ရွေးပြီးပါပြီ: {selected}\nMP4 Render တွင် Narration အသံကို အလိုအလျောက်ညှိပါမယ်။"
    )


async def motion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Choose a subtle camera-motion preset for the next MP4 render."""
    if not update.message:
        return
    from motion_presets import MOTION_PRESETS
    selected = context.args[0].strip().lower() if context.args else ""
    if not selected or selected == "list":
        await update.message.reply_text(
            "🎥 NEXORA Camera Motion\nအသုံးပြုပုံ: /motion <preset>\n"
            + "\n".join("• " + name for name in sorted(MOTION_PRESETS))
            + "\nDefault: none"
        )
        return
    if selected not in MOTION_PRESETS:
        await update.message.reply_text("Motion preset မသိပါ။ /motion list ဖြင့် ကြည့်ပါ။")
        return
    defaults = context.user_data.setdefault("video_edit_defaults", {})
    defaults["motion_preset"] = selected
    session = context.user_data.get("video_render")
    if session is not None:
        session["motion_preset"] = selected
    await update.message.reply_text(f"Camera Motion ရွေးပြီးပါပြီ: {selected}")


async def transition_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Choose a cross-clip transition for the active source-video edit."""
    if not update.message: return
    from video_transitions import TRANSITIONS
    selected = context.args[0].strip().lower() if context.args else ""
    options = ["cut", *sorted(TRANSITIONS)]
    if not selected or selected == "list":
        await update.message.reply_text("🎞 NEXORA Transitions\nအသုံးပြုပုံ: /transition <preset>\n" + "\n".join("• " + name for name in options) + "\nDefault: fade (0.6s)")
        return
    if selected not in options:
        await update.message.reply_text("Transition မသိပါ။ /transition list ဖြင့် ကြည့်ပါ။")
        return
    session = context.user_data.get("video_render")
    if session is None: context.user_data["video_render"] = {"transition": selected}
    else: session["transition"] = selected
    await update.message.reply_text(f"Transition ရွေးပြီးပါပြီ: {selected}")

async def sourcevideo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Accept a creator-owned/licensed source video, narration, and SRT for MP4 rendering."""
    if not update.message:
        return
    action = context.args[0].lower() if context.args else "start"
    if action == "cancel":
        context.user_data.pop("creator_voice_assets", None)
        cancelled = context.user_data.pop("video_render", None) or {}
        downloaded_source = cancelled.get("source_video_path")
        if downloaded_source:
            try:
                Path(downloaded_source).unlink(missing_ok=True)
            except OSError:
                log.warning("Could not remove cancelled licensed source video")
        clip_dir = cancelled.get("source_video_clip_dir")
        if clip_dir:
            import shutil
            shutil.rmtree(clip_dir, ignore_errors=True)
        await update.message.reply_text("Source Video Recap ကို ပယ်ဖျက်ပြီး ယာယီ Video ဖိုင်များကို ရှင်းလင်းပြီးပါပြီ။")
        return
    session = context.user_data.get("video_render")
    if action == "finish":
        if not session or session.get("mode") != "source_video":
            await update.message.reply_text("အရင်ဆုံး /sourcevideo ပို့ပါ။")
            return
        missing = [
            label for key, label in (
                ("narration_audio", "မြန်မာ Narration MP3"),
                ("subtitles", "SRT"),
            ) if not session.get(key)
        ]
        if not (session.get("source_video") or session.get("source_video_path") or session.get("source_videos")):
            missing.insert(0, "မူရင်း Video Clip")
        if missing:
            await update.message.reply_text("မရသေးသောဖိုင်: " + "၊ ".join(missing))
            return
        await update.message.reply_text("သင်ပေးထားသော မူရင်း Video ကို Narration/SRT နှင့် ပေါင်းပြီး MP4 ထုတ်နေပါတယ်...")
        output_paths = []
        combined_source_path = None
        try:
            work_root = Path(os.getenv("NEXORA_WORK_DIR", "/tmp/nexora-work"))
            chat_id = str(update.effective_chat.id if update.effective_chat else "unknown")
            safe_chat = re.sub(r"[^0-9-]", "", chat_id) or "unknown"
            output_dir = work_root / safe_chat / "exports"
            output_dir.mkdir(parents=True, exist_ok=True)
            platform = session.get("platform", "youtube")
            source_clips = session.get("source_videos") or []
            source_video = None if source_clips else (session.get("source_video") or session.get("source_video_path"))
            batch_dir = output_dir / ("nexora_recap_" + secrets.token_hex(8))
            if source_clips:
                from source_video_renderer import concatenate_source_video_clips
                combined_source_path = batch_dir / "combined_source.mp4" if platform in {"youtube", "facebook"} else output_dir / ("nexora_source_" + secrets.token_hex(8) + ".mp4")
                combined_source_path.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(concatenate_source_video_clips, source_clips, combined_source_path, session.get("transition", "fade"))
                source_video = combined_source_path
            if platform in {"youtube", "facebook"}:
                output_paths = await asyncio.to_thread(
                    render_three_part_longform,
                    source_video,
                    session["narration_audio"],
                    session["subtitles"],
                    batch_dir,
                    platform,
                    session.get("effect_preset", "cinematic"),
                    session.get("audio_preset", "voice"),
                    session.get("motion_preset", "none"),
                    context.user_data.get("background_music"),
                    context.user_data.get("brand_logo"),
                    context.user_data.get("logo_position", "bottom-right"),
                    session.get("subtitle_style", "classic"),
                    session.get("burn_subtitles", False),
                    session.get("fade_seconds", 0.6),
                    session.get("quality_preset", "720p"),
                    music_volume=session.get("music_volume", 0.18),
                    music_ducking=session.get("music_ducking", True),
                )
            else:
                single_output = output_dir / ("nexora_recap_" + secrets.token_hex(8) + ".mp4")
                await asyncio.to_thread(
                    render_user_source_video,
                    source_video,
                    session["narration_audio"],
                    session["subtitles"],
                    single_output,
                    platform,
                    effect_preset=session.get("effect_preset", "cinematic"),
                    audio_preset=session.get("audio_preset", "voice"),
                    motion_preset=session.get("motion_preset", "none"),
                    background_music=context.user_data.get("background_music"),
                    brand_logo=context.user_data.get("brand_logo"),
                    logo_position=context.user_data.get("logo_position", "bottom-right"),
                    subtitle_style=session.get("subtitle_style", "classic"),
                    burn_subtitles=session.get("burn_subtitles", False),
                    fade_seconds=session.get("fade_seconds", 0.6),
                    quality_preset=session.get("quality_preset", "720p"),
                    music_volume=session.get("music_volume", 0.18),
                    music_ducking=session.get("music_ducking", True),
                )
                output_paths = [single_output]
            now = time.time()
            for old_token, record in list(DOWNLOAD_LINKS.items()):
                if float(record.get("expires_at", 0)) <= now:
                    Path(str(record.get("path", ""))).unlink(missing_ok=True)
                    DOWNLOAD_LINKS.pop(old_token, None)
            while len(DOWNLOAD_LINKS) + len(output_paths) > MAX_DOWNLOAD_LINKS:
                oldest = min(DOWNLOAD_LINKS, key=lambda key: float(DOWNLOAD_LINKS[key].get("created_at", 0)))
                old_record = DOWNLOAD_LINKS.pop(oldest)
                Path(str(old_record.get("path", ""))).unlink(missing_ok=True)
            base_url = (PUBLIC_URL or "").rstrip("/")
            if not base_url:
                raise SourceVideoRenderError("Download Link ထုတ်ရန် Public URL မရှိပါ။")
            links = []
            for index, rendered_path in enumerate(output_paths, 1):
                token = secrets.token_urlsafe(32)
                filename = (
                    f"nexora_{platform}_part_{index}.mp4"
                    if len(output_paths) == 3 else "nexora_tiktok_recap.mp4"
                )
                DOWNLOAD_LINKS[token] = {
                    "path": str(rendered_path),
                    "filename": filename,
                    "created_at": now,
                    "expires_at": now + DOWNLOAD_LINK_TTL_SECONDS,
                }
                label = f"Part {index}" if len(output_paths) == 3 else "TikTok"
                links.append(f"{label}: {base_url}/download/{token}")
            description = (
                "YouTube/Facebook Recap MP4 သုံးပိုင်းလုံး ပြီးပါပြီ။ တစ်ပိုင်းစီ ၁၅–၂၀ မိနစ်၊ "
                "Narration/SRT ကို အချိန်အလိုက် ခွဲထားပြီး မူရင်း Video အပိုင်းမတူများကို အသုံးပြုထားပါတယ်။"
                if len(output_paths) == 3 else
                "TikTok Recap MP4 ပြီးပါပြီ။ မြန်မာ Narration နှင့် SRT ထည့်ထားပြီး မူရင်း Video အသံကို အစားထိုးထားပါတယ်။"
            )
            await update.message.reply_text(
                description + "\n" + "\n".join(links) + "\n"
                "Download Link များသည် ၂၄ နာရီသာ အသုံးပြုနိုင်ပြီး Render restart/deploy လုပ်ပါက ပျက်နိုင်ပါတယ်။ "
                "ထုတ်ဝေမီ မူပိုင်ခွင့်၊ အသုံးပြုခွင့်နှင့် Attribution ကို စစ်ဆေးပါ။"
            )
        except (SourceVideoRenderError, RecapPartitionError) as exc:
            for path in output_paths:
                Path(path).unlink(missing_ok=True)
            await update.message.reply_text(str(exc))
            return
        except Exception:
            for path in output_paths:
                Path(path).unlink(missing_ok=True)
            log.exception("User source video recap render failed")
            await update.message.reply_text("MP4 ထုတ်လုပ်မှု မအောင်မြင်ပါ။ Video/Audio/SRT ဖိုင်များနှင့် Server Storage ကို ပြန်စစ်ပါ။")
            return
        finally:
            downloaded_source = session.get("source_video_path")
            if downloaded_source:
                try:
                    Path(downloaded_source).unlink(missing_ok=True)
                except OSError:
                    log.warning("Could not remove temporary licensed source video")
            clip_dir = session.get("source_video_clip_dir")
            if clip_dir:
                import shutil
                shutil.rmtree(clip_dir, ignore_errors=True)
            if combined_source_path:
                try:
                    Path(combined_source_path).unlink(missing_ok=True)
                except OSError:
                    log.warning("Could not remove temporary concatenated source video")
            context.user_data.pop("video_render", None)
            context.user_data.pop("creator_voice_assets", None)
        metadata = session.get("source_metadata") or {}
        if metadata:
            attribution_lines = [
                "Source attribution (လိုင်စင်စည်းကမ်းအရ ထည့်သွင်းရန်):",
                f"Title: {str(metadata.get('title', ''))[:250]}",
                f"License: {str(metadata.get('license', ''))[:120]}",
                f"Creator: {str(metadata.get('artist', 'Unknown'))[:200]}",
                f"Attribution: {str(metadata.get('attribution', ''))[:350]}",
                f"Source: {str(metadata.get('source_page', ''))[:500]}",
            ]
            await update.message.reply_text("\n".join(attribution_lines), disable_web_page_preview=True)
        return
    previous = context.user_data.get("video_render") or {}
    if previous.get("source_video_path"):
        Path(previous["source_video_path"]).unlink(missing_ok=True)
    if previous.get("source_video_clip_dir"):
        import shutil
        shutil.rmtree(previous["source_video_clip_dir"], ignore_errors=True)
    platform = context.user_data.get("platform", "youtube")
    selected_effect = str(previous.get("effect_preset", "cinematic"))
    selected_audio = str(previous.get("audio_preset", "voice"))
    defaults = context.user_data.get("video_edit_defaults") or {}
    selected_transition = str(previous.get("transition", defaults.get("transition", "fade")))
    selected_motion = str(previous.get("motion_preset", defaults.get("motion_preset", "none")))
    selected_subtitle_style = str(previous.get("subtitle_style", defaults.get("subtitle_style", "classic")))
    selected_burn_subtitles = bool(previous.get("burn_subtitles", defaults.get("burn_subtitles", False)))
    selected_fade_seconds = float(previous.get("fade_seconds", defaults.get("fade_seconds", 0.6)))
    selected_quality = str(previous.get("quality_preset", defaults.get("quality_preset", "720p")))
    selected_effect = str(previous.get("effect_preset", defaults.get("effect_preset", "cinematic")))
    selected_audio = str(previous.get("audio_preset", defaults.get("audio_preset", "voice")))
    chat_id = str(update.effective_chat.id if update.effective_chat else "unknown")
    safe_chat = re.sub(r"[^0-9-]", "", chat_id) or "unknown"
    clip_dir = Path(os.getenv("NEXORA_WORK_DIR", "/tmp/nexora-work")) / safe_chat / "source_clips" / secrets.token_hex(8)
    cached_voice_assets = context.user_data.pop("creator_voice_assets", None) or {}
    if cached_voice_assets.get("platform") not in {None, platform}:
        cached_voice_assets = {}
    context.user_data["video_render"] = {
        "mode": "source_video",
        "platform": platform,
        **cached_voice_assets,
        "effect_preset": selected_effect,
        "audio_preset": selected_audio,
        "transition": selected_transition,
        "motion_preset": selected_motion,
        "subtitle_style": selected_subtitle_style,
        "burn_subtitles": selected_burn_subtitles,
        "fade_seconds": selected_fade_seconds,
        "quality_preset": selected_quality,
        "source_video": None,
        "source_videos": [],
        "source_video_path": None,
        "source_video_clip_dir": str(clip_dir),
        "narration_audio": cached_voice_assets.get("narration_audio"),
        "subtitles": cached_voice_assets.get("subtitles"),
    }
    await update.message.reply_text(
        "Source Video Recap စတင်ပါပြီ။ သင်ပိုင်ဆိုင်သော သို့မဟုတ် အသုံးပြုခွင့်ရထားသော Video ကိုသာ ပို့ပါ။\n"
        "၁) MP4/MOV/M4V/WEBM Video Clip တစ်ခုလျှင် ၁၉ MiB အောက်၊ စုစုပေါင်း ၃၀ ခု/၁၈၀ MiB အထိ ပို့နိုင်သည်။\n"
        "၂) မြန်မာ Narration MP3/M4A/WAV/OGG (၂၀ MB အောက်) — ကိုယ်ပိုင်အသံ Command သုံးထားလျှင် auto-attach လုပ်ထားသည်။\n"
        "၃) UTF-8 .SRT စာတန်းထိုး (၁ MB အောက်)\n"
        "ဖိုင် ၃ မျိုးလုံးပို့ပြီး /sourcevideo finish ပို့ပါ။ /recapvoice myvoice သို့မဟုတ် /recapvoice3 myvoice ကို သုံးထားပါက Narration/SRT ကို အလိုအလျောက် ချိတ်ပေးထားနိုင်သည်။ /sourcevideo cancel ဖြင့် ရပ်နိုင်ပါတယ်။"
    )


async def render_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Use the video-footage-only source-video workflow; still-image rendering is disabled."""
    await sourcevideo_cmd(update, context)

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


async def myvoice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Friendly personal-voice setup and status tool."""
    if not update.message:
        return
    action = context.args[0].strip().lower() if context.args else "help"
    if action in {"start", "setup", "add"}:
        context.user_data["pending_voice_profile_consent"] = "ကိုယ်ပိုင်အသံ"
        context.user_data.pop("pending_voice_profile", None)
        await update.message.reply_text(
            "🎙️ ကိုယ်ပိုင်အသံ Setup\n\n"
            "၁။ ကိုယ့်အသံသာ ပါတဲ့ ၁၀–၃၀ စက္ကန့် အသံနမူနာကို တိတ်ဆိတ်တဲ့နေရာမှာ သဘာဝအတိုင်း ဖတ်ပြီး Record လုပ်ပါ။\n"
            "၂။ Background music/အခြားလူအသံ မပါစေဘဲ Mic ကို ပါးစပ်နှင့် ၁၅–၂၀ စင်တီမီတာ ခန့်ထားပါ။\n"
            "၃။ MP3/M4A/WAV/OGG ဖိုင် (၂၀ MB အောက်) အဖြစ် ဒီ Chat ထဲ ပို့နိုင်ပါတယ်။\n"
            "ဖတ်ရန် နမူနာ: မင်္ဂလာပါ။ ကျွန်တော်က NEXORA Myanmar Recap အတွက် ဇာတ်လမ်းတွေကို မြန်မာဘာသာနဲ့ ရှင်းပြပေးမှာ ဖြစ်ပါတယ်။\n"
            "၄။ ကိုယ့်အသံဖြစ်ကြောင်းနှင့် AI voice cloning အတွက် အသုံးပြုခွင့်ပေးကြောင်း အတည်ပြုရန် /myvoice confirm ပို့ပါ။\n\n"
            "အခြားသူ၏အသံကို ခွင့်ပြုချက်မရှိဘဲ မတင်ပါနှင့်။ အတည်ပြုပြီးမှသာ အသံဖိုင်ကို လက်ခံသိမ်းဆည်းပါမယ်။ "
            "Render Free မှာ clone မထုတ်နိုင်သေးဘဲ compatible GPU host လိုအပ်ပါတယ်။"
        )
        return
    if action == "confirm":
        pending_consent = context.user_data.pop("pending_voice_profile_consent", None)
        if not pending_consent:
            await update.message.reply_text("အရင် /myvoice start ပို့ပြီး အသံပိုင်ဆိုင်မှု/ခွင့်ပြုချက်ကို အတည်ပြုပါ။")
            return
        context.user_data["pending_voice_profile"] = pending_consent
        await update.message.reply_text(
            "အတည်ပြုချက် လက်ခံပြီးပါပြီ။ ကိုယ့်အသံသာ ပါသော ၁၀–၃၀ စက္ကန့် MP3/M4A/WAV/OGG ဖိုင်ကို အခု ပို့ပါ (၂၀ MB အောက်)။"
        )
        return
    if action == "test":
        try:
            profiles = load_voice_profiles(update.effective_user.id)
            profile = profiles.get("ကိုယ်ပိုင်အသံ")
            if not profile:
                await update.message.reply_text("စမ်းသပ်ရန် ကိုယ်ပိုင်အသံမရှိသေးပါ။ /myvoice start → /myvoice confirm → အသံဖိုင်ပို့ပါ။")
                return
            await update.message.reply_text("ကိုယ်ပိုင်အသံ နမူနာ WAV ကို ဖန်တီးနေပါတယ်။ GPU host လိုအပ်ပါတယ်...")
            sample_text = "မင်္ဂလာပါ။ ဒီအသံက ကျွန်တော့်ရဲ့ NEXORA ကိုယ်ပိုင်အသံ စမ်းသပ်နမူနာ ဖြစ်ပါတယ်။"
            audio = await synthesize_cloned_burmese_voice(sample_text, profile["filename"], profile["audio"])
            file_obj = BytesIO(audio)
            file_obj.name = "nexora_myvoice_test.wav"
            await update.message.reply_document(
                document=InputFile(file_obj, filename=file_obj.name),
                caption="ကိုယ်ပိုင်အသံ Clone စမ်းသပ် WAV။ အသံထွက်နှင့် သဘာဝကျမှုကို နားထောင်စစ်ဆေးပါ။",
                read_timeout=120,
                write_timeout=120,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            await update.message.reply_text(f"ကိုယ်ပိုင်အသံ စမ်းသပ်မရပါ: {exc}")
        return
    if action in {"status", "list"}:
        try:
            profiles = load_voice_profiles(update.effective_user.id)
        except (OSError, ValueError) as exc:
            await update.message.reply_text(f"Voice Storage ကို ဖတ်မရပါ: {exc}")
            return
        names = ", ".join(profiles) if profiles else "မသိမ်းရသေးပါ"
        default = profiles.get("ကိုယ်ပိုင်အသံ")
        sample_state = "ရှိပြီး" if default else "မရှိသေးပါ"
        await update.message.reply_text(
            f"🎙️ ကိုယ်ပိုင်အသံ အခြေအနေ\nProfile: {names}\n"
            f"Default ကိုယ်ပိုင်အသံ: {sample_state}\n"
            "Clone engine: VoxCPM2 (GPU host လိုအပ်)\n"
            "Persistent Disk + VOICE_PROFILE_DB_PATH မရှိလျှင် restart ပြီး အသံပျောက်နိုင်ပါတယ်။\n"
            "အသံတင်ရန် /myvoice start | အတည်ပြုရန် /myvoice confirm | စမ်းသပ်ရန် /myvoice test | အသံထုတ်ရန် /voiceclone ကို သုံးပါ။"
        )
        return
    if action in {"delete", "remove"}:
        try:
            profiles = load_voice_profiles(update.effective_user.id)
            delete_voice_profile(profiles, "ကိုယ်ပိုင်အသံ")
            save_voice_profiles(update.effective_user.id, profiles)
        except (OSError, ValueError) as exc:
            await update.message.reply_text(f"ကိုယ်ပိုင်အသံ ဖျက်မရပါ: {exc}")
            return
        context.user_data["custom_voice_profiles"] = profiles
        await update.message.reply_text("Default ကိုယ်ပိုင်အသံ Profile ကို ဖျက်ပြီးပါပြီ။")
        await send_voice_profile_backup(update, profiles, "ကိုယ်ပိုင်အသံဖျက်ပြီးနောက်")
        return
    await update.message.reply_text(
        "🎙️ NEXORA ကိုယ်ပိုင်အသံ Tool\n"
        "/myvoice start — ကိုယ့်အသံနမူနာ Wizard စတင်မည်\n"
        "/myvoice confirm — ကိုယ့်အသံဖြစ်ကြောင်းနှင့် cloning ခွင့်ပြုချက် အတည်ပြုရန်\n"
        "/myvoice status — သိမ်းထားသော Profile ကြည့်ရန်\n"
        "/myvoice test — ကိုယ်ပိုင်အသံ နမူနာ WAV ထုတ်စမ်းရန် (GPU host လိုအပ်)\n"
        "/myvoice delete — Default ကိုယ်ပိုင်အသံ ဖျက်ရန်\n"
        "/voiceclone ကိုယ်ပိုင်အသံ ပြီးနောက် စာသားကို စာကြောင်းအသစ်မှ ထည့်ပါ။\n"
        "မှတ်ချက်: ကိုယ့်အသံ/ခွင့်ပြုချက်ရသော အသံသာ သုံးပါ။ AI Clone အတွက် GPU host လိုအပ်ပါတယ်။"
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


async def quality_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Choose standard 720p or HD 1080p output dimensions."""
    if not update.message:
        return
    selected = context.args[0].strip().lower() if context.args else "720p"
    if selected not in {"720p", "1080p"}:
        await update.message.reply_text("အသုံးပြုပုံ: /quality 720p သို့မဟုတ် /quality 1080p")
        return
    defaults = context.user_data.setdefault("video_edit_defaults", {})
    defaults["quality_preset"] = selected
    session = context.user_data.get("video_render")
    if session is not None:
        session["quality_preset"] = selected
    note = "Render ပိုမြန်စေရန် 720p ကို Default ထားပါတယ်။" if selected == "720p" else "1080p သည် ပိုကြည်လင်သော်လည်း Render အချိန်/Memory ပိုလိုအပ်ပါတယ်။"
    await update.message.reply_text(f"Output Quality: {selected}\n{note}")


async def editstatus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all automatic editor settings before the user renders a video."""
    if not update.message:
        return
    defaults = context.user_data.get("video_edit_defaults") or {}
    session = context.user_data.get("video_render") or {}
    current = {**defaults, **session}
    lines = [
        "🧩 NEXORA EDIT SETTINGS",
        f"Platform: {current.get('platform', context.user_data.get('platform', 'youtube'))}",
        f"Output Quality: {current.get('quality_preset', '720p')}",
        f"Effect: {current.get('effect_preset', 'cinematic')}",
        f"Audio: {current.get('audio_preset', 'voice')}",
        f"Transition: {current.get('transition', 'fade')}",
        f"Camera Motion: {current.get('motion_preset', 'none')}",
        f"Subtitle Style: {current.get('subtitle_style', 'classic')}",
        f"Hard-burn subtitles: {'ON' if current.get('burn_subtitles', False) else 'OFF (soft subtitle)'}",
        f"Opening/Closing Fade: {float(current.get('fade_seconds', 0.6)):.1f}s",
        f"Background Music: {'READY' if context.user_data.get('background_music') else 'NOT SET'}",
        f"Background Music Volume: {float(current.get('music_volume', 0.18)):.2f}",
        f"Music Ducking: {'ON' if current.get('music_ducking', True) else 'OFF'}",
        f"Brand Logo: {'READY' if context.user_data.get('brand_logo') else 'NOT SET'}",
        f"Logo Position: {context.user_data.get('logo_position', 'bottom-right')}",
    ]
    await update.message.reply_text("\n".join(lines))


async def fade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set automatic opening/closing fade duration; zero disables fades."""
    if not update.message:
        return
    raw = context.args[0].strip().lower() if context.args else "0.6"
    if raw in {"off", "none", "0"}:
        seconds = 0.0
    else:
        try:
            seconds = float(raw)
        except ValueError:
            await update.message.reply_text("အသုံးပြုပုံ: /fade 0.6 သို့မဟုတ် /fade off")
            return
    if not 0 <= seconds <= 5:
        await update.message.reply_text("Fade သည် ၀ မှ ၅ စက္ကန့်အတွင်း ဖြစ်ရပါမယ်။")
        return
    defaults = context.user_data.setdefault("video_edit_defaults", {})
    defaults["fade_seconds"] = seconds
    session = context.user_data.get("video_render")
    if session is not None:
        session["fade_seconds"] = seconds
    await update.message.reply_text("Opening/Closing Fade ပိတ်ထားပါပြီ။" if seconds == 0 else f"Opening/Closing Fade ကို {seconds:.1f} စက္ကန့် သတ်မှတ်ပြီးပါပြီ။")


async def substyle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select a styled caption preset for optional hard-burn subtitles."""
    if not update.message:
        return
    from subtitle_styles import SUBTITLE_STYLES
    selected = context.args[0].strip().lower() if context.args else ""
    if not selected or selected == "list":
        await update.message.reply_text(
            "💬 NEXORA Subtitle Styles\nအသုံးပြုပုံ: /substyle <preset>\n"
            + "\n".join("• " + name for name in sorted(SUBTITLE_STYLES))
            + "\nDefault: classic"
        )
        return
    if selected not in SUBTITLE_STYLES:
        await update.message.reply_text("Subtitle style မသိပါ။ /substyle list ဖြင့် ကြည့်ပါ။")
        return
    defaults = context.user_data.setdefault("video_edit_defaults", {})
    defaults["subtitle_style"] = selected
    session = context.user_data.get("video_render")
    if session is not None:
        session["subtitle_style"] = selected
    await update.message.reply_text(f"Subtitle Style ရွေးပြီးပါပြီ: {selected}")


async def subburn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle permanently burned captions; soft selectable subtitles remain default."""
    if not update.message:
        return
    selected = context.args[0].strip().lower() if context.args else "on"
    if selected not in {"on", "off", "true", "false", "1", "0"}:
        await update.message.reply_text("အသုံးပြုပုံ: /subburn on သို့မဟုတ် /subburn off")
        return
    enabled = selected in {"on", "true", "1"}
    defaults = context.user_data.setdefault("video_edit_defaults", {})
    defaults["burn_subtitles"] = enabled
    session = context.user_data.get("video_render")
    if session is not None:
        session["burn_subtitles"] = enabled
    await update.message.reply_text(
        "Subtitle ကို Video ပေါ်တွင် တိုက်ရိုက် Burn လုပ်ပါမယ်။" if enabled
        else "Soft Subtitle Mode ပြန်ထားပါပြီ။ Player မှာ ဖွင့်/ပိတ်နိုင်ပါတယ်။"
    )


async def bgm_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request optional background music upload or clear the stored track."""
    if not update.message:
        return
    action = context.args[0].strip().lower() if context.args else "upload"
    if action in {"off", "clear", "remove"}:
        context.user_data.pop("background_music", None)
        context.user_data.pop("pending_bgm_upload", None)
        await update.message.reply_text("Background Music ဖယ်ရှားပြီးပါပြီ။")
        return
    if action not in {"upload", "on", "set"}:
        await update.message.reply_text("အသုံးပြုပုံ: /bgm (သီချင်းဖိုင်တင်ရန်) သို့မဟုတ် /bgm off (ဖယ်ရန်)")
        return
    context.user_data.pop("pending_logo_upload", None)
    context.user_data["pending_bgm_upload"] = True
    await update.message.reply_text(
        "🎵 Background Music ဖိုင် MP3/M4A/WAV/OGG တစ်ခု ပို့ပါ (၂၀ MB အောက်)။\n"
        "Narration ပြောနေချိန်တွင် Music ကို အလိုအလျောက်လျှော့ပေးပါမယ်။\n"
        "ဖယ်ရှားရန် /bgm off"
    )


async def bgmvolume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set background music loudness from muted (0) to full volume (1)."""
    if not update.message:
        return
    raw = context.args[0].strip() if context.args else "0.18"
    try:
        volume = float(raw)
    except ValueError:
        await update.message.reply_text("အသုံးပြုပုံ: /bgmvolume 0.18 (၀ မှ ၁ အတွင်း)")
        return
    if not 0.0 <= volume <= 1.0:
        await update.message.reply_text("Music Volume သည် ၀ မှ ၁ အတွင်း ဖြစ်ရပါမယ်။ ဥပမာ /bgmvolume 0.18")
        return
    defaults = context.user_data.setdefault("video_edit_defaults", {})
    defaults["music_volume"] = volume
    session = context.user_data.get("video_render")
    if session is not None:
        session["music_volume"] = volume
    await update.message.reply_text(f"Background Music Volume ကို {volume:.2f} သတ်မှတ်ပြီးပါပြီ။")


async def bgmduck_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle automatic background-music ducking while narration is speaking."""
    if not update.message:
        return
    selected = context.args[0].strip().lower() if context.args else "on"
    if selected not in {"on", "off", "true", "false", "1", "0"}:
        await update.message.reply_text("အသုံးပြုပုံ: /bgmduck on သို့မဟုတ် /bgmduck off")
        return
    enabled = selected in {"on", "true", "1"}
    defaults = context.user_data.setdefault("video_edit_defaults", {})
    defaults["music_ducking"] = enabled
    session = context.user_data.get("video_render")
    if session is not None:
        session["music_ducking"] = enabled
    await update.message.reply_text(
        "Narration ပြောနေချိန် Background Music ကို အလိုအလျောက်လျှော့ပါမယ်။"
        if enabled else
        "Background Music Ducking ပိတ်ထားပါပြီ။ Music အသံကို မလျှော့တော့ပါ။"
    )

async def logo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upload, position, or remove the creator's brand logo overlay."""
    if not update.message:
        return
    from logo_overlay import LOGO_POSITIONS
    action = context.args[0].strip().lower() if context.args else "upload"
    if action in {"off", "clear", "remove"}:
        context.user_data.pop("brand_logo", None)
        context.user_data.pop("pending_logo_upload", None)
        await update.message.reply_text("Brand Logo ဖယ်ရှားပြီးပါပြီ။")
        return
    if action == "position":
        position = context.args[1].strip().lower() if len(context.args) > 1 else ""
        if position not in LOGO_POSITIONS:
            await update.message.reply_text("အသုံးပြုပုံ: /logo position top-left|top-right|bottom-left|bottom-right")
            return
        context.user_data["logo_position"] = position
        await update.message.reply_text(f"Logo Position ပြောင်းပြီးပါပြီ: {position}")
        return
    context.user_data.pop("pending_bgm_upload", None)
    context.user_data["pending_logo_upload"] = True
    await update.message.reply_text(
        "🪪 Brand Logo PNG/JPG/WEBP ဖိုင် (၅ MB အောက်) ပို့ပါ။ MP4 ပေါ်တွင် အလိုအလျောက် Overlay လုပ်ပေးပါမယ်။\n"
        "နေရာပြောင်းရန် /logo position top-left စသဖြင့် သုံးပါ။ ဖယ်ရန် /logo off"
    )


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
        context.user_data.pop("pending_voice_profile_consent", None)
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
        await message.reply_text(f"{pending} အသံနမူနာကို သိမ်းပြီးပါပြီ။ /myvoice status ဖြင့် စစ်ပါ။ AI ကို ကိုယ့်အသံနဲ့ စာသားဖတ်ခိုင်းရန် /voiceclone ကိုသုံးပါ။ ဒီလုပ်ဆောင်မှုသည် GPU host လိုအပ်ပြီး Render Free တွင် မရနိုင်သေးပါ။")
        await send_voice_profile_backup(update, profiles, "Profile အသစ်သိမ်းပြီးနောက်")
        return
    if context.user_data.get("pending_logo_upload"):
        logo_media = message.photo[-1] if message.photo else None
        logo_filename = "brand_logo.jpg" if logo_media else ""
        if message.document:
            candidate = message.document.file_name or ""
            if Path(candidate).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                logo_media = message.document
                logo_filename = candidate
        if logo_media is None:
            await message.reply_text("PNG/JPG/WEBP Logo ဖိုင်ကို ပို့ပါ။")
            return
        media_file = await logo_media.get_file()
        if (getattr(media_file, "file_size", 0) or 0) <= 0 or (getattr(media_file, "file_size", 0) or 0) > 5 * 1024 * 1024:
            await message.reply_text("Brand Logo သည် ၅ MB အောက် ဖြစ်ရပါမယ်။")
            return
        buffer = BytesIO()
        await media_file.download_to_memory(out=buffer)
        context.user_data["brand_logo"] = (logo_filename, buffer.getvalue())
        context.user_data.pop("pending_logo_upload", None)
        await message.reply_text("🪪 Brand Logo လက်ခံပြီးပါပြီ။ နောက် MP4 Render မှာ အလိုအလျောက် Overlay လုပ်ပါမယ်။ /logo off ဖြင့် ဖယ်နိုင်ပါတယ်။")
        return
    if context.user_data.get("pending_bgm_upload"):
        music_media = message.audio or message.voice
        music_filename = getattr(music_media, "file_name", None) if music_media else None
        if message.document:
            candidate = message.document.file_name or ""
            if Path(candidate).suffix.lower() in {".mp3", ".m4a", ".wav", ".ogg"}:
                music_media = message.document
                music_filename = candidate
        if music_media is None:
            await message.reply_text("MP3/M4A/WAV/OGG Music ဖိုင်ကို ပို့ပါ။")
            return
        media_file = await music_media.get_file()
        if (getattr(media_file, "file_size", 0) or 0) <= 0 or (getattr(media_file, "file_size", 0) or 0) > 20 * 1024 * 1024:
            await message.reply_text("Background Music သည် ၂၀ MB အောက် ဖြစ်ရပါမယ်။")
            return
        buffer = BytesIO()
        await media_file.download_to_memory(out=buffer)
        filename = music_filename or ("background.ogg" if message.voice else "background.mp3")
        context.user_data["background_music"] = (filename, buffer.getvalue())
        context.user_data.pop("pending_bgm_upload", None)
        await message.reply_text("🎵 Background Music လက်ခံပြီးပါပြီ။ Narration အသံပြောချိန်တွင် Music ကို အလိုအလျောက်လျှော့ပြီး MP4 ထဲထည့်ပါမယ်။ /bgm off ဖြင့် ဖယ်နိုင်ပါတယ်။")
        return
    session = context.user_data.get("video_render")
    if session is None:
        return
    if session.get("mode") == "source_video":
        media = None
        filename = ""
        kind = ""
        if message.video:
            media, filename, kind = message.video, (message.video.file_name or "source.mp4"), "video"
        elif message.document:
            doc_name = message.document.file_name or ""
            suffix = os.path.splitext(doc_name)[1].lower()
            if suffix in {".mp4", ".mov", ".m4v", ".webm"}:
                media, filename, kind = message.document, doc_name, "video"
            elif suffix == ".srt":
                media, filename, kind = message.document, doc_name, "subtitle"
            elif suffix in {".mp3", ".m4a", ".wav", ".ogg"}:
                media, filename, kind = message.document, doc_name, "audio"
        elif message.audio or message.voice:
            media = message.audio or message.voice
            filename = getattr(media, "file_name", None) or ("narration.ogg" if message.voice else "narration.mp3")
            kind = "audio"
        if media is None:
            return
        media_file = await media.get_file()
        size = getattr(media_file, "file_size", 0) or 0
        limit = (19 * 1024 * 1024 if kind == "video" else 20 * 1024 * 1024) if kind in {"video", "audio"} else 1024 * 1024
        if size <= 0 or size > limit:
            await message.reply_text("Video Clip သည် ၁၉ MiB အောက်၊ အသံသည် ၂၀ MB အောက်၊ SRT သည် ၁ MB အောက် ဖြစ်ရပါမယ်။")
            return
        if kind == "video":
            clips = session.setdefault("source_videos", [])
            if len(clips) >= 30:
                await message.reply_text("Video Clip ၃၀ ခု ပြည့်ပါပြီ။ /sourcevideo finish ပို့ပါ။")
                return
            clip_dir = Path(session["source_video_clip_dir"])
            clip_dir.mkdir(parents=True, exist_ok=True)
            clip_path = clip_dir / f"clip_{len(clips) + 1:02d}{Path(filename).suffix.lower()}"
            total_bytes = sum(Path(item[1]).stat().st_size for item in clips) + size
            if total_bytes > 180 * 1024 * 1024:
                await message.reply_text("Video Clip စုစုပေါင်း ၁၈၀ MiB ကျော်နေပါတယ်။ ပိုသေးသော Clip များသုံးပါ။")
                return
            await media_file.download_to_drive(custom_path=str(clip_path))
            clips.append((filename, str(clip_path)))
            session["source_video"] = None
            old_download = session.get("source_video_path")
            if old_download:
                Path(old_download).unlink(missing_ok=True)
                session["source_video_path"] = None
            received = f"Video Clip {len(clips)}/30 လက်ခံပြီးပါပြီ။"
        else:
            buffer = BytesIO()
            await media_file.download_to_memory(out=buffer)
            payload = (filename, buffer.getvalue())
            key = {"audio": "narration_audio", "subtitle": "subtitles"}[kind]
            session[key] = payload
            received = {
                "audio": "မြန်မာ Narration အသံ လက်ခံပြီးပါပြီ။",
                "subtitle": "SRT စာတန်းထိုး လက်ခံပြီးပါပြီ။",
            }[kind]
        await message.reply_text(received + " လိုအပ်သည့်ဖိုင်အားလုံးပြီးလျှင် /sourcevideo finish ပို့ပါ။")
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
    if media_file is None and message.document:
        document_name = message.document.file_name or ""
        document_kind = classify_render_document(document_name)
        if document_kind:
            media_file = await message.document.get_file()
            filename = document_name or ("captions.srt" if document_kind == "subtitle" else "narration.mp3")
            kind = document_kind
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
    elif kind == "audio" and message.document:
        if session.get("mode") == "timeline":
            active = session.get("active_scene")
            if active is None:
                await message.reply_text("အရင်ဆုံး /render scene <အမည်> ဖြင့် Scene ဖွင့်ပါ။")
                return
            if session["scenes"][active].get("audio"):
                await message.reply_text("ဒီ Scene မှာ အသံရှိပြီးပါပြီ။ နောက် Scene အတွက် /render scene <အမည်> ပို့ပါ။")
                return
            session["scenes"][active]["audio"] = (filename, data)
            await message.reply_text(f"Scene {active + 1} အသံဖိုင် လက်ခံပြီးပါပြီ။")
            return
        if session.get("mode") != "timeline":
            session["audio"] = (filename, data)
            await message.reply_text("Narration အသံဖိုင် လက်ခံပြီးပါပြီ။ /render finish ပို့နိုင်ပါပြီ။")
            return
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



async def voiceclone_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clone the current Telegram user's own saved reference voice."""
    if not update.message or not update.message.text:
        return
    first_line, separator, script = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    profile_name = parts[1].strip() if len(parts) > 1 else ""
    if not separator or not script.strip() or not profile_name:
        await update.message.reply_text(
            "အသုံးပြုပုံ: /voiceclone <voice_profile_name> ပြီးနောက် မြန်မာစာသားကို စာကြောင်းအသစ်မှ ထည့်ပါ။\n"
            "အရင်ဆုံး /voiceprofile <name> ဖြင့် ကိုယ့်အသံဖိုင်ကို သိမ်းထားပါ။"
        )
        return
    try:
        profiles = load_voice_profiles(update.effective_user.id)
        profile = profiles.get(normalize_profile_name(profile_name))
    except (OSError, ValueError) as exc:
        await update.message.reply_text(f"Voice Profile ကို ဖတ်မရပါ: {exc}")
        return
    if not profile:
        await update.message.reply_text("ဒီအမည်နဲ့ သိမ်းထားသောအသံ မတွေ့ပါ။ /voiceprofile list ဖြင့် စစ်ပါ။")
        return
    await update.message.reply_text(
        "သိမ်းထားသော ကိုယ်ပိုင် Reference အသံဖြင့် မြန်မာစာကို ဖန်တီးနေပါတယ်။ "
        "ဒီလုပ်ဆောင်မှုမှာ compatible GPU host လိုအပ်ပြီး Render Free မှာ မရနိုင်ပါ..."
    )
    try:
        audio = await synthesize_cloned_burmese_voice(
            script.strip(), profile["filename"], profile["audio"]
        )
    except (ValueError, RuntimeError) as exc:
        await update.message.reply_text(str(exc))
        return
    file_obj = BytesIO(audio)
    file_obj.name = "nexora_creator_voice_clone.wav"
    await update.message.reply_document(
        document=InputFile(file_obj, filename=file_obj.name),
        caption="ကိုယ်ပိုင် Reference အသံကို အသုံးပြုထားသော AI Voice Clone ဖြစ်သည်။ ထုတ်ဝေမီ အသံထွက်နှင့် အမည်များကို ပြန်စစ်ပါ။",
        read_timeout=120,
        write_timeout=120,
    )


async def recapvoiceclone_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate creator-owned VoxCPM narration and attach it to an active source-video render."""
    if not update.message or not update.message.text:
        return
    first_line, separator, script = update.message.text.partition("\n")
    parts = first_line.split(maxsplit=1)
    profile_name = parts[1].strip() if len(parts) > 1 else "ကိုယ်ပိုင်အသံ"
    if not separator or not script.strip():
        await update.message.reply_text(
            "အသုံးပြုပုံ: /recapvoiceclone [profile_name] ပြီးနောက် မြန်မာ narration ကို စာကြောင်းအသစ်မှ ထည့်ပါ။\n"
            "အရင် /sourcevideo start ဖြင့် Video Render Session ဖွင့်ပြီး /myvoice setup ဖြင့် အသံသိမ်းထားပါ။"
        )
        return
    session = context.user_data.get("video_render")
    if not session or session.get("mode") != "source_video":
        await update.message.reply_text(
            "အရင် /sourcevideo start ပို့ပြီး Render Session ဖွင့်ပါ။ ထို့နောက် /recapvoiceclone ဖြင့် narration ဖန်တီးနိုင်ပါတယ်။"
        )
        return
    try:
        profiles = load_voice_profiles(update.effective_user.id)
        profile = profiles.get(normalize_profile_name(profile_name))
        if not profile:
            await update.message.reply_text("သိမ်းထားသော Voice Profile မတွေ့ပါ။ /myvoice status သို့ /voiceprofile list ဖြင့် စစ်ပါ။")
            return
        await update.message.reply_text("ကိုယ်ပိုင် Reference အသံဖြင့် narration WAV ဖန်တီးနေပါတယ်။ Compatible GPU host လိုအပ်ပါတယ်...")
        audio = await synthesize_cloned_burmese_voice(script.strip(), profile["filename"], profile["audio"])
        from recap_voice_clone_pipeline import build_estimated_srt_for_audio
        srt_text = build_estimated_srt_for_audio(script.strip(), audio)
    except (OSError, ValueError, RuntimeError) as exc:
        await update.message.reply_text(f"ကိုယ်ပိုင်အသံ Recap narration မဖန်တီးနိုင်ပါ: {exc}")
        return
    except Exception:
        log.exception("/recapvoiceclone failed")
        await update.message.reply_text("ကိုယ်ပိုင်အသံ Recap ဖန်တီးရာတွင် အမှားရှိပါတယ်။")
        return

    session["narration_audio"] = ("nexora_myvoice_narration.wav", audio)
    session["subtitles"] = ("nexora_myvoice_estimated.srt", srt_text.encode("utf-8-sig"))
    session["narration_voice"] = "ကိုယ်ပိုင်အသံ"
    audio_file = BytesIO(audio)
    audio_file.name = "nexora_myvoice_narration.wav"
    await update.message.reply_document(
        document=InputFile(audio_file, filename=audio_file.name),
        caption="ကိုယ်ပိုင်အသံ Recap narration WAV။ ဒီဖိုင်ကို လက်ရှိ /sourcevideo Session ထဲသို့လည်း ချိတ်ထားပါပြီ။"
    )
    subtitle_file = BytesIO(srt_text.encode("utf-8-sig"))
    subtitle_file.name = "nexora_myvoice_estimated.srt"
    await update.message.reply_document(
        document=InputFile(subtitle_file, filename=subtitle_file.name),
        caption="အသံကြာချိန်နှင့် အဆုံးချိန်ညှိထားသော ခန့်မှန်း SRT ဖြစ်သည်။ Word-level alignment မဟုတ်ပါ။ ထုတ်ဝေမီ အသံနှင့်တိုက်စစ်ပြီး လိုအပ်လျှင် ပြင်ထားသော SRT ကို Upload လုပ်ပါ။"
    )
    await update.message.reply_text(
        "ကိုယ်ပိုင်အသံ Narration + SRT ကို Render Session ထဲ ထည့်ပြီးပါပြီ။ မူရင်း Video/ခွင့်ပြုထားသော Footage ကို ပို့ပြီး /sourcevideo finish လုပ်ပါ။"
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
    if duration_report:
        await update.message.reply_text(duration_report, disable_web_page_preview=True)

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
        if preset != "myvoice":
            validate_tts_request(script, preset)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    voice_label = "ကိုယ်ပိုင်အသံ" if preset == "myvoice" else VOICE_PRESETS[preset]["label"]
    await update.message.reply_text(
        f"မြန်မာ narration ကို {voice_label} ဖြင့် ဖန်တီးပြီး SRT ပြင်ဆင်နေပါတယ်..."
    )
    clone_duration = None
    try:
        if preset == "myvoice":
            profiles = load_voice_profiles(update.effective_user.id)
            profile = profiles.get("ကိုယ်ပိုင်အသံ")
            if not profile:
                raise ValueError("ကိုယ်ပိုင်အသံ Profile မရှိသေးပါ။ /myvoice start → /myvoice confirm → အသံဖိုင်ပို့ပါ။")
            audio, srt_text, clone_duration = await synthesize_recap_in_creator_voice(
                script, profile["filename"], profile["audio"]
            )
        else:
            audio, srt_text = await synthesize_burmese_speech_with_srt(script, preset)
    except (ValueError, RuntimeError) as exc:
        await update.message.reply_text(f"Recap အသံ/စာတန်း ဖန်တီးမရပါ: {exc}")
        return
    except Exception:
        log.exception("/recapvoice synthesis failed")
        await update.message.reply_text("Recap အသံ/စာတန်း ဖန်တီးရာတွင် မမျှော်လင့်ထားသော အမှားရှိပါတယ်။")
        return

    platform = context.user_data.get("platform", "youtube")
    duration_report = ""
    duration_caption = ""
    if platform == "tiktok":
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="nexora-tiktok-recap-", suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(audio)
            metadata = (
                {"duration_seconds": clone_duration, "audio_stream": "MP3", "decode_ok": True, "file_size_bytes": len(audio)}
                if clone_duration is not None
                else await asyncio.to_thread(inspect_audio_file, temp_path)
            )
            evaluation = evaluate_audio_duration("tiktok", metadata["duration_seconds"])
            duration_report = format_audio_qa_report("tiktok", metadata, evaluation)
            duration_caption = (
                " | DURATION PASS — လူကိုယ်တိုင်စစ်ရန်"
                if evaluation["status"] == "DURATION PASS"
                else " | DURATION FAIL — မထုတ်ဝေရသေး"
            )
        except Exception as exc:
            log.warning("TikTok recap audio QA failed (%s)", type(exc).__name__)
            await update.message.reply_text(
                "TikTok Audio ကို FFmpeg ဖြင့် တိုင်းတာမရပါ။ QA မပြည့်စုံသဖြင့် MP3 ကို မထုတ်ပေးထားပါ။"
            )
            return
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    audio_file = BytesIO(audio)
    audio_file.name = "nexora_recap_voiceover.mp3"
    await update.message.reply_document(
        document=InputFile(audio_file, filename=audio_file.name),
        caption=(
            f"🎙️ Burmese Recap Voice-over — {voice_label}\n"
            "ကိုယ်တိုင်ရေးထားသော Script မှ ဖန်တီးထားသည်။ အသံထွက်နှင့် အမည်များကို ပြန်စစ်ပါ။" + duration_caption
        ),
        read_timeout=120,
        write_timeout=120,
    )
    subtitle_file = BytesIO(srt_text.encode("utf-8-sig"))
    subtitle_file.name = (
        "nexora_recap_subtitles_estimated.srt"
        if preset == "myvoice"
        else "nexora_recap_subtitles_aligned.srt"
    )
    if preset == "myvoice":
        voice_assets = {
            "narration_audio": ("nexora_recap_voiceover.mp3", audio),
            "subtitles": (subtitle_file.name, srt_text.encode("utf-8-sig")),
            "narration_voice": "ကိုယ်ပိုင်အသံ",
            "platform": context.user_data.get("platform", "youtube"),
        }
        context.user_data["creator_voice_assets"] = voice_assets
        render_session = context.user_data.get("video_render")
        if render_session and render_session.get("mode") == "source_video":
            render_session.update(voice_assets)
    await update.message.reply_document(
        document=InputFile(subtitle_file, filename=subtitle_file.name),
        caption=(
            "ကိုယ်ပိုင်အသံ Clone ၏ တကယ့် MP3 ကြာချိန်အပေါ် စာသားအရှည်အလိုက် ခန့်မှန်းထားသော SRT ဖြစ်သည်။ Word-level sync မဟုတ်ပါ။ ထုတ်ဝေမီ ပြန်ညှိပါ။"
            if preset == "myvoice"
            else "အသံထုတ်လုပ်စဉ် WordBoundary အချိန်မှတ်တမ်းဖြင့် ချိန်ညှိထားသော မြန်မာ SRT ဖြစ်သည်။ ထုတ်ဝေမီ ပြန်စစ်ပါ။"
        ),
    )


async def recapvoice3_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate three separate narration MP3/SRT pairs and gate them by measured duration."""
    if not update.message or not update.message.text:
        return
    platform = context.user_data.get("platform", "youtube")
    if platform not in {"youtube", "facebook"}:
        await update.message.reply_text(
            "/recapvoice3 သည် YouTube/Facebook အတွက်သာ ဖြစ်သည်။ "
            "TikTok အတွက် /recapvoice ကိုသုံးပြီး တစ်ဖိုင်တည်း ၄–၇ မိနစ် ထုတ်ပါ။"
        )
        return
    try:
        preset, parts = parse_recap_voice_parts_request(update.message.text, VOICE_PRESETS)
        if preset != "myvoice":
            for script in parts.values():
                validate_tts_request(script, preset)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    voice_label = "ကိုယ်ပိုင်အသံ" if preset == "myvoice" else VOICE_PRESETS[preset]["label"]
    await update.message.reply_text(
        f"{platform.upper()} အတွက် narration ၃ ပိုင်းကို {voice_label} ဖြင့် MP3/SRT သီးခြားဖန်တီးပြီး "
        "FFmpeg ဖြင့် တကယ့်ကြာချိန်ကို စစ်ဆေးနေပါတယ်..."
    )
    generated = []
    durations = []
    try:
        if preset == "myvoice":
            profiles = load_voice_profiles(update.effective_user.id)
            profile = profiles.get("ကိုယ်ပိုင်အသံ")
            if not profile:
                raise ValueError("ကိုယ်ပိုင်အသံ Profile မရှိသေးပါ။ /myvoice start → /myvoice confirm → အသံဖိုင်ပို့ပါ။")
            for index in (1, 2, 3):
                audio, srt_text, duration = await synthesize_recap_in_creator_voice(
                    parts[index], profile["filename"], profile["audio"]
                )
                durations.append(duration)
                generated.append((index, audio, srt_text))
            combined_audio, combined_srt, _ = await combine_creator_voice_parts([
                (audio, srt_text, duration)
                for (_, audio, srt_text), duration in zip(generated, durations)
            ])
            voice_assets = {
                "narration_audio": ("nexora_recap_voiceover.mp3", combined_audio),
                "subtitles": ("nexora_recap_subtitles_estimated.srt", combined_srt.encode("utf-8-sig")),
                "narration_voice": "ကိုယ်ပိုင်အသံ",
                "platform": platform,
            }
            context.user_data["creator_voice_assets"] = voice_assets
            render_session = context.user_data.get("video_render")
            if render_session and render_session.get("mode") == "source_video":
                render_session.update(voice_assets)
        else:
            for index in (1, 2, 3):
                audio, srt_text = await synthesize_burmese_speech_with_srt(parts[index], preset)
                with tempfile.NamedTemporaryFile(prefix="nexora-recap-part-", suffix=".mp3", delete=False) as temp_file:
                    temp_path = temp_file.name
                    temp_file.write(audio)
                try:
                    metadata = await asyncio.to_thread(inspect_audio_file, temp_path)
                finally:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
                durations.append(metadata["duration_seconds"])
                generated.append((index, audio, srt_text))
    except (ValueError, RuntimeError) as exc:
        await update.message.reply_text(
            "Part MP3 ထုတ်လုပ်ခြင်း သို့မဟုတ် FFmpeg တိုင်းတာခြင်း မအောင်မြင်ပါ။ "
            "QA မပြည့်စုံသဖြင့် ဖိုင်များကို အပြီးသတ်အဖြစ် မထုတ်ပေးထားပါ။\n" + str(exc)
        )
        return
    except Exception as exc:
        log.warning("Three-part recap voice generation failed (%s)", type(exc).__name__)
        await update.message.reply_text(
            "သုံးပိုင်း MP3 ဖန်တီးမှု မအောင်မြင်ပါ။ အပိုင်းအားလုံးကို ပြန်စစ်ပြီးမှ ထပ်လုပ်ပါ။"
        )
        return

    evaluation = evaluate_audio_parts(platform, durations)
    await update.message.reply_text(format_audio_parts_qa_report(platform, evaluation))
    ready_label = (
        "DURATION PASS — လူကိုယ်တိုင် နောက်ဆုံးစစ်ဆေးရန်"
        if evaluation["status"] == "DURATION PASS"
        else "DURATION FAIL — မထုတ်ဝေရသေး၊ Script ကို ပြင်ဆင်ရန်"
    )
    for index, audio, srt_text in generated:
        audio_name = f"nexora_recap_{platform}_part_{index}.mp3"
        audio_file = BytesIO(audio)
        audio_file.name = audio_name
        await update.message.reply_document(
            document=InputFile(audio_file, filename=audio_name),
            caption=f"🎙️ {platform.upper()} Part {index}/3 — {ready_label}",
            read_timeout=120,
            write_timeout=120,
        )
        subtitle_name = f"nexora_recap_{platform}_part_{index}.srt"
        subtitle_file = BytesIO(srt_text.encode("utf-8-sig"))
        subtitle_file.name = subtitle_name
        await update.message.reply_document(
            document=InputFile(subtitle_file, filename=subtitle_name),
            caption=(
                f"Part {index} အတွက် Clone MP3 ကြာချိန်အပေါ် စာသားအရှည်အလိုက် ခန့်မှန်းထားသော SRT ဖြစ်သည်။ Word-level sync မဟုတ်ပါ။ လူကိုယ်တိုင် ပြန်ညှိပါ။"
                if preset == "myvoice"
                else f"Part {index} အတွက် WordBoundary အချိန်မှတ်တမ်းဖြင့် ချိန်ညှိထားသော SRT။ လူကိုယ်တိုင် ပြန်စစ်ပါ။"
            ),
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

async def productionqa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check platform script parts, estimated duration, and supplied SRT structure."""
    if not update.message or not update.message.text:
        return
    message_parts = update.message.text.split("\n", 1)
    header = message_parts[0].split(maxsplit=1)
    if len(header) < 2 or len(message_parts) < 2:
        await update.message.reply_text(
            "အသုံးပြုပုံ:\n/productionqa Anime|Demon Slayer|youtube\n"
            "[PART 1]\nScript အပိုင်း ၁\n[PART 2]\nScript အပိုင်း ၂\n[PART 3]\nScript အပိုင်း ၃\n[SRT]\nSRT စာသား\n"
            "TikTok အတွက် [PART 1] တစ်ခုတည်း ထည့်ပါ။"
        )
        return
    fields = [item.strip() for item in header[1].split("|")]
    if len(fields) != 3:
        await update.message.reply_text("Category|Title|Platform ပုံစံသုံးပါ။ ဥပမာ: Anime|Demon Slayer|youtube")
        return
    category, title, platform = fields
    package_text = message_parts[1]
    parsed_parts, _ = parse_production_package(package_text)
    combined_script = "\n\n".join(parsed_parts.get(number, "") for number in sorted(parsed_parts))
    editorial = analyze_recap_script(category, title, combined_script)
    production = analyze_production_package(platform, package_text)
    output = format_recap_qa_report(editorial) + "\n\n" + format_production_qa_report(production)
    if len(output) <= 3900:
        await update.message.reply_text(output, disable_web_page_preview=True)
    else:
        file_obj = BytesIO(output.encode("utf-8-sig"))
        file_obj.name = "nexora_production_qa.txt"
        await update.message.reply_document(
            document=InputFile(file_obj, filename=file_obj.name),
            caption="NEXORA Script / Duration / Subtitle QA — Human review မဖြစ်မနေ လုပ်ပါ။",
        )


async def audioqa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Measure the actual duration of an audio file replied to by the user."""
    if not update.message:
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "အသုံးပြုပုံ: Audio ဖိုင်ကို reply လုပ်ပြီး /audioqa youtube သို့မဟုတ် /audioqa facebook သို့မဟုတ် /audioqa tiktok ဟု ပို့ပါ။"
        )
        return
    platform = context.args[0].strip().casefold()
    if platform not in {"youtube", "facebook", "tiktok", "yt", "fb", "tt"}:
        await update.message.reply_text("Platform သည် youtube၊ facebook သို့မဟုတ် tiktok ဖြစ်ရပါမည်။")
        return
    replied = update.message.reply_to_message
    if not replied:
        await update.message.reply_text("စစ်ဆေးလိုသော MP3/WAV/M4A/OGG Audio ဖိုင်ကို အရင်ပို့ပြီး ထိုဖိုင်ကို reply လုပ်ကာ /audioqa <platform> ဟု ပို့ပါ။")
        return
    media_file = replied.audio or replied.voice or replied.video or replied.document
    if not media_file:
        await update.message.reply_text("Reply လုပ်ထားသော message တွင် Audio ပါဝင်သည့် ဖိုင် မတွေ့ပါ။")
        return
    file_size = getattr(media_file, "file_size", None)
    if file_size and file_size > MAX_AUDIO_BYTES:
        await update.message.reply_text("Audio ဖိုင်သည် 20 MB ထက် ကျော်နေသည်။")
        return
    await update.message.reply_text("Audio ကို download လုပ်ပြီး FFmpeg ဖြင့် အမှန်တကယ်ကြာချိန်နှင့် decode ကို စစ်ဆေးနေပါတယ်...")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="nexora-audioqa-", suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name
        telegram_file = await context.bot.get_file(media_file.file_id)
        await telegram_file.download_to_drive(custom_path=temp_path)
        metadata = await asyncio.to_thread(inspect_audio_file, temp_path)
        evaluation = evaluate_audio_duration(platform, metadata["duration_seconds"])
        report = format_audio_qa_report(platform, metadata, evaluation)
        await update.message.reply_text(report, disable_web_page_preview=True)
    except Exception as exc:
        log.warning("Audio QA failed (%s)", type(exc).__name__)
        await update.message.reply_text("Audio QA မအောင်မြင်ပါ။ ဖိုင် format၊ ဖိုင်အခြေအနေနှင့် 20 MB ကန့်သတ်ချက်ကို စစ်ပါ။")
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current commands, especially the measured recap voice workflows."""
    if not update.message:
        return
    await update.message.reply_text(
        "NEXORA — အသုံးပြုနည်း\n\n"
        "【အခြေခံ】\n"
        "/start — စတင်ရန်\n"
        "/status — Bot/API အခြေအနေ\n"
        "/voices — Voice preset များ\n"
        "/platform youtube|facebook|tiktok — Platform ရွေးရန်\n"
        "/duration <ကြာချိန်> — အထွေထွေ Script planning ကြာချိန်ရွေးရန်\n"
        "/settings — လက်ရှိရွေးချယ်မှု\n"
        "/mode free|ai — Mode ရွေးရန် (Paid API ကို အလိုအလျောက် မခေါ်ပါ)\n\n"
        "【Recap အသံထုတ်လုပ်မှု】\n"
        "/recapvoice [preset|myvoice] — MP3 တစ်ဖိုင် + SRT တစ်ဖိုင်\n"
        "/recapvoice myvoice — TikTok/တစ်ဖိုင် Recap အတွက် ကိုယ်ပိုင်အသံ MP3/SRT ထုတ်ရန် (GPU host လိုအပ်)\n"\n        "/recapvoice3 myvoice — YouTube/Facebook အတွက် ၁၅–၂၀ မိနစ်စီ ၃ ပိုင်းထုတ်ပြီး MP4 ပေါင်းစပ်ဖိုင် auto-attach လုပ်ရန်\n"\n        "ကိုယ်ပိုင်အသံ SRT သည် ကြာချိန်အပေါ် ခန့်မှန်းထားခြင်းဖြစ်၍ ထုတ်ဝေမီ ပြန်ညှိပါ။\n"
        "TikTok အတွက် /platform tiktok ကို အရင်ရွေးပါ။ တစ်ဖိုင်တည်း ၄–၇ မိနစ် ဖြစ်ရမည်။ FFmpeg ဖြင့် တကယ့်အသံကြာချိန်ကို စစ်ပြီး QA မအောင်မြင်လျှင် MP3 မထုတ်ပေးပါ။\n"
        "/recapvoice3 [preset|myvoice] — YouTube/Facebook အတွက် MP3 သုံးဖိုင် + SRT သုံးဖိုင်\n"
        "Script ကို Command နဲ့ message တစ်စောင်တည်းတွင် အောက်ပါပုံစံအတိုင်း ထည့်ပါ။\n"
        "/recapvoice3 narrator\n"
        "[PART 1]\nအပိုင်း ၁ Script စာသား...\n"
        "[PART 2]\nအပိုင်း ၂ Script စာသား...\n"
        "[PART 3]\nအပိုင်း ၃ Script စာသား...\n"
        "YouTube/Facebook စည်းမျဉ်း: အပိုင်း ၃ ပိုင်းတိတိ၊ တစ်ပိုင်းလျှင် ၁၅–၂၀ မိနစ်၊ စုစုပေါင်း ၄၆–၆၀ မိနစ်။ FFmpeg တိုင်းတာချက်ဖြင့် QA ပြုလုပ်သည်။\n"
        "/audioqa youtube|facebook|tiktok — Audio ဖိုင်ကို reply လုပ်ပြီး တကယ့်ကြာချိန် စစ်ရန်\n"
        "/productionqa <Category>|<Title>|<Platform> — Script/ခန့်မှန်းကြာချိန်/SRT စစ်ရန်\n"
        "/recapvideo <title> — Recap Video Preview ထုတ်ရန်\n"
        "သတိ: /duration ၏ အထွေထွေ planning preset များသည် /recapvoice နှင့် /recapvoice3 ၏ အထက်ပါ တကယ့်အသံကြာချိန် QA စည်းမျဉ်းများကို အစားမထိုးပါ။ DURATION PASS သည် ကြာချိန်စစ်ဆေးမှုသာဖြစ်ပြီး လူကိုယ်တိုင် နားထောင်/စစ်ဆေးပြီးမှ ထုတ်ဝေပါ။\n\n"
        "【Research / Draft】\n"
        "/auto <အမည်> — Wikipedia source lead ရှာရန်\n"
        "/research <အမည်> — Research worksheet\n"
        "/multisourceresearch <အမည်> — Anime/Animation/Movie/TV အမျိုးအစားစုံ ရင်းမြစ်စစ်ရန်\n"
        "/moviemultisourceresearch <အမည်> — Movie metadata စစ်ရန်\n"
        "/seriesguide <အမည်> — Series လမ်းညွှန်\n"
        "/draft <အမည်> — Research Notes မှ Draft worksheet\n"
        "/draft3 <အမည်> — YouTube သုံးပိုင်း Draft worksheet\n"
        "/allplatforms <အမည်> — Platform သုံးခုအတွက် Plan\n"
        "/episodeplots <အမည်> — Episode ဇာတ်ကွက်များစုရန်\n"
        "/episodeverify <အမည်> — Episode အချက်အလက်နှိုင်းယှဉ်ရန်\n"
        "/episodepack <အမည်> — Episode production pack\n"
        "/episodeoutline <အမည်> — Episode recap outline\n"
        "/topratedepisodes <အမည်> — Rating မြင့် Episode များ\n\n"
        "【Video / Subtitle / အခြား】\n"
        "/clipsource <အမည်> — လိုင်စင်ရှိ Video ရင်းမြစ်ရှာရန်\n"
        "/autoclip <အမည်> — Licensed footage Preview\n"
        "/autonarrateclip — Licensed footage + narration Preview\n"
        "/growthpack <category>|<title>|<summary> — Channel ထုတ်ဝေမှု Pack\n"
        "/voiceover <အမည်> / /voiceover3 <အမည်> — Voice-over မူကြမ်းဖိုင်များ\n"
        "/srt — Timestamp ပါစာသားမှ SRT\n"
        "/srtmy — မြန်မာစာသားမှ SRT\n"
        "/tts <preset> — MP3 အသံထုတ်ရန်\n"
        "/voicedemo <preset> — အသံနမူနာ\n"
        "/voiceprofile <name> — ကိုယ်ပိုင် Reference အသံဖိုင် သိမ်းရန်\n"
        "/voiceclone <name> — ကိုယ်ပိုင်အသံဖြင့် မြန်မာစာ TTS WAV ထုတ်ရန် (GPU host လိုအပ်)\n"
        "/commentstatus — Comment Auto-Reply အခြေအနေ\n"
        "/commentdraft <platform> <comment> — Reply Draft\n"
        "/help — ဒီအကူအညီစာမျက်နှာ"
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
    global telegram_app, comment_autoreply_task, daily_recap_task
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
    telegram_app.add_handler(CommandHandler("licensedownload", licensedownload_cmd))
    telegram_app.add_handler(CommandHandler("autoclip", autoclip_cmd))
    telegram_app.add_handler(CommandHandler("autonarrateclip", autonarrateclip_cmd))
    telegram_app.add_handler(CommandHandler("autofactsclip", autofactsclip_cmd))
    telegram_app.add_handler(CommandHandler("autoplotclip", autoplotclip_cmd))
    telegram_app.add_handler(CommandHandler("animesynopsis", animesynopsis_cmd))
    telegram_app.add_handler(CommandHandler("multisourceresearch", multisourceresearch_cmd))
    telegram_app.add_handler(CommandHandler("seriesresearch", seriesresearch_cmd))
    telegram_app.add_handler(CommandHandler("animationepisodes", animationepisodes_cmd))
    telegram_app.add_handler(CommandHandler("episodeplots", episodeplots_cmd))
    telegram_app.add_handler(CommandHandler("episodeverify", episodeverify_cmd))
    telegram_app.add_handler(CommandHandler("topratedepisodes", topratedepisodes_cmd))
    telegram_app.add_handler(CommandHandler("episodepack", episodepack_cmd))
    telegram_app.add_handler(CommandHandler("episodeoutline", episodeoutline_cmd))
    telegram_app.add_handler(CommandHandler("recapvoice", recapvoice_cmd))
    telegram_app.add_handler(CommandHandler("recapvoice3", recapvoice3_cmd))
    telegram_app.add_handler(CommandHandler("dailyrecap", dailyrecap_cmd))
    telegram_app.add_handler(CommandHandler("recapvideo", recapvideo_cmd))
    telegram_app.add_handler(CommandHandler("sourcevideo", sourcevideo_cmd))
    telegram_app.add_handler(CommandHandler("autoedit", autoedit_cmd))
    telegram_app.add_handler(CommandHandler("effect", effect_cmd))
    telegram_app.add_handler(CommandHandler("audiofx", audiofx_cmd))
    telegram_app.add_handler(CommandHandler("transition", transition_cmd))
    telegram_app.add_handler(CommandHandler("motion", motion_cmd))
    telegram_app.add_handler(CommandHandler("bgm", bgm_cmd))
    telegram_app.add_handler(CommandHandler("bgmvolume", bgmvolume_cmd))
    telegram_app.add_handler(CommandHandler("bgmduck", bgmduck_cmd))
    telegram_app.add_handler(CommandHandler("logo", logo_cmd))
    telegram_app.add_handler(CommandHandler("substyle", substyle_cmd))
    telegram_app.add_handler(CommandHandler("subburn", subburn_cmd))
    telegram_app.add_handler(CommandHandler("fade", fade_cmd))
    telegram_app.add_handler(CommandHandler("editstatus", editstatus_cmd))
    telegram_app.add_handler(CommandHandler("quality", quality_cmd))
    telegram_app.add_handler(CommandHandler("moviemultisourceresearch", moviemultisourceresearch_cmd))
    telegram_app.add_handler(CommandHandler("movieplotresearch", movieplotresearch_cmd))
    telegram_app.add_handler(CommandHandler("growthpack", growthpack_cmd))
    telegram_app.add_handler(CommandHandler("recapqa", recapqa_cmd))
    telegram_app.add_handler(CommandHandler("productionqa", productionqa_cmd))
    telegram_app.add_handler(CommandHandler("audioqa", audioqa_cmd))
    telegram_app.add_handler(CommandHandler("render", render_cmd))
    telegram_app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.Document.ALL, video_media_message))
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
    telegram_app.add_handler(CommandHandler("myvoice", myvoice_cmd))
    telegram_app.add_handler(CommandHandler("voiceclone", voiceclone_cmd))
    telegram_app.add_handler(CommandHandler("recapvoiceclone", recapvoiceclone_cmd))
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
        if daily_recap_task is not None:
            daily_recap_task.cancel()
            try:
                await daily_recap_task
            except asyncio.CancelledError:
                pass
            daily_recap_task = None
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

class _DailyRecapTelegramProxy:
    """Minimal message facade used by the internal scheduled-runner."""
    def __init__(self, bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self.text = "/dailyrecap all"

    async def reply_text(self, text: str, **kwargs):
        return await self.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

    async def reply_document(self, document, **kwargs):
        return await self.bot.send_document(chat_id=self.chat_id, document=document, **kwargs)

    async def reply_video(self, video, **kwargs):
        return await self.bot.send_video(chat_id=self.chat_id, video=video, **kwargs)


async def _run_scheduled_daily_recap(chat_id: int):
    global daily_recap_task
    daily_recap_state.update(status="running", chat_id=chat_id, started_at=time.time(), completed_at=None)
    try:
        if telegram_app is None:
            raise RuntimeError("Telegram bot is not ready")
        from types import SimpleNamespace
        proxy = _DailyRecapTelegramProxy(telegram_app.bot, chat_id)
        update = SimpleNamespace(
            message=proxy,
            effective_chat=SimpleNamespace(id=chat_id),
        )
        context = SimpleNamespace(args=["all"], user_data={})
        await dailyrecap_cmd(update, context)
        daily_recap_state.update(status="completed", completed_at=time.time())
    except asyncio.CancelledError:
        daily_recap_state.update(status="failed", completed_at=time.time(), error="service_shutdown")
        raise
    except Exception as exc:
        daily_recap_state.update(status="failed", completed_at=time.time(), error=type(exc).__name__)
        log.exception("Scheduled daily recap execution failed")
        if telegram_app is not None:
            try:
                await telegram_app.bot.send_message(
                    chat_id=chat_id,
                    text="NEXORA Daily Recap အလိုအလျောက်စတင်မှု မအောင်မြင်ပါ။ Render log နှင့် /status ကို စစ်ဆေးပါ။",
                )
            except Exception:
                log.exception("Could not notify scheduled recap failure")
    finally:
        daily_recap_task = None


def _daily_trigger_authorized(token: str) -> bool:
    expected = os.getenv("NEXORA_DAILY_RECAP_TOKEN", "").strip()
    return len(expected) >= 32 and bool(token) and hmac.compare_digest(token, expected)


@web_app.post("/internal/daily-recap", status_code=202)
async def trigger_internal_daily_recap(
    request: Request,
    x_nexora_daily_token: str = Header(default=""),
):
    """Queue the three-platform daily recap after a constant-time secret check."""
    global daily_recap_task
    expected = os.getenv("NEXORA_DAILY_RECAP_TOKEN", "").strip()
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="Daily recap trigger token is not configured")
    if not _daily_trigger_authorized(x_nexora_daily_token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if telegram_app is None:
        raise HTTPException(status_code=503, detail="Telegram bot is not ready")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    chat_id_value = payload.get("chat_id") if isinstance(payload, dict) else None
    chat_id_text = str(chat_id_value or "").strip()
    if not re.fullmatch(r"-?\d{5,20}", chat_id_text):
        raise HTTPException(status_code=400, detail="A valid Telegram chat_id is required")
    if daily_recap_task is not None and not daily_recap_task.done():
        raise HTTPException(status_code=409, detail="A daily recap run is already active")
    daily_recap_state.update(status="queued", chat_id=int(chat_id_text), queued_at=time.time())
    daily_recap_task = asyncio.create_task(_run_scheduled_daily_recap(int(chat_id_text)))
    return {"status": "accepted", "message": "Daily recap job queued"}


@web_app.get("/internal/daily-recap/status")
async def internal_daily_recap_status(
    x_nexora_daily_token: str = Header(default=""),
):
    """Expose only minimal job state to the authenticated GitHub Actions keepalive."""
    if not _daily_trigger_authorized(x_nexora_daily_token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "status": daily_recap_state.get("status", "idle"),
        "started_at": daily_recap_state.get("started_at"),
        "completed_at": daily_recap_state.get("completed_at"),
        "error": daily_recap_state.get("error"),
    }


@web_app.get("/download/{token}")
async def download_rendered_video(token: str):
    """Serve an MP4 through an unguessable, expiring, process-local download token."""
    record = DOWNLOAD_LINKS.get(token)
    if not record:
        raise HTTPException(status_code=404, detail="Download link is invalid or expired")
    if float(record.get("expires_at", 0)) <= time.time():
        DOWNLOAD_LINKS.pop(token, None)
        Path(str(record.get("path", ""))).unlink(missing_ok=True)
        raise HTTPException(status_code=410, detail="Download link has expired")
    path = Path(str(record.get("path", ""))).resolve()
    root = Path(os.getenv("NEXORA_WORK_DIR", "/tmp/nexora-work")).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        DOWNLOAD_LINKS.pop(token, None)
        raise HTTPException(status_code=404, detail="File not found")
    if path.suffix.lower() != ".mp4" or not path.is_file():
        DOWNLOAD_LINKS.pop(token, None)
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=str(record.get("filename", "nexora_recap.mp4")),
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


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
