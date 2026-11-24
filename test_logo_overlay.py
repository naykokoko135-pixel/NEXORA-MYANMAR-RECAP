import unittest
from logo_overlay import LOGO_POSITIONS, build_logo_overlay_graph

class LogoOverlayTests(unittest.TestCase):
    def test_positions(self):
        for position in LOGO_POSITIONS:
            graph, output = build_logo_overlay_graph(3, position)
            self.assertEqual(output, "[vout]")
            self.assertIn("overlay=x=", graph)

    def test_opacity_and_input_validation(self):
        self.assertIn("aa=0.50", build_logo_overlay_graph(4, "top-left", 0.5)[0])
        with self.assertRaises(ValueError):
            build_logo_overlay_graph(0)
        with self.assertRaises(ValueError):
            build_logo_overlay_graph(3, "center")
        with self.assertRaises(ValueError):
            build_logo_overlay_graph(3, opacity=0)
