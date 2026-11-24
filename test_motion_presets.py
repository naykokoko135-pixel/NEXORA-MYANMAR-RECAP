import unittest
from motion_presets import MOTION_PRESETS, build_motion_filter

class MotionPresetTests(unittest.TestCase):
    def test_all_presets(self):
        for name in MOTION_PRESETS:
            value = build_motion_filter(name, 1280, 720)
            if name == "none":
                self.assertEqual(value, "")
            elif "zoompan" in value:
                self.assertIn("1280x720", value)
            else:
                self.assertIn("crop=1280:720", value)

    def test_invalid_preset_and_dimensions(self):
        with self.assertRaises(ValueError):
            build_motion_filter("shake-camera", 1280, 720)
        with self.assertRaises(ValueError):
            build_motion_filter("pushin", 0, 720)
