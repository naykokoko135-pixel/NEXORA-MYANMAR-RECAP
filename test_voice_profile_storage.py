import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voice_profile_storage import (
    delete_persisted_voice_profile,
    load_voice_profiles,
    save_voice_profiles,
)


class PersistentVoiceProfileStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "profiles.sqlite3")
        self.env = patch.dict(os.environ, {"VOICE_PROFILE_DB_PATH": self.db_path})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp_dir.cleanup()

    def test_profiles_survive_reload_and_are_isolated_by_user(self):
        profiles = {"ဇာတ်ကြောင်းပြော": {"filename": "narrator.mp3", "audio": b"voice-data"}}
        save_voice_profiles(1001, profiles)
        self.assertEqual(load_voice_profiles(1001), {"ဇာတ်ကြောင်းပြော": {"filename": "ဇာတ်ကြောင်းပြော.mp3", "audio": b"voice-data"}})
        self.assertEqual(load_voice_profiles(2002), {})

    def test_save_replaces_only_current_users_profiles(self):
        save_voice_profiles(1001, {"old": {"filename": "old.ogg", "audio": b"old"}})
        save_voice_profiles(2002, {"other": {"filename": "other.wav", "audio": b"other"}})
        save_voice_profiles(1001, {"new": {"filename": "new.mp3", "audio": b"new"}})
        self.assertEqual(set(load_voice_profiles(1001)), {"new"})
        self.assertEqual(set(load_voice_profiles(2002)), {"other"})

    def test_delete_persisted_profile(self):
        save_voice_profiles(1001, {"hero": {"filename": "hero.mp3", "audio": b"hero"}})
        delete_persisted_voice_profile(1001, "hero")
        self.assertEqual(load_voice_profiles(1001), {})

    def test_invalid_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            save_voice_profiles(1001, {"bad/name": {"filename": "x.mp3", "audio": b"x"}})


if __name__ == "__main__":
    unittest.main()
