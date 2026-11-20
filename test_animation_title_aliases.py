import animation_title_aliases as aliases
import kitsu_anime_research as kitsu
import anilist_synopsis
import tvmaze_synopsis


def test_demon_slayer_short_name_has_curated_series_aliases():
    variants = aliases.animation_title_variants("Demon Slayer")
    assert "Demon Slayer: Kimetsu no Yaiba" in variants
    assert "Kimetsu no Yaiba" in variants
    assert "Demon Slayer: Kimetsu no Yaiba – The Movie: Infinity Castle" not in variants


def test_infinity_castle_aliases_are_separate_from_tv_series():
    variants = aliases.animation_title_variants(
        "Demon Slayer: Kimetsu no Yaiba – The Movie: Infinity Castle"
    )
    assert "Kimetsu no Yaiba: Mugenjou-hen Movie 1 - Akaza Sairai" in variants
    assert "Demon Slayer" not in variants


def test_kitsu_episode_lookup_uses_short_series_alias(monkeypatch):
    record = {
        "id": "series-1",
        "attributes": {
            "canonicalTitle": "Kimetsu no Yaiba",
            "titles": {"en": "Demon Slayer: Kimetsu no Yaiba"},
            "slug": "kimetsu-no-yaiba",
            "ageRating": "PG",
            "subtype": "TV",
        },
        "relationships": {"episodes": {"data": [{"id": "ep-1", "type": "episodes"}]}},
    }
    payload = {
        "data": [record],
        "included": [{
            "id": "ep-1", "type": "episodes",
            "attributes": {
                "seasonNumber": 1, "number": 1, "canonicalTitle": "Cruelty",
                "synopsis": "Tanjiro faces a tragic event and begins his journey. " * 2,
            },
        }],
    }
    monkeypatch.setattr(kitsu, "_get_json", lambda _url: payload)
    result = kitsu.fetch_kitsu_episode_summaries("Demon Slayer")
    assert result["found"] is True
    assert result["episodes"][0]["number"] == 1


def test_anilist_infinity_castle_alias_matches_unique_movie(monkeypatch):
    movie = {
        "id": 178788,
        "title": {
            "english": "Demon Slayer: Kimetsu no Yaiba Infinity Castle",
            "romaji": "Kimetsu no Yaiba: Mugenjou-hen Movie 1 - Akaza Sairai",
            "native": "劇場版「鬼滅の刃」無限城編 第一章 猗窩座再来",
        },
        "synonyms": [],
        "description": "A detailed movie synopsis. " * 12,
        "siteUrl": "https://anilist.co/anime/178788",
        "format": "MOVIE",
        "episodes": 1,
        "seasonYear": 2025,
        "countryOfOrigin": "JP",
        "isAdult": False,
    }
    monkeypatch.setattr(anilist_synopsis, "_graphql", lambda *_args: {
        "data": {"Page": {"media": [movie]}}
    })
    result = anilist_synopsis.fetch_anilist_synopsis(
        "Demon Slayer: Kimetsu no Yaiba – The Movie: Infinity Castle"
    )
    assert result["found"] is True
    assert result["media_id"] == 178788
    assert result["format"] == "MOVIE"


def test_tvmaze_short_name_resolves_only_unique_series(monkeypatch):
    show = {
        "id": 101,
        "name": "Demon Slayer: Kimetsu no Yaiba",
        "genres": ["Animation", "Action"],
        "network": {"country": {"name": "Japan"}},
        "url": "https://www.tvmaze.com/shows/101/demon-slayer",
    }
    episode = {
        "season": 1, "number": 1, "name": "Cruelty",
        "summary": "<p>" + ("Tanjiro begins his journey. " * 5) + "</p>",
        "url": "https://www.tvmaze.com/episodes/101/1",
    }
    def fake_get(url):
        if "/search/shows?" in url:
            return [{"show": show}]
        return [episode]
    monkeypatch.setattr(tvmaze_synopsis, "_get_json", fake_get)
    result = tvmaze_synopsis.fetch_tvmaze_episode_summaries("Demon Slayer")
    assert result["found"] is True
    assert result["title"] == show["name"]
    assert result["episodes"][0]["number"] == 1


def test_kitsu_episode_lookup_rejects_movie_format(monkeypatch):
    movie = {
        "id": "movie-1",
        "attributes": {
            "canonicalTitle": "Demon Slayer: Kimetsu no Yaiba Infinity Castle",
            "titles": {"en": "Demon Slayer: Kimetsu no Yaiba Infinity Castle"},
            "slug": "infinity-castle",
            "ageRating": "PG",
            "subtype": "movie",
        },
        "relationships": {"episodes": {"data": []}},
    }
    monkeypatch.setattr(kitsu, "_get_json", lambda _url: {"data": [movie], "included": []})
    result = kitsu.fetch_kitsu_episode_summaries(
        "Demon Slayer: Kimetsu no Yaiba – The Movie: Infinity Castle"
    )
    assert result["found"] is False
    assert "TV/Animation Series" in result["status"]
