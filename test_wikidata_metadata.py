import json
import unittest
from io import BytesIO
from urllib.error import URLError
from unittest.mock import patch

from wikidata_metadata import (fetch_wikidata_metadata, format_wikidata_metadata,
                               format_wikidata_episode_guide)


class Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def claim(entity_id=None, time_value=None, quantity_value=None, rank="normal"):
    if entity_id:
        value = {"id": entity_id}
    elif time_value:
        value = {"time": time_value}
    else:
        value = {"amount": str(quantity_value), "unit": "1"}
    return {"rank": rank, "mainsnak": {"datavalue": {"value": value}}}


class WikidataMetadataTests(unittest.TestCase):
    @patch("wikidata_metadata.urlopen")
    def test_exact_title_returns_country_year_director_genre_and_language(self, mock_urlopen):
        search = {"search": [{
            "id": "Q123", "label": "Train to Busan",
            "description": "2016 South Korean film",
        }]}
        entity = {"entities": {"Q123": {"claims": {
            "P495": [claim("Q884")],
            "P577": [claim(time_value="+2016-07-20T00:00:00Z")],
            "P57": [claim("Q555")],
            "P136": [claim("Q11424")],
            "P364": [claim("Q9176")],
        }}}}
        labels = {"entities": {
            "Q884": {"labels": {"en": {"value": "South Korea"}}},
            "Q555": {"labels": {"en": {"value": "Yeon Sang-ho"}}},
            "Q11424": {"labels": {"en": {"value": "film"}}},
            "Q9176": {"labels": {"en": {"value": "Korean"}}},
        }}
        mock_urlopen.side_effect = [
            Response(json.dumps(search).encode()),
            Response(json.dumps(entity).encode()),
            Response(json.dumps(labels).encode()),
        ]
        result = fetch_wikidata_metadata("Train to Busan")
        self.assertTrue(result["found"])
        self.assertEqual(result["countries"], ["South Korea"])
        self.assertEqual(result["year"], "2016")
        self.assertEqual(result["directors"], ["Yeon Sang-ho"])
        self.assertEqual(result["genres"], ["film"])
        self.assertEqual(result["languages"], ["Korean"])
        self.assertIn("wikidata.org/wiki/Q123", format_wikidata_metadata(result))

    @patch("wikidata_metadata.urlopen")
    def test_year_suffix_retries_base_title_and_keeps_exact_match(self, mock_urlopen):
        search_with_year = {"search": []}
        search_without_year = {"search": [{
            "id": "Q850159", "label": "The General",
            "description": "1926 American silent comedy film",
        }]}
        entity = {"entities": {"Q850159": {"claims": {"P495": [claim("Q30")]}}}}
        labels = {"entities": {"Q30": {"labels": {"en": {"value": "United States"}}}}}
        mock_urlopen.side_effect = [
            Response(json.dumps(search_with_year).encode()),
            Response(json.dumps(search_without_year).encode()),
            Response(json.dumps(entity).encode()),
            Response(json.dumps(labels).encode()),
        ]
        result = fetch_wikidata_metadata("The General (1926)")
        self.assertTrue(result["found"])
        self.assertEqual(result["entity_id"], "Q850159")
        self.assertEqual(result["countries"], ["United States"])
        self.assertEqual(mock_urlopen.call_count, 4)

    @patch("wikidata_metadata.urlopen")
    def test_does_not_accept_unrelated_title_match(self, mock_urlopen):
        mock_urlopen.return_value = Response(json.dumps({
            "search": [{"id": "Q99", "label": "Train", "description": "rail vehicle"}]
        }).encode())
        result = fetch_wikidata_metadata("Train to Busan")
        self.assertFalse(result["found"])
        self.assertIn("အမည်တိတိကျကျ", result["status"])
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("wikidata_metadata.urlopen")
    def test_api_failure_is_reported_without_crashing(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("offline")
        result = fetch_wikidata_metadata("Parasite")
        self.assertFalse(result["found"])
        self.assertIn("မခန့်မှန်းထားပါ", format_wikidata_metadata(result))

    def test_missing_metadata_fields_are_explicit(self):
        result = format_wikidata_metadata({
            "found": True, "title": "Example", "description": "",
            "countries": [], "year": None, "directors": [],
            "genres": [], "languages": [], "source": "https://www.wikidata.org/wiki/Q1",
            "status": "Needs verification",
        })
        self.assertIn("ထွက်ရှိသည့်နှစ်: မရရှိပါ", result)
        self.assertIn("ဒါရိုက်တာ: မရရှိပါ", result)
        self.assertIn("ထပ်မံတိုက်စစ်ပါ", result)


    @patch("wikidata_metadata.urlopen")
    def test_episode_and_season_counts_are_extracted_from_wikidata(self, mock_urlopen):
        search = {"search": [{
            "id": "Q321", "label": "Example Series",
            "description": "animated television series",
        }]}
        entity = {"entities": {"Q321": {"claims": {
            "P1113": [claim(quantity_value="+24")],
            "P2437": [claim(quantity_value="+2")],
        }}}}
        mock_urlopen.side_effect = [
            Response(json.dumps(search).encode()),
            Response(json.dumps(entity).encode()),
        ]
        result = fetch_wikidata_metadata("Example Series")
        self.assertTrue(result["found"])
        self.assertEqual(result["episode_count"], 24)
        self.assertEqual(result["season_count"], 2)
        formatted = format_wikidata_episode_guide(result)
        self.assertIn("စုစုပေါင်း Episode အရေအတွက်: 24", formatted)
        self.assertIn("Season အရေအတွက်: 2", formatted)
        self.assertIn("wikidata.org/wiki/Q321", formatted)
        self.assertIn("Season တစ်ခုချင်းစီ", formatted)

    @patch("wikidata_metadata.urlopen")
    def test_ambiguous_episode_counts_are_not_guessed(self, mock_urlopen):
        search = {"search": [{"id": "Q322", "label": "Example Series"}]}
        entity = {"entities": {"Q322": {"claims": {
            "P1113": [
                claim(quantity_value="+24"),
                claim(quantity_value="+26"),
            ],
        }}}}
        mock_urlopen.side_effect = [
            Response(json.dumps(search).encode()),
            Response(json.dumps(entity).encode()),
        ]
        result = fetch_wikidata_metadata("Example Series")
        self.assertIsNone(result["episode_count"])
        self.assertIn("မရရှိပါ", format_wikidata_episode_guide(result))

    def test_episode_fallback_does_not_invent_missing_counts(self):
        formatted = format_wikidata_episode_guide({
            "found": True, "title": "Example Series",
            "episode_count": None, "season_count": None,
            "source": "https://www.wikidata.org/wiki/Q1",
        })
        self.assertIn("မရရှိပါ", formatted)
        self.assertIn("မခန့်မှန်းထားပါ", formatted)


    @patch("wikidata_metadata.urlopen")
    def test_extracts_burmese_labels_for_auto_narration(self, mock_urlopen):
        search = {"search": [{
            "id": "Q777", "label": "Example Animation",
            "description": "animated film",
        }]}
        entity = {"entities": {"Q777": {
            "labels": {
                "en": {"value": "Example Animation"},
                "my": {"value": "ဥပမာ အန်နီမေးရှင်း"},
            },
            "descriptions": {"my": {"value": "ကာတွန်းရုပ်ရှင်"}},
            "claims": {
                "P136": [claim("Q888")],
                "P495": [claim("Q999")],
            },
        }}}
        labels = {"entities": {
            "Q888": {"labels": {
                "en": {"value": "animation"},
                "my": {"value": "အန်နီမေးရှင်း"},
            }},
            "Q999": {"labels": {
                "en": {"value": "Japan"},
                "my": {"value": "ဂျပန်"},
            }},
        }}
        mock_urlopen.side_effect = [
            Response(json.dumps(search).encode()),
            Response(json.dumps(entity).encode()),
            Response(json.dumps(labels).encode()),
        ]
        result = fetch_wikidata_metadata("Example Animation")
        self.assertTrue(result["found"])
        self.assertEqual(result["title_my"], "ဥပမာ အန်နီမေးရှင်း")
        self.assertEqual(result["description_my"], "ကာတွန်းရုပ်ရှင်")
        self.assertEqual(result["genres_my"], ["အန်နီမေးရှင်း"])
        self.assertEqual(result["countries_my"], ["ဂျပန်"])


    @patch("wikidata_metadata.urlopen")
    def test_returns_exact_burmese_wikipedia_sitelink(self, mock_urlopen):
        search = {"search": [{"id": "Q654", "label": "Example Film"}]}
        entity = {"entities": {"Q654": {
            "claims": {},
            "sitelinks": {"mywiki": {"title": "ဥပမာ ရုပ်ရှင်"}, "enwiki": {"title": "Example Film"}},
        }}}
        mock_urlopen.side_effect = [
            Response(json.dumps(search).encode()),
            Response(json.dumps(entity).encode()),
        ]
        result = fetch_wikidata_metadata("Example Film")
        self.assertTrue(result["found"])
        self.assertEqual(result["mywiki_title"], "ဥပမာ ရုပ်ရှင်")
        self.assertIn("my.wikipedia.org/wiki/", result["mywiki_source"])
        self.assertEqual(result["enwiki_title"], "Example Film")
        self.assertIn("en.wikipedia.org/wiki/Example_Film", result["enwiki_source"])




    @patch("wikidata_metadata.urlopen")
    def test_exact_alias_match_is_accepted(self, mock_urlopen):
        search = {"search": [{
            "id": "Q900", "label": "Sousou no Frieren",
            "description": "Japanese animated television series",
            "match": {"type": "alias", "language": "en", "text": "Frieren: Beyond Journey's End"},
        }]}
        entity = {"entities": {"Q900": {"claims": {"P495": [claim("Q884")]}}}}
        labels = {"entities": {"Q884": {"labels": {"en": {"value": "Japan"}}}}}
        mock_urlopen.side_effect = [
            Response(json.dumps(search).encode()),
            Response(json.dumps(entity).encode()),
            Response(json.dumps(labels).encode()),
        ]
        result = fetch_wikidata_metadata("Frieren: Beyond Journey's End")
        self.assertTrue(result["found"])
        self.assertEqual(result["entity_id"], "Q900")
        self.assertEqual(result["countries"], ["Japan"])

    @patch("wikidata_metadata.urlopen")
    def test_ambiguous_exact_alias_matches_are_rejected(self, mock_urlopen):
        search = {"search": [
            {"id": "Q901", "label": "Sousou no Frieren",
             "match": {"type": "alias", "text": "Frieren: Beyond Journey's End"}},
            {"id": "Q902", "label": "Frieren (TV series)",
             "match": {"type": "alias", "text": "Frieren: Beyond Journey's End"}},
        ]}
        mock_urlopen.return_value = Response(json.dumps(search).encode())
        result = fetch_wikidata_metadata("Frieren: Beyond Journey's End")
        self.assertFalse(result["found"])
        self.assertIn("အများအပြား", result["status"])
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("wikidata_metadata.urlopen")
    def test_punctuation_normalization_accepts_exact_equivalent(self, mock_urlopen):
        search = {"search": [{
            "id": "Q903", "label": "Frieren Beyond Journey's End",
            "match": {"type": "label", "text": "Frieren Beyond Journey's End"},
        }]}
        entity = {"entities": {"Q903": {"claims": {"P495": [claim("Q884")]}}}}
        labels = {"entities": {"Q884": {"labels": {"en": {"value": "Japan"}}}}}
        mock_urlopen.side_effect = [
            Response(json.dumps(search).encode()),
            Response(json.dumps(entity).encode()),
            Response(json.dumps(labels).encode()),
        ]
        result = fetch_wikidata_metadata("Frieren: Beyond Journey's End")
        self.assertTrue(result["found"])



    @patch("wikidata_metadata.urlopen")
    def test_exact_alias_prefers_unique_anime_series_over_manga_and_franchise(self, mock_urlopen):
        search = {"search": [
            {"id": "Q115792176", "label": "Frieren",
             "description": "Japanese anime television series",
             "match": {"type": "alias", "text": "Frieren: Beyond Journey's End"}},
            {"id": "Q98642652", "label": "Frieren",
             "description": "Japanese manga series",
             "match": {"type": "alias", "text": "Frieren: Beyond Journey's End"}},
            {"id": "Q120087412", "label": "Frieren",
             "description": "Japanese media franchise",
             "match": {"type": "alias", "text": "Frieren: Beyond Journey's End"}},
        ]}
        entity = {"entities": {"Q115792176": {"claims": {"P495": [claim("Q884")]}}}}
        labels = {"entities": {"Q884": {"labels": {"en": {"value": "Japan"}}}}}
        mock_urlopen.side_effect = [
            Response(json.dumps(search).encode()),
            Response(json.dumps(entity).encode()),
            Response(json.dumps(labels).encode()),
        ]
        result = fetch_wikidata_metadata("Frieren: Beyond Journey's End")
        self.assertTrue(result["found"])
        self.assertEqual(result["entity_id"], "Q115792176")
        self.assertEqual(result["countries"], ["Japan"])

    @patch("wikidata_metadata.urlopen")
    def test_multiple_primary_screen_work_matches_remain_ambiguous(self, mock_urlopen):
        search = {"search": [
            {"id": "Q901", "label": "Example",
             "description": "Japanese anime television series",
             "match": {"type": "alias", "text": "Example"}},
            {"id": "Q902", "label": "Example",
             "description": "Japanese animated film",
             "match": {"type": "alias", "text": "Example"}},
        ]}
        mock_urlopen.return_value = Response(json.dumps(search).encode())
        result = fetch_wikidata_metadata("Example")
        self.assertFalse(result["found"])
        self.assertIn("candidates", result)
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(mock_urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
