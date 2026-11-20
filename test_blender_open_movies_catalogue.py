import unittest

import blender_open_movies_catalogue as blender


class BlenderOpenMoviesCatalogueTests(unittest.TestCase):
    def test_exact_match(self):
        result = blender.fetch_blender_open_movie("Big Buck Bunny")
        self.assertTrue(result["found"])
        self.assertEqual(result["year"], 2008)
        self.assertEqual(result["provider"], "Blender Studio Open Movies (curated 3D subset)")

    def test_not_fuzzy(self):
        result = blender.fetch_blender_open_movie("Big Buck")
        self.assertFalse(result["found"])

    def test_known_2d_and_live_action_projects_are_not_in_3d_subset(self):
        self.assertFalse(blender.fetch_blender_open_movie("Hero")["found"])
        self.assertFalse(blender.fetch_blender_open_movie("Tears of Steel")["found"])
        self.assertFalse(blender.fetch_blender_open_movie("Wing It!")["found"])

    def test_catalogue_is_explicitly_limited(self):
        self.assertGreaterEqual(len(blender._OPEN_MOVIES), 10)
        self.assertEqual(blender.BLENDER_FILMS_URL, "https://studio.blender.org/films/")


if __name__ == "__main__":
    unittest.main()
