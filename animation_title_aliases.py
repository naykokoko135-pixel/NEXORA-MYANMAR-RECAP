"""Conservative, explicitly curated title aliases for known animation works.

Aliases are discovery query variants, not proof of identity. Callers must still
match a returned provider record uniquely and enforce its media format.
"""
import re
import unicodedata

_ALIAS_GROUPS = (
    (
        "demon_slayer_series",
        (
            "Demon Slayer",
            "Demon Slayer: Kimetsu no Yaiba",
            "Kimetsu no Yaiba",
            "鬼滅の刃",
        ),
    ),
    (
        "demon_slayer_infinity_castle",
        (
            "Demon Slayer: Kimetsu no Yaiba – The Movie: Infinity Castle",
            "Demon Slayer: Kimetsu no Yaiba - The Movie: Infinity Castle",
            "Demon Slayer: Kimetsu no Yaiba Infinity Castle",
            "Kimetsu no Yaiba: Mugenjou-hen Movie 1 - Akaza Sairai",
            "劇場版「鬼滅の刃」無限城編 第一章 猗窩座再来",
        ),
    ),
)


def normalize_animation_title(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = re.sub(r"[^\\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def animation_title_variants(title):
    """Return requested spelling plus curated variants from its exact alias group."""
    requested = " ".join(str(title or "").split()).strip()
    if not requested:
        return []
    normalized = normalize_animation_title(requested)
    for _group_id, aliases in _ALIAS_GROUPS:
        if normalized in {normalize_animation_title(alias) for alias in aliases}:
            return list(dict.fromkeys([requested, *aliases]))
    return [requested]


def animation_title_match_names(title):
    """Normalized allowed title spellings; provider records still need unique IDs."""
    return {normalize_animation_title(value) for value in animation_title_variants(title)}
