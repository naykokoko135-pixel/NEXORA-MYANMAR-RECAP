import unittest

from autofacts_narration import generate_burmese_facts_narration


class AutofactsNarrationTests(unittest.TestCase):
    def test_generates_only_metadata_facts_and_source_disclaimer(self):
        script = generate_burmese_facts_narration({
            "found": True,
            "title": "Example Film",
            "title_my": "ဥပမာရုပ်ရှင်",
            "year": "2024",
            "countries": ["Japan"],
            "countries_my": ["ဂျပန်"],
            "genres_my": ["သိပ္ပံစိတ်ကူးယဉ်"],
            "directors_my": ["ဒါရိုက်တာအမည်"],
            "languages_my": ["ဂျပန်ဘာသာ"],
        })
        self.assertIn("ဥပမာရုပ်ရှင်", script)
        self.assertIn("2024", script)
        self.assertIn("ဂျပန်", script)
        self.assertIn("သိပ္ပံစိတ်ကူးယဉ်", script)
        self.assertIn("ဇာတ်ကွက်အသေးစိတ်", script)

    def test_rejects_indian_titles(self):
        with self.assertRaisesRegex(ValueError, "အိန္ဒိယ"):
            generate_burmese_facts_narration({
                "found": True,
                "title": "Example",
                "countries": ["India"],
                "year": "2020",
            })

    def test_rejects_metadata_without_verified_fact_fields(self):
        with self.assertRaisesRegex(ValueError, "metadata"):
            generate_burmese_facts_narration({
                "found": True,
                "title": "Example",
                "countries": [],
                "genres_my": [],
                "directors_my": [],
                "year": None,
            })

    def test_rejects_missing_exact_match(self):
        with self.assertRaisesRegex(ValueError, "Wikidata"):
            generate_burmese_facts_narration({"found": False})


if __name__ == "__main__":
    unittest.main()
