"""
UNESCO-aligned, Balkan region-aware heritage taxonomy.
Subtype is strictly controlled per heritage_type; form is physical shape only.
"""

from __future__ import annotations

UNESCO_CLASSES: tuple[str, ...] = ("monument", "group_of_buildings", "site")

HERITAGE_TYPES: tuple[str, ...] = (
    "funerary",
    "memorial",
    "religious",
    "architectural",
    "archaeological",
    "industrial",
    "cultural_landscape",
    "military",
)

# Physical shape only (stećak / memorial morphology)
FORM_OPTIONS: tuple[str, ...] = (
    "slab",
    "chest",
    "gabled",
    "pillar",
    "stele",
    "obelisk",
    "cross_form",
)

STYLE_OPTIONS: tuple[str, ...] = (
    "medieval",
    "ottoman",
    "modernist",
    "socialist_modernism",
    "contemporary",
)

SUBTYPES_BY_HERITAGE: dict[str, tuple[str, ...]] = {
    "funerary": (
        "stecak",
        "tombstone",
        "necropolis",
        "mausoleum",
        "sarcophagus",
        "grave_marker",
    ),
    "memorial": (
        "partisan_memorial",
        "war_memorial",
        "genocide_memorial",
        "commemorative_plaque",
        "monumental_complex",
    ),
    "religious": (
        "church",
        "monastery",
        "mosque",
        "chapel",
        "shrine",
        "cemetery",
    ),
    "architectural": (
        "fortress",
        "castle",
        "tower",
        "bridge",
        "historic_house",
        "palace",
        "urban_block",
    ),
    "archaeological": (
        "archaeological_site",
        "ruins",
        "villa_rustica",
        "ancient_settlement",
        "burial_mound",
    ),
    "industrial": (
        "mine",
        "factory",
        "railway",
        "dam",
        "industrial_complex",
    ),
    "cultural_landscape": (
        "cultural_landscape",
        "heritage_route",
        "historic_area",
        "rural_landscape",
    ),
    "military": (
        "fortification",
        "bunker",
        "military_complex",
        "battlefield",
        "defensive_wall",
    ),
}

HERITAGE_FOR_SUBTYPE: dict[str, str] = {}
for _ht, subs in SUBTYPES_BY_HERITAGE.items():
    for _s in subs:
        HERITAGE_FOR_SUBTYPE[_s] = _ht


def all_subtypes_sorted() -> list[str]:
    out: list[str] = []
    for subs in SUBTYPES_BY_HERITAGE.values():
        out.extend(subs)
    return sorted(set(out))


def subtypes_for_heritage(heritage_type: str) -> tuple[str, ...]:
    return SUBTYPES_BY_HERITAGE.get(heritage_type, ())


def is_valid_triplet(heritage_type: str, subtype: str, form: str, style: str) -> bool:
    if heritage_type not in HERITAGE_TYPES:
        return False
    if subtype not in subtypes_for_heritage(heritage_type):
        return False
    if form not in FORM_OPTIONS:
        return False
    if style not in STYLE_OPTIONS:
        return False
    return True


# --- Migration from older schema (free subtype, extended forms, setting column) ---

FORM_LEGACY_TO_CANONICAL: dict[str, str] = {
    "pillar_slab": "pillar",
    "modernist_pylon": "obelisk",
    "relief_wall": "stele",
    "relief_panel": "stele",
    "sarcophagus": "chest",
    "other": "slab",
}

SUBTYPE_ALIASES: dict[str, str] = {
    # legacy / typos → canonical subtype (heritage must match via HERITAGE_FOR_SUBTYPE)
}

CENTURY_OVERRIDES_FOR_SUBTYPE: dict[str, tuple[str, str]] = {
    # if we must force heritage+subtype from broken rows (rare)
}


def canonical_form(raw: str | None) -> str:
    if not raw:
        return "slab"
    r = raw.strip()
    if r in FORM_OPTIONS:
        return r
    return FORM_LEGACY_TO_CANONICAL.get(r, "slab")


def canonical_subtype_and_heritage(
    heritage_raw: str | None, subtype_raw: str | None
) -> tuple[str, str]:
    """Return (heritage_type, subtype) satisfying controlled vocabulary."""
    st = (subtype_raw or "").strip()
    ht = (heritage_raw or "").strip()

    if not st:
        if ht in SUBTYPES_BY_HERITAGE and SUBTYPES_BY_HERITAGE[ht]:
            return ht, SUBTYPES_BY_HERITAGE[ht][0]
        return "archaeological", "archaeological_site"

    if st in HERITAGE_FOR_SUBTYPE:
        return HERITAGE_FOR_SUBTYPE[st], st

    if st in SUBTYPE_ALIASES:
        st = SUBTYPE_ALIASES[st]
        if st in HERITAGE_FOR_SUBTYPE:
            return HERITAGE_FOR_SUBTYPE[st], st

    if ht == "memorial" and "partisan" in st.lower():
        return "memorial", "partisan_memorial"
    if "villa" in st.lower():
        return "archaeological", "villa_rustica"
    if ht in SUBTYPES_BY_HERITAGE and SUBTYPES_BY_HERITAGE[ht]:
        return ht, SUBTYPES_BY_HERITAGE[ht][0]
    return "archaeological", "archaeological_site"


def infer_style_from_record(
    *,
    heritage_type: str,
    subtype: str,
    century: int,
    old_form_hint: str | None,
) -> str:
    if heritage_type == "memorial" and subtype in (
        "partisan_memorial",
        "monumental_complex",
    ):
        return "socialist_modernism"
    if old_form_hint and "modernist" in old_form_hint:
        return "socialist_modernism"
    if century >= 20 and heritage_type in ("memorial", "industrial"):
        return "modernist" if heritage_type == "industrial" else "socialist_modernism"
    if heritage_type == "archaeological" and century <= 6:
        return "medieval"
    if heritage_type in ("funerary", "religious") and century <= 16:
        return "medieval"
    return "medieval"


# --- Display labels (English primary; YU uses Latin labels below) ---

_EN_UNESCO = {
    "monument": "Individual monument",
    "group_of_buildings": "Group of buildings",
    "site": "Site",
}
_YU_UNESCO = {
    "monument": "Pojedinačni spomenik",
    "group_of_buildings": "Grupa građevina",
    "site": "Lokalitet",
}

_EN_HERITAGE = {
    "funerary": "Funerary",
    "memorial": "Memorial",
    "religious": "Religious",
    "architectural": "Architectural",
    "archaeological": "Archaeological",
    "industrial": "Industrial",
    "cultural_landscape": "Cultural landscape",
    "military": "Military",
}
_YU_HERITAGE = {
    "funerary": "Grobni",
    "memorial": "Memorijalni",
    "religious": "Vjerski",
    "architectural": "Arhitektonski",
    "archaeological": "Arheološki",
    "industrial": "Industrijski",
    "cultural_landscape": "Kulturni krajolik",
    "military": "Vojni",
}

_EN_FORM = {
    "slab": "Slab",
    "chest": "Chest",
    "gabled": "Gabled roof",
    "pillar": "Pillar",
    "stele": "Stele",
    "obelisk": "Obelisk",
    "cross_form": "Cross / cruciform",
}
_YU_FORM = {k: v for k, v in _EN_FORM.items()}

_EN_STYLE = {
    "medieval": "Medieval",
    "ottoman": "Ottoman",
    "modernist": "Modernist",
    "socialist_modernism": "Socialist modernism",
    "contemporary": "Contemporary",
}
_YU_STYLE = {
    "medieval": "Srednjovjekovni",
    "ottoman": "Osmanski",
    "modernist": "Modernistički",
    "socialist_modernism": "Socijalistički modernizam",
    "contemporary": "Suvremeni",
}

# Readable subtype names (Balkan / UNESCO context)
_SUBTYPE_EN: dict[str, str] = {
    "stecak": "Stećak",
    "tombstone": "Tombstone",
    "necropolis": "Necropolis",
    "mausoleum": "Mausoleum",
    "sarcophagus": "Sarcophagus (subtype)",
    "grave_marker": "Grave marker",
    "partisan_memorial": "Partisan memorial",
    "war_memorial": "War memorial",
    "genocide_memorial": "Genocide memorial",
    "commemorative_plaque": "Commemorative plaque",
    "monumental_complex": "Monumental complex",
    "church": "Church",
    "monastery": "Monastery",
    "mosque": "Mosque",
    "chapel": "Chapel",
    "shrine": "Shrine",
    "cemetery": "Cemetery",
    "fortress": "Fortress",
    "castle": "Castle",
    "tower": "Tower",
    "bridge": "Bridge",
    "historic_house": "Historic house",
    "palace": "Palace",
    "urban_block": "Urban block",
    "archaeological_site": "Archaeological site",
    "ruins": "Ruins",
    "villa_rustica": "Villa rustica",
    "ancient_settlement": "Ancient settlement",
    "burial_mound": "Burial mound",
    "mine": "Mine",
    "factory": "Factory",
    "railway": "Railway heritage",
    "dam": "Dam",
    "industrial_complex": "Industrial complex",
    "cultural_landscape": "Cultural landscape (subtype)",
    "heritage_route": "Heritage route",
    "historic_area": "Historic area",
    "rural_landscape": "Rural landscape",
    "fortification": "Fortification",
    "bunker": "Bunker",
    "military_complex": "Military complex",
    "battlefield": "Battlefield",
    "defensive_wall": "Defensive wall",
}


def _yu(code: str, en: dict[str, str], yu: dict[str, str], use_cyrillic: bool) -> str:
    if use_cyrillic:
        return yu.get(code, en.get(code, code))
    return yu.get(code, en.get(code, code))


def label_unesco(code: str, *, lang: str, cyrillic: bool) -> str:
    if lang == "yu":
        return _yu(code, _EN_UNESCO, _YU_UNESCO, cyrillic)
    return _EN_UNESCO.get(code, code)


def label_heritage(code: str, *, lang: str, cyrillic: bool) -> str:
    if lang == "yu":
        return _yu(code, _EN_HERITAGE, _YU_HERITAGE, cyrillic)
    return _EN_HERITAGE.get(code, code)


def label_form(code: str, *, lang: str, cyrillic: bool) -> str:
    if lang == "yu":
        return _yu(code, _EN_FORM, _YU_FORM, cyrillic)
    return _EN_FORM.get(code, code)


def label_style(code: str, *, lang: str, cyrillic: bool) -> str:
    if lang == "yu":
        return _yu(code, _EN_STYLE, _YU_STYLE, cyrillic)
    return _EN_STYLE.get(code, code)


def label_subtype(code: str, *, lang: str, cyrillic: bool) -> str:
    del lang, cyrillic  # same EN/YU string for brevity; extend later if needed
    return _SUBTYPE_EN.get(code, code.replace("_", " ").title())
