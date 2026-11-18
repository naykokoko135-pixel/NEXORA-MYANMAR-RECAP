"""SQLite-backed storage for creator-owned prerecorded voice profiles.

For durable hosting, point VOICE_PROFILE_DB_PATH at a mounted persistent volume.
A database on an ephemeral container filesystem will still be lost on redeploy.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from voice_profiles import (
    MAX_AUDIO_BYTES,
    MAX_PROFILES,
    MAX_TOTAL_PROFILE_BYTES,
    normalize_profile_name,
    store_voice_profile,
)

DEFAULT_DB_PATH = os.getenv("VOICE_PROFILE_DB_PATH", "data/nexora_voice_profiles.sqlite3")


def database_path() -> Path:
    return Path(os.getenv("VOICE_PROFILE_DB_PATH", DEFAULT_DB_PATH)).expanduser()


def _connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=15)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS voice_profiles (
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            filename TEXT NOT NULL,
            audio BLOB NOT NULL,
            PRIMARY KEY (user_id, name)
        )
    """)
    return connection


def load_voice_profiles(user_id: int | str) -> dict:
    if user_id is None:
        raise ValueError("Telegram user ID မရရှိပါ။")
    profiles = {}
    with _connect() as connection:
        rows = connection.execute(
            "SELECT name, filename, audio FROM voice_profiles WHERE user_id = ? ORDER BY name",
            (str(user_id),),
        ).fetchall()
    for name, filename, audio in rows:
        store_voice_profile(profiles, name, filename, bytes(audio))
    return profiles


def save_voice_profiles(user_id: int | str, profiles: dict) -> None:
    if user_id is None:
        raise ValueError("Telegram user ID မရရှိပါ။")
    if len(profiles) > MAX_PROFILES:
        raise ValueError("Voice Profile အများဆုံး ၁၂ ခုသာ သိမ်းနိုင်ပါတယ်။")
    total = 0
    checked = {}
    for raw_name, entry in profiles.items():
        name = normalize_profile_name(raw_name)
        filename = str(entry.get("filename", ""))
        audio = entry.get("audio")
        if not isinstance(audio, bytes) or not audio or len(audio) > MAX_AUDIO_BYTES:
            raise ValueError("Voice Profile အသံဖိုင်အချက်အလက် မမှန်ပါ။")
        total += len(audio)
        if total > MAX_TOTAL_PROFILE_BYTES:
            raise ValueError("Voice Profile အားလုံးပေါင်း ၄၀ MB ထက် ကျော်နေပါတယ်။")
        checked[name] = (filename, audio)
    with _connect() as connection:
        connection.execute("DELETE FROM voice_profiles WHERE user_id = ?", (str(user_id),))
        connection.executemany(
            "INSERT INTO voice_profiles (user_id, name, filename, audio) VALUES (?, ?, ?, ?)",
            [(str(user_id), name, filename, sqlite3.Binary(audio))
             for name, (filename, audio) in checked.items()],
        )


def delete_persisted_voice_profile(user_id: int | str, name: str) -> None:
    key = normalize_profile_name(name)
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM voice_profiles WHERE user_id = ? AND name = ?",
            (str(user_id), key),
        )
        if cursor.rowcount == 0:
            raise ValueError("သိမ်းထားသောအသံ Profile မတွေ့ပါ။")
