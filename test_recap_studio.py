from recap_studio import build_original_recap_notes


def test_builds_original_notes_from_verified_metadata_and_trend_signals():
    report = {
        "title": "Example Film",
        "tmdb": {
            "found": True, "title": "Example Film", "year": "2020",
            "overview": "A person solves a mystery.",
            "provider_url": "https://www.themoviedb.org/movie/1",
            "countries": ["South Korea"],
        },
        "wikidata": {"found": False},
        "india_excluded": False,
    }
    examples = [{
        "channel": "Foreign Recap Channel", "title": "Example Film Movie Recap",
        "views": 100000, "published_at": "2026-01-01",
        "url": "https://youtube.com/watch?v=abc",
    }]
    notes = build_original_recap_notes(report, examples)
    assert "A person solves a mystery." in notes
    assert "views=100,000" in notes
    assert "never translate" in notes
    assert "footage" in notes.lower()


def test_rejects_indian_production():
    report = {
        "title": "Example", "tmdb": {"found": True},
        "wikidata": {"found": False}, "india_excluded": True,
    }
    try:
        build_original_recap_notes(report, [])
    except ValueError as exc:
        assert "အိန္ဒိယ" in str(exc)
    else:
        assert False


def test_requires_verified_catalogue_facts():
    report = {
        "title": "Unknown", "tmdb": {"found": False},
        "wikidata": {"found": False}, "india_excluded": False,
    }
    try:
        build_original_recap_notes(report, [])
    except ValueError as exc:
        assert "အတည်ပြု" in str(exc)
    else:
        assert False


def test_recapstudio_command_runs_research_then_original_script(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    import bot

    report = {
        "title": "Example Film",
        "tmdb": {
            "found": True, "title": "Example Film", "year": "2020",
            "overview": "A verified short catalogue overview.",
            "provider_url": "https://www.themoviedb.org/movie/1",
            "countries": ["South Korea"],
        },
        "wikidata": {"found": False},
        "india_excluded": False,
    }
    calls = []
    monkeypatch.setattr(bot, "research_movie_sources", lambda title: (calls.append(("research", title)) or report))
    monkeypatch.setattr(bot, "search_youtube_movie_recaps", lambda title, limit: (calls.append(("market", title, limit)) or []))
    monkeypatch.setattr(bot, "generate_burmese_recap_script", lambda title, notes, platform, duration: (calls.append(("script", title, platform, duration, "VERIFIED CATALOGUE FACTS" in notes)) or "မူရင်းစမ်းသပ် Script"))

    sent = []

    async def reply_text(message):
        sent.append(message)

    update = SimpleNamespace(message=SimpleNamespace(reply_text=reply_text))
    context = SimpleNamespace(args=["Example", "Film"], user_data={"platform": "youtube", "duration": "46-60"})
    asyncio.run(bot.recapstudio_cmd(update, context))

    assert calls[0] == ("research", "Example Film")
    assert calls[1] == ("market", "Example Film", 8)
    assert calls[2] == ("script", "Example Film", "youtube", "46-60", True)
    assert any("မူရင်းစမ်းသပ် Script" in message for message in sent)


def test_recapstudio_command_stops_on_indian_production(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    import bot

    report = {
        "title": "Excluded Film",
        "tmdb": {"found": True, "title": "Excluded Film", "countries": ["India"]},
        "wikidata": {"found": False},
        "india_excluded": True,
    }
    monkeypatch.setattr(bot, "research_movie_sources", lambda title: report)
    monkeypatch.setattr(bot, "search_youtube_movie_recaps", lambda title, limit: [])
    script_calls = []
    monkeypatch.setattr(bot, "generate_burmese_recap_script", lambda *args: script_calls.append(args) or "should not run")

    sent = []

    async def reply_text(message):
        sent.append(message)

    update = SimpleNamespace(message=SimpleNamespace(reply_text=reply_text))
    context = SimpleNamespace(args=["Excluded", "Film"], user_data={})
    asyncio.run(bot.recapstudio_cmd(update, context))

    assert not script_calls
    assert any("အိန္ဒိယ" in message for message in sent)


def test_missing_metadata_error_explains_each_provider_without_secrets():
    report = {
        "title": "Parasite",
        "tmdb": {
            "found": False,
            "status": "TMDB API Read Access Token မချိတ်ရသေးပါ။",
        },
        "wikidata": {
            "found": False,
            "status": "Wikidata ရင်းမြစ်ကို ယခုချိန်တွင် မရရှိနိုင်ပါ။",
        },
        "india_excluded": False,
    }
    try:
        build_original_recap_notes(report, [])
    except ValueError as exc:
        message = str(exc)
        assert "TMDB:" in message
        assert "Wikidata:" in message
        assert "TMDB_API_READ_ACCESS_TOKEN" in message
        assert "Token တန်ဖိုးကို Chat ထဲ မပို့ပါနှင့်" in message
    else:
        assert False, "Expected a safe provider diagnostic"


def test_gemini_grounded_metadata_can_build_original_recap_notes():
    report = {
        "title": "Example Film",
        "tmdb": {"found": False, "status": "TMDB မချိတ်ထားပါ။"},
        "wikidata": {"found": False, "status": "Wikidata မှတ်တမ်းမတွေ့ပါ။"},
        "gemini": {
            "found": True,
            "title": "Example Film",
            "year": "2020",
            "countries": ["South Korea"],
            "overview": "A verified synopsis from grounded sources.",
            "sources": [{"url": "https://studio.example/film"}],
        },
        "india_excluded": False,
    }
    notes = build_original_recap_notes(report, [])
    assert "Gemini grounded title: Example Film" in notes
    assert "South Korea" in notes
    assert "https://studio.example/film" in notes


def test_gemini_indian_coproduction_is_excluded_by_movie_research(monkeypatch):
    import tmdb_movie_research as movie_research
    monkeypatch.setattr(movie_research, "fetch_tmdb_movie", lambda title: {
        "found": False, "status": "TMDB token not configured"
    })
    monkeypatch.setattr(movie_research, "fetch_wikidata_metadata", lambda title: {
        "found": False, "status": "No record"
    })
    monkeypatch.setattr(movie_research, "fetch_gemini_movie_metadata", lambda title: {
        "found": True, "countries": ["South Korea", "India"], "year": "2020"
    })
    report = movie_research.research_movie_sources("Example Film")
    assert report["india_excluded"] is True
