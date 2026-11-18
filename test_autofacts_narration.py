import pytest

from autofacts_narration import generate_burmese_facts_narration


def test_generates_only_metadata_facts_and_source_disclaimer():
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
    assert "ဥပမာရုပ်ရှင်" in script
    assert "2024" in script
    assert "ဂျပန်" in script
    assert "သိပ္ပံစိတ်ကူးယဉ်" in script
    assert "ဇာတ်ကွက်အသေးစိတ်" in script


def test_rejects_indian_titles():
    with pytest.raises(ValueError, match="အိန္ဒိယ"):
        generate_burmese_facts_narration({
            "found": True,
            "title": "Example",
            "countries": ["India"],
            "year": "2020",
        })


def test_rejects_metadata_without_verified_fact_fields():
    with pytest.raises(ValueError, match="metadata"):
        generate_burmese_facts_narration({
            "found": True,
            "title": "Example",
            "countries": [],
            "genres_my": [],
            "directors_my": [],
            "year": None,
        })


def test_rejects_missing_exact_match():
    with pytest.raises(ValueError, match="Wikidata"):
        generate_burmese_facts_narration({"found": False})
