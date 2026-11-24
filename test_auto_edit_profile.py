import unittest

from auto_edit_profile import build_auto_edit_profile, list_auto_edit_categories


class AutoEditProfileTests(unittest.TestCase):
    def test_every_profile_uses_supported_presets(self):
        from video_effects import EFFECT_PRESETS
        from audio_mastering import AUDIO_PRESETS
        from video_transitions import TRANSITIONS
        for category in list_auto_edit_categories():
            profile = build_auto_edit_profile(category, "youtube")
            self.assertIn(profile["effect_preset"], EFFECT_PRESETS)
            self.assertIn(profile["audio_preset"], AUDIO_PRESETS)
            self.assertIn(profile["transition"], TRANSITIONS)

    def test_aliases_and_unknown_category_fallback(self):
        self.assertEqual(build_auto_edit_profile("3D")["category"], "3d animation")
        self.assertEqual(build_auto_edit_profile("unknown")["effect_preset"], "cinematic")

    def test_platform_validation(self):
        with self.assertRaises(ValueError):
            build_auto_edit_profile("anime", "square")
