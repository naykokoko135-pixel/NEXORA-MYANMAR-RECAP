import unittest
from unittest.mock import patch

import bcdb_cartoon_catalogue as bcdb


class BcdbCartoonCatalogueTests(unittest.TestCase):
    def test_parser_extracts_only_cartoon_records_and_periods(self):
        html = """
        <h2>Most viewed of all time</h2>
        <ol><li><a href="/cartoon/3-the-lion-king">The Lion King</a></li></ol>
        <h2>Most viewed this month November 2026</h2>
        <ol><li><a href="https://www.bcdb.com/cartoon/4-cinderella">Cinderella</a></li></ol>
        <a href="/search?q=lion">Search</a>
        """
        parser = bcdb._PopularPageParser()
        parser.feed(html)
        self.assertEqual(len(parser.items), 2)
        self.assertEqual(parser.items[0]["title"], "The Lion King")
        self.assertEqual(parser.items[0]["period"], "all_time")
        self.assertEqual(parser.items[1]["title"], "Cinderella")
        self.assertEqual(parser.items[1]["period"], "this_month")

    def test_exact_popular_title_match_and_year_suffix(self):
        with patch.object(bcdb, "_fetch_popular_catalogue", return_value=[
            {"id": "3", "title": "The Lion King", "url": "https://www.bcdb.com/cartoon/3-the-lion-king",
             "period": "all_time"},
        ]):
            result = bcdb.fetch_bcdb_popular_cartoon("The Lion King (1994)")
        self.assertTrue(result["found"])
        self.assertEqual(result["media_id"], "3")
        self.assertEqual(result["license"], "CC BY 4.0 for BCDB facts and compilation; artwork excluded")

    def test_does_not_fuzzy_match_or_claim_absence(self):
        with patch.object(bcdb, "_fetch_popular_catalogue", return_value=[
            {"id": "3", "title": "The Lion King", "url": "https://www.bcdb.com/cartoon/3-the-lion-king",
             "period": "all_time"},
        ]):
            result = bcdb.fetch_bcdb_popular_cartoon("Lion King")
        self.assertFalse(result["found"])
        self.assertIn("မတွေ့ပါ", result["status"])

    def test_fetch_uses_only_allowed_popular_url(self):
        self.assertEqual(bcdb.POPULAR_URL, "https://www.bcdb.com/most-popular")
        self.assertNotIn("/search", bcdb.POPULAR_URL)
        self.assertGreaterEqual(bcdb.CRAWL_DELAY_SECONDS, 5)


if __name__ == "__main__":
    unittest.main()
