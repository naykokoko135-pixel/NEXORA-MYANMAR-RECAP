import os
import subprocess
from pathlib import Path

import requests

from . import config

TG_LIMIT = 49 * 1024 * 1024


def tg(text, chat=None):
    chat = chat or config.TG_CHAT
    if not (config.TG_TOKEN and chat):
        print("[tg-disabled]", text)
        return
    for i in range(0, len(text), 3900):
        try:
            requests.post(f"https://api.telegram.org/bot{config.TG_TOKEN}/sendMessage",
                          json={"chat_id": chat, "text": text[i:i + 3900], "disable_web_page_preview": True}, timeout=30)
        except Exception as e:  # noqa
            print("tg error", e)


def tg_file(path, caption="", chat=None):
    chat = chat or config.TG_CHAT
    p = Path(path)
    if not (config.TG_TOKEN and chat) or not p.exists():
        return False
    if p.stat().st_size > TG_LIMIT:
        return False
    with p.open("rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{config.TG_TOKEN}/sendDocument",
                          data={"chat_id": chat, "caption": caption[:900]}, files={"document": f}, timeout=600)
    return r.ok


def r2_upload(path, key):
    need = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"]
    if not all(os.getenv(k) for k in need):
        return None
    import boto3
    s3 = boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                      region_name="auto")
    s3.upload_file(str(path), os.environ["R2_BUCKET"], key)
    return s3.generate_presigned_url("get_object", Params={"Bucket": os.environ["R2_BUCKET"], "Key": key}, ExpiresIn=7 * 86400)


def split_for_telegram(mp4, wd):
    from .tts import ffprobe_dur
    size, dur = Path(mp4).stat().st_size, ffprobe_dur(mp4)
    seg = max(60, int(dur * (TG_LIMIT * 0.9) / size))
    pat = str(Path(wd) / "part_%02d.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-c", "copy", "-f", "segment", "-segment_time", str(seg),
                    "-reset_timestamps", "1", pat], check=True)
    return sorted(Path(wd).glob("part_*.mp4"))


def deliver(mp4, extras, caption, wd, chat=None, name="video"):
    """Telegram if <50MB; else R2 link; else split into parts."""
    for e in extras:
        tg_file(e, "", chat)
    size = Path(mp4).stat().st_size
    if size <= TG_LIMIT:
        if tg_file(mp4, caption, chat):
            return "telegram"
    link = r2_upload(mp4, f"recaps/{name}.mp4")
    if link:
        tg(f"{caption}\n\n⬇️ Download (7 days):\n{link}", chat)
        return "r2"
    parts = split_for_telegram(mp4, wd)
    for i, p in enumerate(parts, 1):
        tg_file(p, f"{caption}\nPart {i}/{len(parts)}", chat)
    return f"telegram-split-{len(parts)}"
