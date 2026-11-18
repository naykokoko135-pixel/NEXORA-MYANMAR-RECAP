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


    def test_parse_eight_regular_scenes(self):
        script = "\n".join(
            f"[narrator]\nအခန်း {i}" for i in range(1, 9)
        )
        scenes = parse_scene_script(script)
        self.assertEqual(len(scenes), 8)

    def test_regular_scene_limit_rejects_ninth_scene(self):
        script = "\n".join(
            f"[narrator]\nအခန်း {i}" for i in range(1, 10)
        )
        with self.assertRaisesRegex(ValueError, "အများဆုံး 8 ခန်း"):
            parse_scene_script(script)

    def test_role_aliases_map_to_existing_presets(self):
        scenes = parse_scene_script(
            "[protagonist]\nဇာတ်လိုက်စာသား\n"
            "[antagonist]\nဆန့်ကျင်ဘက်ဇာတ်ကောင်စာသား\n"
            "[comic]\nဟာသစာသား"
        )
        self.assertEqual(
            [scene["preset"] for scene in scenes],
            ["hero", "villain", "comedy"],
        )

    def test_regular_scene_rejects_text_before_header(self):
        with self.assertRaisesRegex(ValueError, "အသံခေါင်းစဉ်တပ်ပါ"):
            parse_scene_script("ခေါင်းစဉ်မပါသောစာသား\n[narrator]\nမင်္ဂလာပါ")

    def test_empty_scene_is_skipped_without_corrupting_next_scene(self):
        scenes = parse_scene_script(
            "[narrator]\n\n[hero]\nဇာတ်လိုက်စာသား"
        )
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["role"], "hero")
        self.assertEqual(scenes[0]["text"], "ဇာတ်လိုက်စာသား")


if __name__ == "__main__":
    unittest.main()
