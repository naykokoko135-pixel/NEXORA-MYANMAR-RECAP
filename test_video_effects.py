import unittest

from video_effects import EFFECT_PRESETS, build_effect_filter


class VideoEffectPresetTests(unittest.TestCase):
    def test_all_presets_build_platform_specific_filters(self):
        for preset in EFFECT_PRESETS:
            for dimensions in ((1280, 720), (864, 1080), (720, 1280)):
                result = build_effect_filter(preset, *dimensions)
                self.assertIn(f"scale={dimensions[0]}:{dimensions[1]}", result)
                self.assertIn("format=yuv420p", result)

    def test_unknown_preset_is_rejected(self):
        with self.assertRaises(ValueError):
            build_effect_filter("not-a-real-effect", 1280, 720)

    def test_unsupported_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            build_effect_filter("cinematic", 1920, 1080)
