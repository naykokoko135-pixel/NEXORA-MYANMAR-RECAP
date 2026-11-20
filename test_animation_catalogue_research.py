import unittest
from unittest.mock import patch

import animation_catalogue_research as catalogues


class AnimationCatalogueResearchTests(unittest.TestCase):
    def setUp(self):
        self._patch("fetch_bcdb_popular_cartoon", lambda _title: {"found": False, "status": "not mocked"})
        self._patch("fetch_blender_open_movie", lambda _title: {"found": False, "status": "not mocked"})

    def _patch(self, name, value):
        mocked = patch.object(catalogues, name, value)
        mocked.start()
        self.addCleanup(mocked.stop)

    def test_bangumi_requires_unique_exact_animation_title(self):
        self._patch("_bangumi_search", lambda _title: {
            "data": [
                {"id": 11, "type": 2, "name": "Example Donghua", "name_cn": "示例动画",
                 "summary": "An original animation.", "nsfw": False},
                {"id": 12, "type": 2, "name": "Example Donghua", "name_cn": "示例动画",
                 "summary": "Duplicate entry.", "nsfw": False},
                {"id": 13, "type": 1, "name": "Example Donghua", "name_cn": "示例动画",
                 "nsfw": False},
            ]
        })
        result = catalogues.fetch_bangumi_animation("Example Donghua")
        self.assertFalse(result["found"])
        self.assertIn("တစ်ခုတည်း", result["status"])

    def test_bangumi_returns_exact_non_nsfw_animation_record(self):
        self._patch("_bangumi_search", lambda _title: {
            "data": [
                {"id": 11, "type": 2, "name": "Example Donghua", "name_cn": "Example Donghua",
                 "summary": "An original animated story.", "date": "2025-01-01",
                 "score": 8.1, "rank": 20, "nsfw": False},
                {"id": 12, "type": 2, "name": "Example Donghua Special", "name_cn": "",
                 "nsfw": False},
            ]
        })
        result = catalogues.fetch_bangumi_animation("Example Donghua")
        self.assertTrue(result["found"])
        self.assertEqual(result["media_id"], 11)
        self.assertEqual(result["provider_url"], "https://bgm.tv/subject/11")

    def test_bangumi_rejects_nsfw_and_non_animation_subjects(self):
        self._patch("_bangumi_search", lambda _title: {
            "data": [
                {"id": 11, "type": 2, "name": "Example", "name_cn": "", "nsfw": True},
                {"id": 12, "type": 4, "name": "Example", "name_cn": "", "nsfw": False},
            ]
        })
        result = catalogues.fetch_bangumi_animation("Example")
        self.assertFalse(result["found"])

    def test_donghua_requires_bangumi_and_wikidata_china_origin(self):
        self._patch("fetch_bangumi_animation", lambda _title: {
            "found": True, "title": "Example", "provider_url": "https://bgm.tv/subject/11",
        })
        self._patch("_safe_wikidata", lambda _title: {
            "found": True, "title": "Example", "countries": ["China"],
            "description": "Chinese animated television series", "source": "https://www.wikidata.org/wiki/Q11",
        })
        result = catalogues.research_animation_catalogues("Example")
        self.assertTrue(result["donghua"]["found"])

    def test_bangumi_alone_does_not_prove_donghua_origin(self):
        self._patch("fetch_bangumi_animation", lambda _title: {"found": True, "title": "Example"})
        self._patch("_safe_wikidata", lambda _title: {
            "found": True, "title": "Example", "countries": ["Japan"],
            "description": "Japanese animated television series",
        })
        result = catalogues.research_animation_catalogues("Example")
        self.assertFalse(result["donghua"]["found"])
        self.assertIn("China", result["donghua"]["status"])

    def test_cartoon_and_3d_classifications_require_explicit_wikidata_description(self):
        self._patch("fetch_bangumi_animation", lambda _title: {"found": False, "status": "not found"})
        self._patch("_safe_wikidata", lambda _title: {
            "found": True, "title": "Example", "description": "American computer-animated film",
            "countries": ["United States"], "year": "2024", "source": "https://www.wikidata.org/wiki/Q1",
        })
        result = catalogues.research_animation_catalogues("Example")
        self.assertTrue(result["cartoon"]["found"])
        self.assertTrue(result["3d_animation"]["found"])

    def test_unknown_3d_technique_is_not_inferred(self):
        self._patch("fetch_bangumi_animation", lambda _title: {"found": False})
        self._patch("_safe_wikidata", lambda _title: {
            "found": True, "title": "Example", "description": "Animated feature film",
            "countries": ["United States"],
        })
        result = catalogues.research_animation_catalogues("Example")
        self.assertTrue(result["cartoon"]["found"])
        self.assertFalse(result["3d_animation"]["found"])

    def test_animation_catalogue_report_has_all_three_tracks(self):
        report = {
            "title": "Example",
            "donghua": {"found": False, "status": "No Donghua match"},
            "cartoon": {"found": False, "status": "No cartoon match"},
            "3d_animation": {"found": False, "status": "No 3D match"},
        }
        output = catalogues.format_animation_catalogue_report(report)
        self.assertIn("DONGHUA", output)
        self.assertIn("CARTOON", output)
        self.assertIn("3D ANIMATION", output)
        self.assertNotIn("\\n", output)

    def test_verified_indian_origin_is_excluded_from_cartoon_and_3d_tracks(self):
        self._patch("fetch_bangumi_animation", lambda _title: {"found": False})
        self._patch("_safe_wikidata", lambda _title: {
            "found": True, "title": "Example", "description": "Indian computer-animated film",
            "countries": ["India"],
        })
        result = catalogues.research_animation_catalogues("Example")
        self.assertFalse(result["cartoon"]["found"])
        self.assertTrue(result["cartoon"]["india_excluded"])
        self.assertFalse(result["3d_animation"]["found"])
        self.assertTrue(result["3d_animation"]["india_excluded"])

    def test_bcdb_cartoon_match_requires_non_japanese_non_chinese_origin(self):
        self._patch("fetch_bcdb_popular_cartoon", lambda _title: {
            "found": True, "title": "Example Cartoon", "provider_url": "https://www.bcdb.com/cartoon/3-example",
            "catalogue_url": "https://www.bcdb.com/most-popular",
        })
        self._patch("_safe_wikidata", lambda _title: {
            "found": True, "title": "Example Cartoon", "countries": ["United States"],
            "description": "American animated television series", "year": "2024",
            "source": "https://www.wikidata.org/wiki/Q11",
        })
        result = catalogues.research_animation_catalogues("Example Cartoon")
        self.assertTrue(result["cartoon"]["found"])
        self.assertEqual(result["cartoon"]["provider"], "The Big Cartoon DataBase (BCDB)")
        self.assertTrue(result["cartoon"]["origin_verified"])

    def test_bcdb_japanese_title_is_not_mislabelled_cartoon(self):
        self._patch("fetch_bcdb_popular_cartoon", lambda _title: {
            "found": True, "title": "Example", "provider_url": "https://www.bcdb.com/cartoon/3-example",
        })
        self._patch("_safe_wikidata", lambda _title: {
            "found": True, "title": "Example", "countries": ["Japan"],
            "description": "Japanese animated film",
        })
        result = catalogues.research_animation_catalogues("Example")
        self.assertFalse(result["cartoon"]["found"])

    def test_blender_open_movie_is_a_3d_catalogue_lead(self):
        self._patch("fetch_blender_open_movie", lambda _title: {
            "found": True, "provider": "Blender Studio Open Movies (curated 3D subset)",
            "title": "Big Buck Bunny", "year": 2008,
            "source": "https://studio.blender.org/projects/big-buck-bunny/",
            "catalogue": "https://studio.blender.org/films/",
        })
        self._patch("_safe_wikidata", lambda _title: {
            "found": True, "title": "Big Buck Bunny", "countries": ["Netherlands"],
            "description": "Computer animated short film",
        })
        result = catalogues.research_animation_catalogues("Big Buck Bunny")
        self.assertTrue(result["3d_animation"]["found"])
        self.assertEqual(
            result["3d_animation"]["provider"],
            "Blender Studio Open Movies (curated 3D subset)",
        )


if __name__ == "__main__":
    unittest.main()
