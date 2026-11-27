"""Publishing: official-API upload when credentials + permission exist, otherwise a publish-ready draft.

A video is only reported as ``uploaded``/``verified`` after the platform API actually answered with an id; ``verified`` additionally
means a follow-up API read confirmed the video exists. TikTok has no unattended upload path here, so it is always a draft.
"""
import os
import re
from pathlib import Path

import requests

from .. import config

YT_URL = config.YOUTUBE_URL
FB_URL = config.FACEBOOK_URL
GRAPH = "https://graph.facebook.com/v19.0"
GRAPH_VIDEO = "https://graph-video.facebook.com/v19.0"


def build_metadata(project: dict, research: dict | None, credits: list[dict], cfg: dict) -> dict:
    t, year, cat = project["title"], project.get("year"), project.get("category") or ""
    platform = project["platform"]
    tags = ["#MovieRecap", "#မြန်မာဇာတ်လမ်းအကျဉ်း"] + (["#" + cat.replace(" ", "")] if cat else []) + ["#" + "".join(ch for ch in t if ch.isalnum())]
    title = f"{t}{f' ({year})' if year else ''} မြန်မာ Recap" + (" #shorts" if platform == "tiktok" else "")
    sources = []
    for s in (research or {}).get("source_refs", []) or []:
        sources.append(f"- {s.get('name', 'Source')}: {s.get('url', '')}")
    if (research or {}).get("wiki_url"):
        sources.append(f"- Wikipedia: {research['wiki_url']}")
    lines = [f"{t}{f' ({year})' if year else ''} — {cat + ' ' if cat else ''}recap in Burmese with English subtitles."]
    if sources:
        lines += ["", "Sources:"] + list(dict.fromkeys(sources))
    lines += ["", "AI disclosure: the narration in this video is synthetic (text-to-speech) and the script was written with AI assistance from the sources above."]
    if credits:
        lines += ["", "Image credits:"] + [f"- {c['title']} — {c['attribution'] or 'unknown author'} ({c['license']}) {c['page_url']}".strip() for c in credits]
    else:
        lines += ["", "Visuals: self-generated graphics (no movie footage is used)."]
    cta = cfg.get("cta") or ""
    lines += ["", cta, "", " ".join(tags)]
    return {"title": title[:100], "description": "\n".join(lines)[:4900], "tags": tags, "cta": cta}


# ----------------------------------------------------------------------------- availability
def capability(platform: str) -> dict:
    if platform == "youtube":
        need = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]
    elif platform == "facebook":
        need = ["FB_PAGE_ID", "FB_PAGE_TOKEN"]
    else:
        return {"publish_ready": False, "method": "draft", "missing": [],
                "note": "TikTok's Content Posting API needs an approved app audit, so NEXORA prepares a publish-ready draft (MP4 + caption) for manual upload."}
    missing = [n for n in need if not os.getenv(n)]
    if os.getenv("AUTO_UPLOAD", "0") != "1":
        missing.append("AUTO_UPLOAD=1")
    ok = not missing
    return {"publish_ready": ok, "method": "api" if ok else "draft", "missing": missing,
            "note": ("Official API upload is configured." if ok else "Missing server configuration; videos are prepared as drafts.") +
                    (" Uploads are created as 'private' on YouTube unless YT_PRIVACY=public." if platform == "youtube" else "")}


# ----------------------------------------------------------------------------- uploads
def _yt_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    cr = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], client_id=os.environ["YT_CLIENT_ID"],
                     client_secret=os.environ["YT_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token")
    return build("youtube", "v3", credentials=cr, cache_discovery=False)


def upload_youtube(mp4: Path, meta: dict, log=print) -> dict:
    from googleapiclient.http import MediaFileUpload
    yt = _yt_service()
    privacy = os.getenv("YT_PRIVACY", "private")
    body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": [t.strip("#") for t in meta["tags"]], "categoryId": "24"},
            "status": {"privacyStatus": privacy, "containsSyntheticMedia": True}}
    req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(str(mp4), chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st:
            log(f"[publish] youtube upload {int(st.progress() * 100)}%")
    vid = resp["id"]
    chk = yt.videos().list(part="status", id=vid).execute()
    items = chk.get("items", [])
    verified = bool(items) and items[0]["status"].get("uploadStatus") in ("uploaded", "processed")
    return {"status": "verified" if verified else "uploaded", "url": f"https://youtu.be/{vid}", "privacy": privacy, "external_id": vid,
            "detail": f"YouTube accepted the upload (privacy: {privacy})." + (" API read-back confirmed it." if verified else " Could not confirm via read-back yet.")}


def upload_facebook(mp4: Path, meta: dict, log=print) -> dict:
    page, tok = os.environ["FB_PAGE_ID"], os.environ["FB_PAGE_TOKEN"]
    size = mp4.stat().st_size
    base = f"{GRAPH_VIDEO}/{page}/videos"
    s = requests.post(base, data={"upload_phase": "start", "file_size": size, "access_token": tok}, timeout=60).json()
    if "upload_session_id" not in s:
        raise RuntimeError("Facebook start phase failed: " + str(s.get("error", s))[:200])
    sid, vid, start, end = s["upload_session_id"], s.get("video_id"), int(s["start_offset"]), int(s["end_offset"])
    with open(mp4, "rb") as f:
        while start != end:
            f.seek(start)
            r = requests.post(base, data={"upload_phase": "transfer", "start_offset": start, "upload_session_id": sid, "access_token": tok},
                              files={"video_file_chunk": f.read(end - start)}, timeout=600).json()
            if "start_offset" not in r:
                raise RuntimeError("Facebook transfer failed: " + str(r.get("error", r))[:200])
            start, end = int(r["start_offset"]), int(r["end_offset"])
            log(f"[publish] facebook upload {int(start / size * 100)}%")
    fin = requests.post(base, data={"upload_phase": "finish", "upload_session_id": sid, "access_token": tok, "title": meta["title"],
                                    "description": meta["description"]}, timeout=120).json()
    if not fin.get("success"):
        raise RuntimeError("Facebook finish failed: " + str(fin.get("error", fin))[:200])
    verified = False
    if vid:
        chk = requests.get(f"{GRAPH}/{vid}", params={"fields": "status", "access_token": tok}, timeout=30).json()
        verified = "status" in chk and "error" not in chk
    return {"status": "verified" if verified else "uploaded", "url": f"https://www.facebook.com/{page}/videos/{vid}" if vid else None, "external_id": vid,
            "detail": "Facebook accepted the upload." + (" API read-back confirmed it." if verified else " Could not confirm via read-back yet.")}


def publish(project: dict, mp4: Path, meta: dict, effective_mode: str, log=print) -> dict:
    """Return {mode,status,url,detail,metadata}. Statuses: draft_ready | uploaded | verified | failed | unavailable."""
    platform = project["platform"]
    base = {"mode": effective_mode, "metadata": meta, "url": None}
    if effective_mode != "auto":
        return {**base, "status": "draft_ready", "detail": "Draft prepared (publish mode is 'draft'). Upload the MP4 with the generated title, description and tags."}
    cap = capability(platform)
    if platform == "tiktok":
        return {**base, "status": "unavailable", "detail": cap["note"]}
    if not cap["publish_ready"]:
        return {**base, "status": "unavailable", "detail": "Auto-publish requested but not configured (missing: " + ", ".join(cap["missing"]) + "). Draft prepared instead."}
    try:
        res = upload_youtube(mp4, meta, log) if platform == "youtube" else upload_facebook(mp4, meta, log)
        return {**base, **res}
    except Exception as e:
        msg = re.sub(r"(access_token|client_secret|refresh_token)=[^&\s]+", r"\1=***", str(e))
        return {**base, "status": "failed", "detail": f"Upload failed: {msg[:300]}"}
