import unittest
from render_quality import QUALITY_DIMENSIONS, resolve_output_dimensions

class RenderQualityTests(unittest.TestCase):
    def test_platform_dimensions(self):
        self.assertEqual(resolve_output_dimensions("youtube", "1080p"), (1920, 1080))
        self.assertEqual(resolve_output_dimensions("tiktok", "1080p"), (1080, 1920))
        self.assertEqual(resolve_output_dimensions("facebook", "720p"), (864, 1080))

    def test_all_quality_profiles_are_even(self):
        for profile in QUALITY_DIMENSIONS.values():
            for width, height in profile.values():
                self.assertEqual(width % 2, 0)
                self.assertEqual(height % 2, 0)

    def test_invalid_values(self):
        with self.assertRaises(ValueError):
            resolve_output_dimensions("youtube", "4k")
        with self.assertRaises(ValueError):
            resolve_output_dimensions("square", "720p")
