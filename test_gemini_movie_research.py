import json

import gemini_movie_research as research


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return json.dumps(self.payload).encode("utf-8")


def test_gemini_movie_metadata_requires_grounded_sources_and_exact_identity(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response = {
        "candidates": [{
            "content": {"parts": [{
                "text": json.dumps({
                    "title": "Parasite",
                    "media_type": "feature film",
                    "release_year": "2019",
                    "production_countries": ["South Korea"],
                    "original_language": "Korean",
                    "directors": ["Bong Joon-ho"],
                    "genres": ["Thriller"],
                    "overview": "A poor family schemes to become employed by a wealthy family.",
                    "identity_match": True,
                    "uncertainty": "",
                })
            }]},
            "groundingMetadata": {"groundingChunks": [
                {"web": {"title": "Official Film Page", "uri": "https://www.neonrated.com/film/parasite"}},
                {"web": {"title": "Festival Catalogue", "uri": "https://www.festival-cannes.com/en/f/parasite/"}},
            ]},
        }]
    }
    monkeypatch.setattr(research, "urlopen", lambda *args, **kwargs: FakeResponse(response))
    result = research.fetch_gemini_movie_metadata("Parasite")
    assert result["found"] is True
    assert result["year"] == "2019"
    assert result["countries"] == ["South Korea"]
    assert len(result["sources"]) == 2


def test_gemini_movie_metadata_fails_closed_without_two_source_domains(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response = {
        "candidates": [{
            "content": {"parts": [{"text": "{}"}]},
            "groundingMetadata": {"groundingChunks": [
                {"web": {"title": "One", "uri": "https://example.com/a"}},
                {"web": {"title": "Same domain", "uri": "https://www.example.com/b"}},
            ]},
        }]
    }
    monkeypatch.setattr(research, "urlopen", lambda *args, **kwargs: FakeResponse(response))
    result = research.fetch_gemini_movie_metadata("Parasite")
    assert result["found"] is False
    assert "domain" in result["status"]


def test_gemini_movie_metadata_requires_existing_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = research.fetch_gemini_movie_metadata("Parasite")
    assert result["found"] is False
    assert "GEMINI_API_KEY" in result["status"]
