"""Web runtime DB adapter for Pyodide (no sqlite3)."""

from __future__ import annotations

from typing import Any, Optional

try:
    from nakamen import taxonomy
except (ModuleNotFoundError, ImportError):
    import taxonomy  # type: ignore

_ROWS: list[dict[str, Any]] = []
_NEXT_ID = 1


def init_db() -> None:
    """No-op for web runtime; keep data in memory."""
    return


def fetch_monuments(
    heritage_type: Optional[str] = None,
    subtype: Optional[str] = None,
    style: Optional[str] = None,
    century_min: int = 1,
    century_max: int = 30,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in _ROWS:
        if not (century_min <= int(r.get("century", 0)) <= century_max):
            continue
        if heritage_type and r.get("heritage_type") != heritage_type:
            continue
        if subtype and r.get("subtype") != subtype:
            continue
        if style and r.get("style") != style:
            continue
        out.append(dict(r))
    return sorted(out, key=lambda x: int(x["id"]))


def get_monument(monument_id: int) -> Optional[dict[str, Any]]:
    for r in _ROWS:
        if int(r["id"]) == int(monument_id):
            return dict(r)
    return None


def insert_monument(data: dict[str, Any]) -> int:
    global _NEXT_ID
    if not taxonomy.is_valid_triplet(
        data["heritage_type"],
        data["subtype"],
        data["form"],
        data["style"],
    ):
        raise ValueError("Invalid heritage/subtype/form/style combination")

    row = dict(data)
    row["id"] = _NEXT_ID
    row.setdefault("image_path", "")
    _ROWS.append(row)
    _NEXT_ID += 1
    return int(row["id"])
