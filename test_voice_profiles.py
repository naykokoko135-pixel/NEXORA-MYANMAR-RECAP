import pytest
from voice_profiles import normalize_profile_name, store_voice_profile, delete_voice_profile, MAX_AUDIO_BYTES


def test_store_and_delete():
    profiles = {}
    store_voice_profile(profiles, "Hero", "take.mp3", b"audio")
    assert profiles["Hero"]["audio"] == b"audio"
    delete_voice_profile(profiles, "Hero")
    assert profiles == {}


@pytest.mark.parametrize("name", ["", "../bad", "a" * 25, "bad/name"])
def test_invalid_names(name):
    with pytest.raises(ValueError):
        normalize_profile_name(name)


def test_reject_invalid_audio():
    with pytest.raises(ValueError):
        store_voice_profile({}, "Hero", "x.exe", b"x")
    with pytest.raises(ValueError):
        store_voice_profile({}, "Hero", "x.mp3", b"x" * (MAX_AUDIO_BYTES + 1))


def test_profile_limit():
    profiles = {str(i): {"filename": "x.mp3", "audio": b"x"} for i in range(12)}
    with pytest.raises(ValueError):
        store_voice_profile(profiles, "extra", "x.mp3", b"x")


def test_accept_burmese_profile_name():
    assert normalize_profile_name("မေ") == "မေ"


def test_total_storage_budget():
    from voice_profiles import MAX_TOTAL_PROFILE_BYTES
    profiles = {}
    store_voice_profile(profiles, "one", "one.mp3", b"x" * (MAX_TOTAL_PROFILE_BYTES - 2))
    with pytest.raises(ValueError):
        store_voice_profile(profiles, "two", "two.mp3", b"xxx")
