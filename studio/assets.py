"""Legal visual-asset sourcing.

Rules enforced in code (not just in the UI):
* Only openly licensed material is accepted: CC0, public domain, CC BY, CC BY-SA. NC / ND / GFDL-only / fair-use / unknown are rejected.
* Wikimedia Commons assets are re-verified server-side against Commons metadata before they are stored.
* Downloads only follow public https hosts (no private IPs), have a size cap, and are validated and re-encoded as JPEG.
* Uploads need an explicit rights declaration; their license is *user-declared* and is stored as unverified.
* Nothing here downloads from streaming services or bypasses DRM; no trailers/stills of copyrighted films are fetched.
"""
import html
import io
import ipaddress
import re
import socket
import time
import urllib.parse
from pathlib import Path

import requests

from . import core, db, security

UA = {"User-Agent": "NexoraRecapStudio/1.0 (https://github.com/naykokoko135-pixel/NEXORA-MYANMAR-RECAP)"}
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
MAX_DOWNLOAD = 25 * 1024 * 1024
MIN_W, MIN_H = 640, 360
ALLOWED_LICENSES = ["CC0", "Public domain", "CC BY", "CC BY-SA", "Own work (user-declared)"]
RULES = [
    "Only CC0, public-domain, CC BY and CC BY-SA material is accepted. NonCommercial, NoDerivatives, GFDL-only, fair-use and unknown licenses are rejected.",
    "Attribution is shown in the rendered video, written to credits.txt and added to the publish description when the license requires it.",
    "NEXORA never downloads from Netflix, Crunchyroll or any streaming service and never bypasses DRM. Posters, trailers and film stills are not fetched.",
    "Uploads need a rights declaration. Your license claim is recorded as user-declared; NEXORA cannot independently verify ownership.",
    "Visuals that are not authorised for this title are never presented as scenes from the movie. When no authorised asset exists, self-generated graphics are used.",
]
_UPLOAD_LICENSES = {"own-work": ("Own work (user-declared)", False), "cc0": ("CC0", False), "public-domain": ("Public domain", False),
                    "cc-by": ("CC BY", True), "cc-by-sa": ("CC BY-SA", True)}


class LicenseRejected(ValueError):
    pass


def classify_license(name: str, url: str = "") -> tuple[bool, str, bool, str | None]:
    """-> (allowed, normalised_name, attribution_required, reject_reason)."""
    n = re.sub(r"\s+", " ", html.unescape(str(name or "")).strip().lower())
    u = str(url or "").lower()
    if not n and not u:
        return False, "", True, "license missing"
    if re.search(r"\b(nc|non-?commercial|nd|no-?derivs?|noderivatives)\b", n) or "-nc" in u or "-nd" in u or "/by-nc" in u or "/by-nd" in u:
        return False, name, True, "NonCommercial/NoDerivatives licenses are not allowed"
    if "gfdl" in n or "fair use" in n or "all rights reserved" in n or "copyrighted" in n or "non-free" in n:
        return False, name, True, "license is not an open license suitable for reuse"
    if re.search(r"\bcc0\b|cc-zero|publicdomain/zero", n + " " + u):
        return True, "CC0", False, None
    if re.search(r"public domain|\bpd\b|pd-|publicdomain/mark", n + " " + u):
        return True, "Public domain", False, None
    m = re.search(r"cc[- ]by[- ]sa", n) or "/by-sa/" in u
    if m:
        return True, "CC BY-SA", True, None
    if re.search(r"cc[- ]by\b", n) or re.search(r"/licenses/by/", u):
        return True, "CC BY", True, None
    return False, name, True, "license is not on the allow-list"


# ---------------------------------------------------------------- safe fetching
def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


def safe_get(url: str, *, max_bytes=MAX_DOWNLOAD, timeout=40, params=None) -> requests.Response:
    """GET following up to 3 redirects, https only, public hosts only, body capped."""
    for _ in range(4):
        pu = urllib.parse.urlparse(url)
        if pu.scheme != "https" or not pu.hostname or not _public_host(pu.hostname):
            raise LicenseRejected("blocked URL (only public https hosts are allowed)")
        r = requests.get(url, headers=UA, timeout=timeout, stream=True, allow_redirects=False, params=params)
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
            url, params = urllib.parse.urljoin(url, r.headers["Location"]), None
            r.close()
            continue
        r.raise_for_status()
        if int(r.headers.get("Content-Length") or 0) > max_bytes:
            r.close()
            raise LicenseRejected("file too large")
        buf, size = io.BytesIO(), 0
        for chunk in r.iter_content(65536):
            size += len(chunk)
            if size > max_bytes:
                r.close()
                raise LicenseRejected("file too large")
            buf.write(chunk)
        r._content = buf.getvalue()
        return r
    raise LicenseRejected("too many redirects")


def normalise_image(data: bytes, dest: Path) -> tuple[int, int]:
    """Validate magic bytes + decode with Pillow, strip metadata, re-encode as JPEG (max 3840 px wide)."""
    from PIL import Image
    if not security.sniff_image(data[:16]):
        raise LicenseRejected("file is not a supported image (PNG, JPEG, WebP, GIF)")
    Image.MAX_IMAGE_PIXELS = 60_000_000
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        raise LicenseRejected("image could not be decoded")
    if im.width < MIN_W or im.height < MIN_H:
        raise LicenseRejected(f"image too small ({im.width}x{im.height}); minimum is {MIN_W}x{MIN_H}")
    im = im.convert("RGB")
    if im.width > 3840:
        im = im.resize((3840, round(im.height * 3840 / im.width)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=90)
    return im.width, im.height


# ---------------------------------------------------------------- Commons
def _strip_tags(v) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(v or ""))).strip()


def _commons_item(page: dict) -> dict | None:
    ii = (page.get("imageinfo") or [None])[0]
    if not ii:
        return None
    meta = ii.get("extmetadata") or {}
    lic_name = _strip_tags((meta.get("LicenseShortName") or {}).get("value"))
    lic_url = _strip_tags((meta.get("LicenseUrl") or {}).get("value"))
    allowed, norm, attr_req, reason = classify_license(lic_name, lic_url)
    if ii.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
        allowed, reason = False, f"unsupported media type {ii.get('mime')}"
    artist = _strip_tags((meta.get("Artist") or {}).get("value"))
    return {"origin": "commons", "title": re.sub(r"^File:", "", page.get("title", "")), "page_url": ii.get("descriptionurl", ""),
            "file_url": ii.get("thumburl") or ii.get("url", ""), "thumb_url": ii.get("thumburl") or "", "license": norm or lic_name, "license_url": lic_url,
            "attribution": artist[:200], "attribution_required": attr_req, "allowed": allowed, "reject_reason": reason,
            "width": ii.get("thumbwidth") or ii.get("width"), "height": ii.get("thumbheight") or ii.get("height"),
            "description": _strip_tags((meta.get("ImageDescription") or {}).get("value"))[:300]}


def search_commons(q: str, limit=12) -> list[dict]:
    d = requests.get(COMMONS_API, headers=UA, timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrsearch": q, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1600}).json()
    items = [_commons_item(p) for p in (d.get("query", {}).get("pages", {}) or {}).values()]
    return [i for i in items if i]


def commons_lookup(page_url: str) -> dict:
    """Re-fetch authoritative license metadata for a Commons file page URL."""
    pu = urllib.parse.urlparse(page_url)
    if pu.hostname != "commons.wikimedia.org" or "/wiki/File:" not in pu.path:
        raise LicenseRejected("page_url is not a Wikimedia Commons file page")
    title = urllib.parse.unquote(pu.path.split("/wiki/", 1)[1]).replace("_", " ")
    d = requests.get(COMMONS_API, headers=UA, timeout=30, params={
        "action": "query", "format": "json", "titles": title, "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1600}).json()
    pages = list((d.get("query", {}).get("pages") or {}).values())
    item = _commons_item(pages[0]) if pages and "missing" not in pages[0] else None
    if not item:
        raise LicenseRejected("Commons file not found")
    return item


# ---------------------------------------------------------------- Openverse
def search_openverse(q: str, limit=12) -> list[dict]:
    d = requests.get(OPENVERSE_API, headers=UA, timeout=30, params={"q": q, "page_size": limit, "license_type": "commercial,modification"}).json()
    out = []
    for r in d.get("results", []):
        lic = f"{r.get('license', '')}{(' ' + str(r.get('license_version'))) if r.get('license_version') else ''}"
        name = ("CC " + r.get("license", "").upper().replace("-", " ")) if r.get("license") not in ("cc0", "pdm") else r.get("license", "")
        allowed, norm, attr_req, reason = classify_license("CC0" if r.get("license") == "cc0" else "Public domain" if r.get("license") == "pdm" else name, r.get("license_url", ""))
        out.append({"origin": "openverse", "title": r.get("title") or "Untitled", "page_url": r.get("foreign_landing_url", ""), "file_url": r.get("url", ""),
                    "thumb_url": r.get("thumbnail") or "", "license": norm or lic, "license_url": r.get("license_url", ""),
                    "attribution": (r.get("creator") or "")[:200], "attribution_required": attr_req, "allowed": allowed, "reject_reason": reason,
                    "width": r.get("width"), "height": r.get("height"), "description": ""})
    return out


def search(q: str, source: str = "all") -> list[dict]:
    q = " ".join(str(q or "").split())[:120]
    if len(q) < 2:
        raise ValueError("Enter at least 2 characters")
    res, errs = [], []
    for name, fn in (("commons", search_commons), ("openverse", search_openverse)):
        if source in ("all", name):
            try:
                res += fn(q)
            except Exception as e:
                errs.append(f"{name}: {str(e)[:100]}")
    if not res and errs:
        raise RuntimeError("Asset search unavailable: " + "; ".join(errs))
    return res


# ---------------------------------------------------------------- storage
def asset_dir(project_id: int) -> Path:
    d = core.DATA_DIR / "assets" / str(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def asset_row_to_api(r: dict) -> dict:
    return {"id": r["id"], "project_id": r["project_id"], "origin": r["origin"], "title": r["title"], "page_url": r["page_url"], "file_url": r["file_url"],
            "local_path": Path(r["local_path"]).name if r["local_path"] else "", "license": r["license"], "license_url": r["license_url"],
            "attribution": r["attribution"], "attribution_required": bool(r["attribution_required"]), "verified": bool(r["verified"]),
            "note": r["note"], "width": None, "height": None, "created": r["created"]}


def list_assets(project_id: int) -> list[dict]:
    return [asset_row_to_api(r) for r in db.query("SELECT * FROM source_assets WHERE project_id=? ORDER BY id", (project_id,))]


def get_asset(asset_id: int) -> dict | None:
    return db.one("SELECT * FROM source_assets WHERE id=?", (asset_id,))


def _insert(project_id, origin, title, page_url, file_url, local, lic, lic_url, attribution, attr_req, verified, note) -> dict:
    with db.tx() as c:
        cur = c.execute("""INSERT INTO source_assets(project_id,origin,title,page_url,file_url,local_path,license,license_url,attribution,
                           attribution_required,verified,note,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (project_id, origin, title[:200], page_url, file_url, str(local), lic, lic_url, attribution, int(attr_req), int(verified), note, time.time()))
        aid = cur.lastrowid
    return asset_row_to_api(get_asset(aid))


def add_remote(project_id: int, *, origin: str, file_url: str, title: str, page_url: str, license: str = "", license_url: str = "",
               attribution: str = "") -> dict:
    """Download and store a remote asset after server-side license verification."""
    if origin == "commons":
        auth = commons_lookup(page_url)  # authoritative metadata, ignores client-supplied license fields
        if not auth["allowed"]:
            raise LicenseRejected(auth["reject_reason"] or "license rejected")
        lic, lic_url, attribution, attr_req = auth["license"], auth["license_url"], auth["attribution"], auth["attribution_required"]
        title, file_url, verified, note = auth["title"], auth["file_url"] or file_url, True, "License verified against Wikimedia Commons metadata."
    elif origin == "openverse":
        allowed, lic, attr_req, reason = classify_license(license, license_url)
        if not allowed:
            raise LicenseRejected(reason or "license rejected")
        lic_url = license_url
        pu = urllib.parse.urlparse(license_url)
        if pu.hostname not in ("creativecommons.org", "www.creativecommons.org"):
            raise LicenseRejected("license_url must point to creativecommons.org")
        verified, note = False, "License reported by Openverse; verify the source page before publishing."
    else:
        raise LicenseRejected("origin must be 'commons' or 'openverse'")
    r = safe_get(file_url)
    dest = asset_dir(project_id) / f"{origin}_{int(time.time() * 1000)}.jpg"
    normalise_image(r.content, dest)
    return _insert(project_id, origin, title, page_url, file_url, dest, lic, lic_url, attribution, attr_req, verified, note)


def add_upload(project_id: int, data: bytes, license_key: str, attribution: str, filename_hint: str = "upload") -> dict:
    if license_key not in _UPLOAD_LICENSES:
        raise LicenseRejected("license must be one of: " + ", ".join(_UPLOAD_LICENSES))
    lic, attr_req = _UPLOAD_LICENSES[license_key]
    if attr_req and not attribution.strip():
        raise LicenseRejected("attribution is required for CC BY / CC BY-SA")
    dest = asset_dir(project_id) / f"upload_{int(time.time() * 1000)}.jpg"
    normalise_image(data, dest)
    return _insert(project_id, "upload", re.sub(r"[^\w .-]", "", filename_hint)[:80] or "Upload", "", "", dest, lic, "", attribution.strip()[:200], attr_req,
                   False, "User-declared license and rights; not independently verified.")


def delete_asset(asset_id: int) -> bool:
    r = get_asset(asset_id)
    if not r:
        return False
    if r["local_path"] and core.is_within(Path(r["local_path"]), core.DATA_DIR):
        Path(r["local_path"]).unlink(missing_ok=True)
    with db.tx() as c:
        c.execute("DELETE FROM source_assets WHERE id=?", (asset_id,))
    return True


def relevant(item: dict, title: str) -> bool:
    """An automatically chosen asset must plausibly depict the work (title words in its name/description)."""
    words = [w for w in re.findall(r"[a-z0-9]{4,}", title.lower()) if w not in {"the", "that", "this", "with", "from", "movie", "film", "part"}]
    hay = (item.get("title", "") + " " + item.get("description", "")).lower()
    return bool(words) and any(w in hay for w in words)


def auto_collect(project_id: int, title: str, year, limit=8, log=print) -> list[dict]:
    """Find, verify and store up to ``limit`` authorised Commons images relevant to the title."""
    got, seen = [], set()
    for q in dict.fromkeys([f"{title} {year}" if year else title, title]):
        try:
            results = search_commons(q, 20)
        except Exception as e:
            raise RuntimeError(f"Commons search failed: {e}")
        for it in results:
            if len(got) >= limit:
                break
            if not it["allowed"] or it["page_url"] in seen or not relevant(it, title):
                continue
            if (it.get("width") or 0) < MIN_W or (it.get("height") or 0) < MIN_H:
                continue
            seen.add(it["page_url"])
            try:
                got.append(add_remote(project_id, origin="commons", file_url=it["file_url"], title=it["title"], page_url=it["page_url"]))
                log(f"[assets] added {it['title'][:60]} ({it['license']})")
            except Exception as e:  # skip a bad candidate, keep going
                log(f"[assets] skipped {it['title'][:50]}: {str(e)[:80]}")
        if len(got) >= limit:
            break
    return got
