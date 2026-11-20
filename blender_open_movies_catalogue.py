"""Small curated index of Blender Studio's official 3D Open Movies.

This is deliberately not a full 3D-animation database. 2D projects, hybrids,
and live-action/VFX titles are omitted from this 3D-only index.
"""
import re
import unicodedata

BLENDER_FILMS_URL = "https://studio.blender.org/films/"

_OPEN_MOVIES = (
    ("Elephants Dream", 2006, "https://studio.blender.org/projects/elephants-dream/"),
    ("Big Buck Bunny", 2008, "https://studio.blender.org/projects/big-buck-bunny/"),
    ("Sintel", 2010, "https://studio.blender.org/projects/sintel/"),
    ("Caminandes: Gran Dillama", 2013, BLENDER_FILMS_URL),
    ("Cosmos Laundromat: First Cycle", 2015, BLENDER_FILMS_URL),
    ("Glass Half", 2015, BLENDER_FILMS_URL),
    ("Caminandes: Llamigos", 2016, BLENDER_FILMS_URL),
    ("The Daily Dweebs", 2017, BLENDER_FILMS_URL),
    ("Spring", 2019, BLENDER_FILMS_URL),
    ("Coffee Run", 2020, BLENDER_FILMS_URL),
    ("Sprite Fright", 2021, BLENDER_FILMS_URL),
    ("Charge", 2022, BLENDER_FILMS_URL),
)


def _norm(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def fetch_blender_open_movie(title):
    """Match one curated 3D open movie; no fuzzy matching."""
    requested = " ".join(str(title or "").split()).strip()
    if not requested or len(requested) > 120:
        return {"found": False, "status": "Blender Open Movie ခေါင်းစဉ် မမှန်ကန်ပါ။"}
    matches = [item for item in _OPEN_MOVIES if _norm(item[0]) == _norm(requested)]
    if len(matches) != 1:
        return {
            "found": False,
            "status": "Blender Studio 3D Open Movies curated list တွင် exact match မတွေ့ပါ။",
        }
    name, year, source = matches[0]
    return {
        "found": True,
        "provider": "Blender Studio Open Movies (curated 3D subset)",
        "title": name,
        "year": year,
        "source": source,
        "catalogue": BLENDER_FILMS_URL,
        "notice": (
            "Blender Studio ရဲ့ 3D Open Movie discovery lead ဖြစ်သည်။ "
            "ဒီမှတ်တမ်းတစ်ခုတည်းက film footage/license အခြေအနေကို မအတည်ပြုပါ။"
        ),
    }
