"""Metadata for every platform + optional auto-upload (YouTube/Facebook). TikTok = draft/export only."""
import os
from pathlib import Path

import requests

from . import config


def metadata(src, platform):
    t = src["title"]
    cat = src["category"]
    tags = ["#MovieRecap", "#မြန်မာဇာတ်လမ်းအကျဉ်း", "#" + cat.replace(" ", ""), "#" + "".join(ch for ch in t if ch.isalnum())]
    cta = f"▶️ YouTube: {config.YOUTUBE_URL}\n📘 Facebook: {config.FACEBOOK_URL}" if platform == "tiktok" else \
        f"Subscribe / Follow:\n▶️ YouTube: {config.YOUTUBE_URL}\n📘 Facebook: {config.FACEBOOK_URL}"
    title = f"{t} ({src['year']}) မြန်မာ Recap" + (" #shorts" if platform == "tiktok" else "")
    desc = (f"{t} ({src['year']}) — {cat} recap in Burmese with English subtitles.\n\nSources: {', '.join(src['sources'])}\n"
            f"{src['wiki_url']}\nVisuals: self-generated graphics.\n\n{cta}\n\n{' '.join(tags)}")
    return dict(title=title[:100], description=desc, tags=tags, cta=cta)


def upload_youtube(mp4, meta, log=print):
    need = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]
    if not all(os.getenv(k) for k in need):
        return None
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    cr = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], client_id=os.environ["YT_CLIENT_ID"],
                     client_secret=os.environ["YT_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=cr)
    body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": [t.strip("#") for t in meta["tags"]],
                        "categoryId": "24"}, "status": {"privacyStatus": os.getenv("YT_PRIVACY", "private")}}
    req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(str(mp4), chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return f"https://youtu.be/{resp['id']}"


def upload_facebook(mp4, meta, log=print):
    page, tok = os.getenv("FB_PAGE_ID"), os.getenv("FB_PAGE_TOKEN")
    if not (page and tok):
        return None
    base = f"https://graph-video.facebook.com/v19.0/{page}/videos"
    size = Path(mp4).stat().st_size
    s = requests.post(base, data={"upload_phase": "start", "file_size": size, "access_token": tok}, timeout=60).json()
    sid, start, end = s["upload_session_id"], int(s["start_offset"]), int(s["end_offset"])
    with open(mp4, "rb") as f:
        while start != end:
            f.seek(start)
            chunk = f.read(end - start)
            r = requests.post(base, data={"upload_phase": "transfer", "start_offset": start, "upload_session_id": sid, "access_token": tok},
                              files={"video_file_chunk": chunk}, timeout=600).json()
            start, end = int(r["start_offset"]), int(r["end_offset"])
    r = requests.post(base, data={"upload_phase": "finish", "upload_session_id": sid, "access_token": tok, "title": meta["title"],
                                  "description": meta["description"]}, timeout=120).json()
    return f"facebook video upload ok: {r}"


def auto_upload(platform, mp4, meta, log=print):
    if os.getenv("AUTO_UPLOAD", "0") != "1":
        return "auto-upload off (AUTO_UPLOAD=1 to enable)"
    try:
        if platform == "youtube":
            return upload_youtube(mp4, meta, log) or "YouTube API credentials missing"
        if platform == "facebook":
            return upload_facebook(mp4, meta, log) or "Facebook page credentials missing"
        return "TikTok: draft/export only (manual upload with the generated caption)"
    except Exception as e:
        return f"upload failed: {e}"
