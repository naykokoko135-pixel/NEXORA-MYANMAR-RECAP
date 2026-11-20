import blender_open_movies_catalogue as blender


def test_blender_open_movie_exact_match():
    result = blender.fetch_blender_open_movie("Big Buck Bunny")
    assert result["found"] is True
    assert result["year"] == 2008
    assert result["provider"] == "Blender Studio Open Movies (curated 3D subset)"


def test_blender_open_movie_is_not_fuzzy():
    result = blender.fetch_blender_open_movie("Big Buck")
    assert result["found"] is False


def test_known_2d_and_live_action_projects_are_not_in_3d_subset():
    assert blender.fetch_blender_open_movie("Hero")["found"] is False
    assert blender.fetch_blender_open_movie("Tears of Steel")["found"] is False
    assert blender.fetch_blender_open_movie("Wing It!")["found"] is False


def test_blender_catalogue_is_explicitly_limited():
    assert len(blender._OPEN_MOVIES) >= 10
    assert blender.BLENDER_FILMS_URL == "https://studio.blender.org/films/"
