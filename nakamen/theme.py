"""Design tokens and Flet theme helpers."""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft


@dataclass(frozen=True)
class Tokens:
    bg_primary: str
    bg_secondary: str
    text_primary: str
    text_secondary: str
    accent: str
    border: str
    card_bg: str


LIGHT = Tokens(
    bg_primary="#F2E6D8",
    bg_secondary="#E8D8C3",
    text_primary="#3A3A3A",
    text_secondary="#8C7A66",
    accent="#C2A27A",
    border="#D6C2A8",
    card_bg="#F7EFE4",
)

DARK = Tokens(
    bg_primary="#1E1C1A",
    bg_secondary="#2A2724",
    text_primary="#EAE3D9",
    text_secondary="#B8A999",
    accent="#C2A27A",
    border="#3A352F",
    card_bg="#25221F",
)

# Carto basemaps (OSM-derived). Do not use tile.openstreetmap.org — unauthenticated
# clients get 403 per https://operations.osmfoundation.org/policies/tiles/
CARTO_LIGHT_TILE = (
    "https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png"
)
CARTO_DARK_TILE = (
    "https://cartodb-basemaps-a.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png"
)


def editorial_font(script: str) -> str:
    if script == "cyrillic":
        return "Noto Serif, 'Times New Roman', serif"
    return "Athelas, Palatino, 'Noto Serif', Georgia, serif"


def make_page_theme(tokens: Tokens) -> ft.Theme:
    sch = ft.ColorScheme(
        primary=tokens.accent,
        on_primary=tokens.text_primary,
        surface=tokens.bg_primary,
        on_surface=tokens.text_primary,
        secondary=tokens.bg_secondary,
        on_secondary=tokens.text_primary,
        outline=tokens.border,
    )
    return ft.Theme(
        color_scheme=sch,
        use_material3=True,
        visual_density=ft.VisualDensity.COMFORTABLE,
    )


def card_shadow() -> list[ft.BoxShadow]:
    return [
        ft.BoxShadow(
            spread_radius=0,
            blur_radius=14,
            color=ft.Colors.with_opacity(0.12, "#000000"),
            offset=ft.Offset(0, 4),
        )
    ]
