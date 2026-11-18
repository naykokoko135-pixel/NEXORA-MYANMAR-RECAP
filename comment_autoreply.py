"""Conservative comment-reply helpers for NEXORA.

YouTube and Facebook Page replies use their official APIs when explicitly enabled.
TikTok is draft-only: the public Research API is read-only and is not a creator reply API.
"""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
FACEBOOK_GRAPH_VERSION = os.getenv("FACEBOOK_GRAPH_VERSION", "v27.0")
MAX_REPLIES_PER_PLATFORM_PER_CYCLE = 3

MYANMAR_POSITIVE = ("ကျေးဇူး", "ကောင်းတယ်", "အရမ်းကောင်း", "ကြိုက်တယ်", "မိုက်တယ်")
ENGLISH_POSITIVE = re.compile(r"\\b(?:thank|thanks|thankyou|nice|good|great|love|amazing|awesome)\\b", re.I)
ENGLISH_NEGATIVE = re.compile(r"\\b(?:not|bad|hate|dislike|terrible|worst|wrong|issue|problem|scam|fake|stop|refund)\\b", re.I)
URL_OR_CONTACT = re.compile(r"(https?://|www\.|\b\S+@\S+\.[A-Za-z]{2,}\b|\+?\d[\d\s().-]{7,}\d)", re.I)


def classify_comment(comment: str) -> str:
    """Return auto_safe only for short, unambiguous positive comments."""
    text = " ".join((comment or "").strip().lower().split())
    if not text or len(text) > 160 or URL_OR_CONTACT.search(text):
        return "review"
    if ENGLISH_NEGATIVE.search(text) or any(mark in text for mark in ("?", "？", "ဘာလို့", "ဘယ်လို", "မကောင်း", "မကြိုက်", "တိုင်ကြား")):
        return "review"
    if any(word in text for word in MYANMAR_POSITIVE) or bool(ENGLISH_POSITIVE.search(text)):
        return "auto_safe"
    if all(ch in "❤️💖💕👍🙏👏🔥✨😊🙂😀😁🥰😍! .," or ch == "\ufe0f" for ch in text):
        return "auto_safe"
    return "review"


def build_reply(comment: str) -> str | None:
    """Create a short non-personal reply only for an unambiguous positive comment."""
    if classify_comment(comment) != "auto_safe":
        return None
    text = comment or ""
    if any("\u1000" <= ch <= "\u109f" for ch in text):
        return "ကြည့်ရှုပေးလို့ ကျေးဇူးတင်ပါတယ်။ နောက်ထပ် Recap တွေလည်း တင်ပေးသွားပါမယ်။"
    return "Thanks for watching! More recaps are on the way."


def _request_json(url: str, token: str, payload: dict | None = None, *, json_body: bool = False) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    if payload is not None:
        if json_body:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        else:
            data = urlencode(payload).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urlopen(request, timeout=20) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        # Never include URLs or request headers in errors: they may contain credentials.
        raise RuntimeError("Platform comment API request failed.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Platform returned an invalid response.")
    if parsed.get("error"):
        raise RuntimeError("Platform rejected the comment API request.")
    return parsed


def _youtube_cycle(env: dict) -> tuple[int, int]:
    token = env.get("YOUTUBE_COMMENT_ACCESS_TOKEN", "").strip()
    channel_id = env.get("YOUTUBE_CHANNEL_ID", "").strip()
    video_ids = [v.strip() for v in env.get("YOUTUBE_COMMENT_VIDEO_IDS", "").split(",") if v.strip()]
    if not token or not channel_id or not video_ids:
        return 0, 0
    sent = reviewed = 0
    for video_id in video_ids:
        if sent >= MAX_REPLIES_PER_PLATFORM_PER_CYCLE:
            break
        query = urlencode({"part": "snippet,replies", "videoId": video_id, "order": "time", "maxResults": 20, "textFormat": "plainText"})
        result = _request_json(f"{YOUTUBE_API}/commentThreads?{query}", token)
        for thread in result.get("items", []):
            if sent >= MAX_REPLIES_PER_PLATFORM_PER_CYCLE:
                break
            snippet = thread.get("snippet", {})
            top = snippet.get("topLevelComment", {})
            top_snippet = top.get("snippet", {})
            comment_id = top.get("id") or thread.get("id")
            author_channel = top_snippet.get("authorChannelId", {}).get("value", "")
            if not comment_id or author_channel == channel_id or int(snippet.get("totalReplyCount", 0) or 0) > 0:
                continue
            reply = build_reply(top_snippet.get("textOriginal") or top_snippet.get("textDisplay") or "")
            if not reply:
                reviewed += 1
                continue
            _request_json(
                f"{YOUTUBE_API}/comments?part=snippet",
                token,
                {"snippet": {"parentId": comment_id, "textOriginal": reply}},
                json_body=True,
            )
            sent += 1
    return sent, reviewed


def _facebook_cycle(env: dict) -> tuple[int, int]:
    token = env.get("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
    page_id = env.get("FACEBOOK_PAGE_ID", "").strip()
    post_ids = [v.strip() for v in env.get("FACEBOOK_POST_IDS", "").split(",") if v.strip()]
    if not token or not page_id or not post_ids:
        return 0, 0
    sent = reviewed = 0
    version = env.get("FACEBOOK_GRAPH_VERSION", FACEBOOK_GRAPH_VERSION).strip()
    for post_id in post_ids:
        if sent >= MAX_REPLIES_PER_PLATFORM_PER_CYCLE:
            break
        query = urlencode({"fields": "id,message,from,comments.limit(10){id,from}", "limit": 20})
        result = _request_json(f"https://graph.facebook.com/{version}/{post_id}/comments?{query}", token)
        for comment in result.get("data", []):
            if sent >= MAX_REPLIES_PER_PLATFORM_PER_CYCLE:
                break
            author_id = (comment.get("from") or {}).get("id", "")
            if not comment.get("id") or author_id == page_id:
                continue
            replies = (comment.get("comments") or {}).get("data", [])
            if any((reply.get("from") or {}).get("id") == page_id for reply in replies):
                continue
            reply = build_reply(comment.get("message", ""))
            if not reply:
                reviewed += 1
                continue
            _request_json(
                f"https://graph.facebook.com/{version}/{comment['id']}/comments",
                token,
                {"message": reply},
            )
            sent += 1
    return sent, reviewed


def run_comment_autoreply_cycle(environ: dict | None = None) -> dict:
    """Run a bounded, conservative polling cycle. Disabled unless explicitly enabled."""
    env = dict(os.environ if environ is None else environ)
    if env.get("COMMENT_AUTOREPLY_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return {"enabled": False, "youtube_sent": 0, "facebook_sent": 0, "review": 0}
    result = {"enabled": True, "youtube_sent": 0, "facebook_sent": 0, "review": 0}
    for platform, worker in (("youtube", _youtube_cycle), ("facebook", _facebook_cycle)):
        try:
            sent, reviewed = worker(env)
            result[f"{platform}_sent"] = sent
            result["review"] += reviewed
        except RuntimeError:
            # Keep secrets and user content out of service logs; the next cycle can retry.
            result["review"] += 1
    return result


def platform_comment_capabilities() -> dict:
    """Describe verified integration capability without exposing credential values."""
    return {
        "youtube": "official API reply supported; OAuth and channel/video configuration required",
        "facebook": "official Page comment reply supported; Page token and permissions required",
        "tiktok": "draft-only; public Research API can read comments but does not provide creator reply posting",
    }
