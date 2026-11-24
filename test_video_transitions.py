import unittest
from video_transitions import TRANSITIONS, build_transition_graph
class VideoTransitionTests(unittest.TestCase):
    def test_offsets(self):
        graph, output = build_transition_graph([10,12,8],"fade",.5)
        self.assertEqual(output,"[v2]")
        self.assertIn("offset=9.500",graph)
        self.assertIn("offset=21.000",graph)
    def test_all_presets(self):
        for name in TRANSITIONS: self.assertIn("xfade=transition="+name,build_transition_graph([5,6],name,.5)[0])
    def test_invalid(self):
        with self.assertRaises(ValueError): build_transition_graph([5,6],"bad",.5)
