import unittest

from voice_profiles import (
    MAX_AUDIO_BYTES,
    MAX_TOTAL_PROFILE_BYTES,
    delete_voice_profile,
    normalize_profile_name,
    store_voice_profile,
)


class VoiceProfileTests(unittest.TestCase):
    def test_store_and_delete(self):
        profiles = {}
        store_voice_profile(profiles, "Hero", "take.mp3", b"audio")
        self.assertEqual(profiles["Hero"]["audio"], b"audio")
        delete_voice_profile(profiles, "Hero")
        self.assertEqual(profiles, {})

    def test_invalid_names(self):
        for name in ("", "../bad", "a" * 25, "bad/name"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                normalize_profile_name(name)

    def test_accept_burmese_profile_name(self):
        self.assertEqual(normalize_profile_name("မေ"), "မေ")

    def test_reject_invalid_audio(self):
        with self.assertRaises(ValueError):
            store_voice_profile({}, "Hero", "x.exe", b"x")
        with self.assertRaises(ValueError):
            store_voice_profile({}, "Hero", "x.mp3", b"x" * (MAX_AUDIO_BYTES + 1))

    def test_profile_limit(self):
        profiles = {str(i): {"filename": "x.mp3", "audio": b"x"} for i in range(12)}
        with self.assertRaises(ValueError):
            store_voice_profile(profiles, "extra", "x.mp3", b"x")

    def test_total_storage_budget(self):
        profiles = {}
        store_voice_profile(profiles, "one", "one.mp3", b"x" * (MAX_TOTAL_PROFILE_BYTES - 2))
        with self.assertRaises(ValueError):
            store_voice_profile(profiles, "two", "two.mp3", b"xxx")


if __name__ == "__main__":
    unittest.main()
