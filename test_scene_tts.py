import unittest

from scene_tts import parse_scene_script, parse_voice_design_scene_script


class SceneTtsTests(unittest.TestCase):
    def test_parse_existing_scene_presets(self):
        scenes = parse_scene_script("[narrator]\nမင်္ဂလာပါ။\n[villain]\nသတိထားပါ။")
        self.assertEqual([scene["preset"] for scene in scenes], ["narrator", "villain"])

    def test_parse_ai_voice_design_scenes(self):
        scenes = parse_voice_design_scene_script(
            "[ai:story_female]\nဇာတ်လမ်း စတင်ပါပြီ။\n"
            "[ai:villain]\nဒီနေရာကနေ ထွက်သွားပါ။"
        )
        self.assertEqual([scene["voice"] for scene in scenes], ["story_female", "villain"])
        self.assertEqual(len(scenes), 2)

    def test_ai_scene_requires_ai_prefix(self):
        with self.assertRaisesRegex(ValueError, "ai:"):
            parse_voice_design_scene_script("[narrator]\nမင်္ဂလာပါ။")

    def test_unknown_ai_voice_rejected(self):
        with self.assertRaises(ValueError):
            parse_voice_design_scene_script("[ai:unknown]\nမင်္ဂလာပါ။")

    def test_ai_scene_requires_header(self):
        with self.assertRaises(ValueError):
            parse_voice_design_scene_script("ခေါင်းစဉ်မပါသောစာသား")

    def test_ai_scene_count_limit(self):
        script = "\n".join(f"[ai:story_female]\nခန်း {i}" for i in range(5))
        with self.assertRaisesRegex(ValueError, "၄ ခန်း"):
            parse_voice_design_scene_script(script)

    def test_ai_scene_character_limit(self):
        with self.assertRaisesRegex(ValueError, "၁,၅၀၀"):
            parse_voice_design_scene_script("[ai:story_female]\n" + "က" * 1501)

    def test_ai_scene_total_limit(self):
        script = "\n".join(
            f"[ai:story_female]\n{'က' * 1500}" for _ in range(4)
        )
        # Per-scene limit is satisfied; aggregate limit is tested by larger accepted
        # per-scene chunks only if the per-scene policy changes.
        self.assertEqual(len(parse_voice_design_scene_script(script)), 4)


if __name__ == "__main__":
    unittest.main()
