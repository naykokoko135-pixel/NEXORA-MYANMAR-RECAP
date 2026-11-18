import unittest
import zipfile
from io import BytesIO

from voice_profile_backup import (
    VoiceProfileBackupError,
    export_voice_profile_backup,
    import_voice_profile_backup,
)


class VoiceProfileBackupTests(unittest.TestCase):
    def test_round_trip_preserves_burmese_names_and_audio(self):
        profiles = {
            "ဇာတ်ကြောင်းပြော": {"filename": "narrator.mp3", "audio": b"voice-a"},
            "သူရဲကောင်း": {"filename": "hero.wav", "audio": b"voice-b"},
        }
        restored = import_voice_profile_backup(export_voice_profile_backup(profiles))
        self.assertEqual(restored, {
            "ဇာတ်ကြောင်းပြော": {"filename": "ဇာတ်ကြောင်းပြော.mp3", "audio": b"voice-a"},
            "သူရဲကောင်း": {"filename": "သူရဲကောင်း.wav", "audio": b"voice-b"},
        })

    def test_import_merges_with_existing_profiles(self):
        archive = export_voice_profile_backup({"hero": {"filename": "hero.ogg", "audio": b"hero"}})
        restored = import_voice_profile_backup(archive, {"narrator": {"filename": "narrator.mp3", "audio": b"narrator"}})
        self.assertEqual(set(restored), {"hero", "narrator"})

    def test_invalid_zip_rejected(self):
        with self.assertRaises(VoiceProfileBackupError):
            import_voice_profile_backup(b"not a zip")

    def test_unknown_manifest_version_rejected(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("manifest.json", '{"format":"nexora-voice-profiles","version":99,"profiles":[]}')
        with self.assertRaises(VoiceProfileBackupError):
            import_voice_profile_backup(buffer.getvalue())

    def test_unlisted_file_rejected(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("manifest.json", '{"format":"nexora-voice-profiles","version":1,"profiles":[]}')
            archive.writestr("extra.txt", "unexpected")
        with self.assertRaises(VoiceProfileBackupError):
            import_voice_profile_backup(buffer.getvalue())

    def test_path_traversal_rejected(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("manifest.json", '{"format":"nexora-voice-profiles","version":1,"profiles":[{"name":"hero","file":"../hero.mp3","size":4}]}')
            archive.writestr("../hero.mp3", b"evil")
        with self.assertRaises(VoiceProfileBackupError):
            import_voice_profile_backup(buffer.getvalue())

    def test_corrupt_size_metadata_rejected(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("manifest.json", '{"format":"nexora-voice-profiles","version":1,"profiles":[{"name":"hero","file":"audio/00.mp3","size":99}]}')
            archive.writestr("audio/00.mp3", b"voice")
        with self.assertRaises(VoiceProfileBackupError):
            import_voice_profile_backup(buffer.getvalue())

    def test_empty_export_is_valid(self):
        self.assertEqual(import_voice_profile_backup(export_voice_profile_backup({})), {})


if __name__ == "__main__":
    unittest.main()
