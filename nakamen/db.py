"""SQLite persistence for monuments (strict UNESCO-aligned taxonomy)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

try:
    from nakamen import taxonomy
except ModuleNotFoundError:
    import taxonomy  # type: ignore

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "nakamen.db"


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _table_has_column(c: sqlite3.Connection, table: str, column: str) -> bool:
    rows = c.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _create_v4(c: sqlite3.Connection) -> None:
    c.execute(
        """
        CREATE TABLE monuments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            unesco_class TEXT NOT NULL,
            heritage_type TEXT NOT NULL,
            subtype TEXT NOT NULL,
            form TEXT NOT NULL,
            style TEXT NOT NULL,
            century INTEGER NOT NULL,
            material TEXT NOT NULL,
            symbols TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            region TEXT NOT NULL,
            description TEXT NOT NULL,
            image_path TEXT NOT NULL,
            image_url TEXT NOT NULL,
            illustration_url TEXT NOT NULL
        )
        """
    )


def _row_to_insert_tuple(data: dict[str, Any]) -> tuple[Any, ...]:
    return (
        data["title"],
        data["unesco_class"],
        data["heritage_type"],
        data["subtype"],
        data["form"],
        data["style"],
        int(data["century"]),
        data["material"],
        data["symbols"],
        float(data["latitude"]),
        float(data["longitude"]),
        data["region"],
        data["description"],
        data.get("image_path", ""),
        data["image_url"],
        data["illustration_url"],
    )


def _migrate_legacy_row(row: sqlite3.Row) -> dict[str, Any] | None:
    d = dict(row)
    ht, sub = taxonomy.canonical_subtype_and_heritage(
        d.get("heritage_type"), d.get("subtype")
    )
    form = taxonomy.canonical_form(d.get("form"))
    century = int(d.get("century") or 1)
    style = taxonomy.infer_style_from_record(
        heritage_type=ht,
        subtype=sub,
        century=century,
        old_form_hint=str(d.get("form") or ""),
    )
    if not taxonomy.is_valid_triplet(ht, sub, form, style):
        # Last resort: clamp style
        for st in taxonomy.STYLE_OPTIONS:
            if taxonomy.is_valid_triplet(ht, sub, form, st):
                style = st
                break
        else:
            sub = taxonomy.subtypes_for_heritage(ht)[0]
            if not taxonomy.is_valid_triplet(ht, sub, form, style):
                return None
    out = {
        "title": d.get("title") or "Untitled",
        "unesco_class": d.get("unesco_class") or "site",
        "heritage_type": ht,
        "subtype": sub,
        "form": form,
        "style": style,
        "century": century,
        "material": (d.get("material") or "").strip(),
        "symbols": (d.get("symbols") or "").strip(),
        "latitude": float(d.get("latitude") or 0),
        "longitude": float(d.get("longitude") or 0),
        "region": (d.get("region") or "").strip(),
        "description": (d.get("description") or "").strip(),
        "image_path": (d.get("image_path") or "").strip(),
        "image_url": (d.get("image_url") or "").strip(),
        "illustration_url": (d.get("illustration_url") or "").strip(),
    }
    return out


def init_db() -> None:
    with _conn() as c:
        exists = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='monuments'"
        ).fetchone()

        if not exists:
            _create_v4(c)
            return

        has_style = _table_has_column(c, "monuments", "style")
        has_image_path = _table_has_column(c, "monuments", "image_path")
        if has_style and has_image_path:
            return

        # Older schema: migrate
        legacy = c.execute("SELECT * FROM monuments").fetchall()
        c.execute("DROP TABLE monuments")
        _create_v4(c)
        for row in legacy:
            m = _migrate_legacy_row(row)
            if m is None:
                continue
            c.execute(
                """
                INSERT INTO monuments (
                    title, unesco_class, heritage_type, subtype, form, style,
                    century, material, symbols, latitude, longitude, region,
                    description, image_path, image_url, illustration_url
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                _row_to_insert_tuple(m),
            )


def _seed(c: sqlite3.Connection) -> None:
    rows = [
        (
            "Radimlja necropolis",
            "site",
            "funerary",
            "stecak",
            "gabled",
            "medieval",
            15,
            "limestone",
            "cross,archer,spiral border",
            43.1168,
            17.9334,
            "Herzegovina, Bosnia and Herzegovina",
            "One of the most significant medieval stećak necropolises in Herzegovina, with densely carved upright slabs and chest tombs.",
            "",
            "https://picsum.photos/seed/radimlja/800/500",
            "https://picsum.photos/seed/radimlja-ill/800/500",
        ),
        (
            "Boljuni necropolis",
            "site",
            "funerary",
            "stecak",
            "slab",
            "medieval",
            14,
            "limestone",
            "rosette,tools,crescent",
            43.0842,
            17.9610,
            "Herzegovina, Bosnia and Herzegovina",
            "Stećak cluster near Stolac with distinctive regional relief carving and regional motifs.",
            "",
            "https://picsum.photos/seed/boljuni/800/500",
            "https://picsum.photos/seed/boljuni-ill/800/500",
        ),
        (
            "Zgošća stećak group",
            "group_of_buildings",
            "funerary",
            "stecak",
            "pillar",
            "medieval",
            15,
            "limestone",
            "shield,sword,deer",
            44.2230,
            17.8855,
            "Central Bosnia, Bosnia and Herzegovina",
            "Open-field grouping of stećci with rich symbolic reliefs in a rural ridge setting.",
            "",
            "https://picsum.photos/seed/zgoscia/800/500",
            "https://picsum.photos/seed/zgoscia-ill/800/500",
        ),
        (
            "Kakanj stećak field",
            "site",
            "funerary",
            "stecak",
            "chest",
            "medieval",
            16,
            "limestone",
            "kolo dance,cross,arch",
            44.1333,
            18.1167,
            "Central Bosnia, Bosnia and Herzegovina",
            "Ridge-top concentration of upright slabs and chest tombs above the Bosna valley.",
            "",
            "https://picsum.photos/seed/kakanj/800/500",
            "https://picsum.photos/seed/kakanj-ill/800/500",
        ),
        (
            "Partisan memorial (Mostar)",
            "monument",
            "memorial",
            "partisan_memorial",
            "obelisk",
            "socialist_modernism",
            20,
            "concrete,aggregate",
            "flame,brigade star",
            43.3436,
            17.8075,
            "Herzegovina, Bosnia and Herzegovina",
            "Modernist Yugoslav-era commemorative monument exemplifying 20th-century memorial practice.",
            "",
            "https://picsum.photos/seed/yugo1/800/500",
            "https://picsum.photos/seed/yugo1-ill/800/500",
        ),
        (
            "Mogorjelo villa rustica",
            "site",
            "archaeological",
            "villa_rustica",
            "slab",
            "medieval",
            4,
            "masonry,brick",
            "peristyle,domus plan",
            43.0394,
            17.5456,
            "Herzegovina, Bosnia and Herzegovina",
            "Late Roman rural complex: villa rustica remains illustrating agricultural and elite residence patterns.",
            "",
            "https://picsum.photos/seed/mogorjelo/800/500",
            "https://picsum.photos/seed/mogorjelo-ill/800/500",
        ),
        (
            "Trbić tower (example fortress)",
            "monument",
            "military",
            "fortification",
            "tower",
            "ottoman",
            18,
            "stone",
            "embrasure,bartizan",
            43.8255,
            18.3110,
            "Bosnia and Herzegovina",
            "Illustrative Ottoman-era defensive tower form common in highland Balkan towns.",
            "",
            "https://picsum.photos/seed/trbic/800/500",
            "https://picsum.photos/seed/trbic-ill/800/500",
        ),
    ]
    c.executemany(
        """
        INSERT INTO monuments (
            title, unesco_class, heritage_type, subtype, form, style,
            century, material, symbols, latitude, longitude, region,
            description, image_path, image_url, illustration_url
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )


def fetch_monuments(
    heritage_type: Optional[str] = None,
    subtype: Optional[str] = None,
    style: Optional[str] = None,
    century_min: int = 1,
    century_max: int = 30,
) -> list[dict[str, Any]]:
    q = """
        SELECT * FROM monuments
        WHERE century BETWEEN ? AND ?
    """
    args: list[Any] = [century_min, century_max]
    if heritage_type:
        q += " AND heritage_type = ?"
        args.append(heritage_type)
    if subtype:
        q += " AND subtype = ?"
        args.append(subtype)
    if style:
        q += " AND style = ?"
        args.append(style)
    q += " ORDER BY id"
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def get_monument(monument_id: int) -> Optional[dict[str, Any]]:
    with _conn() as c:
        r = c.execute("SELECT * FROM monuments WHERE id = ?", (monument_id,)).fetchone()
        return dict(r) if r else None


def insert_monument(data: dict[str, Any]) -> int:
    if not taxonomy.is_valid_triplet(
        data["heritage_type"],
        data["subtype"],
        data["form"],
        data["style"],
    ):
        raise ValueError("Invalid heritage/subtype/form/style combination")
    with _conn() as c:
        cur = c.execute(
            """
            INSERT INTO monuments (
                title, unesco_class, heritage_type, subtype, form, style,
                century, material, symbols, latitude, longitude, region,
                description, image_path, image_url, illustration_url
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            _row_to_insert_tuple(data),
        )
        return int(cur.lastrowid)
