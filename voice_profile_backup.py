"""Safe export/import backups for session-scoped prerecorded voice profiles."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import PurePosixPath
import zipfile

from voice_profiles import (
    ALLOWED_AUDIO_SUFFIXES,
    MAX_AUDIO_BYTES,
    MAX_PROFILES,
    MAX_TOTAL_PROFILE_BYTES,
    normalize_profile_name,
    store_voice_profile,
)

MANIFEST_NAME = "manifest.json"
MAX_BACKUP_BYTES = MAX_TOTAL_PROFILE_BYTES + 1024 * 1024


class VoiceProfileBackupError(ValueError):
    """Raised when a voice-profile backup is invalid or unsafe."""


def export_voice_profile_backup(profiles: dict) -> bytes:
    """Return a ZIP backup containing only validated profile audio and metadata."""
    if len(profiles) > MAX_PROFILES:
        raise VoiceProfileBackupError("Voice Profile အများဆုံး ၁၂ ခုသာ Backup လုပ်နိုင်ပါတယ်။")

    validated = {}
    total = 0
    for name, entry in profiles.items():
        try:
            key = normalize_profile_name(name)
            filename = str(entry.get("filename", ""))
            suffix = PurePosixPath(filename).suffix.lower()
            audio = entry.get("audio")
            if suffix not in ALLOWED_AUDIO_SUFFIXES or not isinstance(audio, bytes) or not audio:
                raise ValueError
            if len(audio) > MAX_AUDIO_BYTES:
                raise ValueError
            if key in validated:
                raise ValueError
            total += len(audio)
            if total > MAX_TOTAL_PROFILE_BYTES:
                raise ValueError
            validated[key] = (suffix, audio)
        except (AttributeError, TypeError, ValueError) as exc:
            raise VoiceProfileBackupError("သိမ်းထားသော Voice Profile အချက်အလက် မမှန်ပါ။") from exc

    manifest = {"format": "nexora-voice-profiles", "version": 1, "profiles": []}
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, (name, (suffix, audio)) in enumerate(sorted(validated.items())):
            member = f"audio/{index:02d}{suffix}"
            manifest["profiles"].append({"name": name, "file": member, "size": len(audio)})
            archive.writestr(member, audio)
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False))
    result = buffer.getvalue()
    if len(result) > MAX_BACKUP_BYTES:
        raise VoiceProfileBackupError("Backup ဖိုင်အရွယ်အစား ကန့်သတ်ချက်ကျော်နေပါတယ်။")
    return result


def import_voice_profile_backup(data: bytes, existing: dict | None = None) -> dict:
    """Validate a backup fully, then return existing profiles merged with its entries."""
    if not isinstance(data, bytes) or not data or len(data) > MAX_BACKUP_BYTES:
        raise VoiceProfileBackupError("Backup ZIP ဖိုင် ဗလာဖြစ်နေခြင်း သို့မဟုတ် အရွယ်အစားကျော်နေပါတယ်။")

    try:
        with zipfile.ZipFile(BytesIO(data), "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_PROFILES + 1 or len(infos) < 1:
                raise VoiceProfileBackupError("Backup ထဲရှိ ဖိုင်အရေအတွက် မမှန်ပါ။")
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or MANIFEST_NAME not in names:
                raise VoiceProfileBackupError("Backup ဖိုင်ဖွဲ့စည်းပုံ မမှန်ပါ။")
            if any(info.is_dir() or info.flag_bits & 0x1 for info in infos):
                raise VoiceProfileBackupError("Folder သို့မဟုတ် encrypted ZIP ကို လက်မခံပါ။")
            if any(info.file_size > MAX_AUDIO_BYTES for info in infos if info.filename != MANIFEST_NAME):
                raise VoiceProfileBackupError("အသံဖိုင်တစ်ခုသည် ၂၀ MB ထက် ကျော်နေပါတယ်။")

            if archive.getinfo(MANIFEST_NAME).file_size > 64 * 1024:
                raise VoiceProfileBackupError("Backup manifest အရွယ်အစား မမှန်ပါ။")
            manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
            if not isinstance(manifest, dict):
                raise VoiceProfileBackupError("Backup manifest ပုံစံ မမှန်ပါ။")
            if manifest.get("format") != "nexora-voice-profiles" or manifest.get("version") != 1:
                raise VoiceProfileBackupError("NEXORA Voice Profile Backup version မကိုက်ညီပါ။")
            entries = manifest.get("profiles")
            if not isinstance(entries, list) or len(entries) > MAX_PROFILES:
                raise VoiceProfileBackupError("Voice Profile အရေအတွက် မမှန်ပါ။")

            expected_files = {MANIFEST_NAME}
            restored = dict(existing or {})
            total = 0
            restored_names = set()
            for item in entries:
                if not isinstance(item, dict):
                    raise VoiceProfileBackupError("Backup metadata မမှန်ပါ။")
                raw_name = item.get("name", "")
                if not isinstance(raw_name, str):
                    raise VoiceProfileBackupError("Backup Profile အမည် မမှန်ပါ။")
                name = normalize_profile_name(raw_name)
                if any(name == existing_name for existing_name in restored_names):
                    raise VoiceProfileBackupError("Backup ထဲတွင် Profile အမည် ထပ်နေပါတယ်။")
                restored_names.add(name)
                member = item.get("file")
                if not isinstance(member, str) or PurePosixPath(member).parts[:1] != ("audio",) or len(PurePosixPath(member).parts) != 2:
                    raise VoiceProfileBackupError("Backup ထဲရှိ audio path မမှန်ပါ။")
                suffix = PurePosixPath(member).suffix.lower()
                if suffix not in ALLOWED_AUDIO_SUFFIXES:
                    raise VoiceProfileBackupError("Backup ထဲရှိ အသံဖိုင်အမျိုးအစား မမှန်ပါ။")
                if member in expected_files or member not in names:
                    raise VoiceProfileBackupError("Backup ထဲရှိ အသံဖိုင် လမ်းကြောင်း မမှန်ပါ။")
                expected_files.add(member)
                audio = archive.read(member)
                if not audio or len(audio) > MAX_AUDIO_BYTES or item.get("size") != len(audio):
                    raise VoiceProfileBackupError("Backup ထဲရှိ အသံဖိုင် အရွယ်အစား မကိုက်ညီပါ။")
                total += len(audio)
                if total > MAX_TOTAL_PROFILE_BYTES:
                    raise VoiceProfileBackupError("Backup အသံဖိုင်အားလုံးပေါင်း ၄၀ MB ထက် ကျော်နေပါတယ်။")
                store_voice_profile(restored, name, name + suffix, audio)

            if set(names) != expected_files:
                raise VoiceProfileBackupError("Backup ထဲတွင် မသက်ဆိုင်သော ဖိုင်များ ပါဝင်နေပါတယ်။")
            return restored
    except VoiceProfileBackupError:
        raise
    except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, OSError) as exc:
        raise VoiceProfileBackupError("Backup ZIP ဖိုင်ကို ဖတ်မရပါ။ မှန်ကန်သော NEXORA Backup ကို သုံးပါ။") from exc
