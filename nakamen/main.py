"""nakamen — Flet UI: map, filters, i18n, themes."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

# `flet run nakamen/main.py` puts only `nakamen/` on sys.path, so `import nakamen`
# fails unless the project root is added.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import flet as ft
import flet_map as ftm

if sys.platform == "emscripten":
    try:
        from nakamen import web_db as db, i18n, taxonomy, theme
    except (ModuleNotFoundError, ImportError):
        import web_db as db  # type: ignore
        import i18n  # type: ignore
        import taxonomy  # type: ignore
        import theme  # type: ignore
else:
    try:
        from nakamen import db, i18n, taxonomy, theme
    except (ModuleNotFoundError, ImportError):
        import db  # type: ignore
        import i18n  # type: ignore
        import taxonomy  # type: ignore
        import theme  # type: ignore

# Logos live next to this file: `nakamen/assets/`. That matches `flet run -a assets`,
# which resolves `assets` relative to the script directory (not the repo root).
ASSETS_DIR = str(Path(__file__).resolve().parent / "assets")
UPLOADS_DIR = Path(ASSETS_DIR) / "uploads"

# Bar height; logo scales to fit inside vertical padding
_TOP_BAR_PADDING_V = 10
_LOGO_HEIGHT = 34


class NakamenApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.lang: i18n.Lang = "en"
        self.script: i18n.Script = "latin"
        self.dark = False
        self.filter_heritage_type: str | None = None
        self.filter_subtype: str | None = None
        self.filter_style: str | None = None
        self.century_min = 12
        self.century_max = 21

        self.lang_seg = ft.Ref[ft.SegmentedButton]()
        self.script_seg = ft.Ref[ft.SegmentedButton]()
        self.map_ref = ft.Ref[ftm.Map]()
        self.theme_btn = ft.Ref[ft.IconButton]()
        self.filter_btn = ft.Ref[ft.OutlinedButton]()
        self.stack_ref = ft.Ref[ft.Stack]()
        self.file_picker = ft.FilePicker(on_result=self._on_image_pick_result)
        self.add_fields: dict[str, ft.Control] | None = None
        self.add_image_preview_ref = ft.Ref[ft.Container]()
        self.add_symbols_row_ref = ft.Ref[ft.Row]()
        self.add_sheet: ft.BottomSheet | None = None
        self.add_pick_mode = False
        self.add_draft_latlng: tuple[float, float] | None = None
        self.add_symbol_choices: set[str] = set()

    @property
    def tokens(self) -> theme.Tokens:
        return theme.DARK if self.dark else theme.LIGHT

    def tr(self, key: str) -> str:
        return i18n.tr(self.lang, self.script, key)

    def ui_font(self) -> str:
        if self.lang == "en":
            return theme.editorial_font("latin")
        return theme.editorial_font(self.script)

    def _text(
        self,
        s: str,
        *,
        size: int = 14,
        weight: ft.FontWeight | None = None,
        color: str | None = None,
    ) -> ft.Text:
        return ft.Text(
            s,
            size=size,
            weight=weight,
            color=color or self.tokens.text_primary,
            font_family=self.ui_font(),
        )

    def _tax(self) -> tuple[str, bool]:
        return (
            "yu" if self.lang == "yu" else "en",
            self.lang == "yu" and self.script == "cyrillic",
        )

    def _tile_url(self) -> str:
        return theme.CARTO_DARK_TILE if self.dark else theme.CARTO_LIGHT_TILE

    def _attribution(self) -> ftm.MapLayer:
        # Carto tiles: credit OSM + Carto (https://carto.com/basemaps/)
        return ftm.RichAttribution(
            attributions=[
                ftm.TextSourceAttribution(
                    text="© OpenStreetMap contributors",
                    on_click=lambda e: e.page.launch_url(
                        "https://www.openstreetmap.org/copyright"
                    ),
                ),
                ftm.TextSourceAttribution(
                    text="© CARTO",
                    on_click=lambda e: e.page.launch_url(
                        "https://carto.com/attribution/"
                    ),
                ),
            ]
        )

    def _marker_icon(self) -> ft.Control:
        return ft.Container(
            width=40,
            height=40,
            alignment=ft.alignment.center,
            border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.92, self.tokens.card_bg),
            border=ft.border.all(1, self.tokens.border),
            shadow=theme.card_shadow(),
            content=ft.Icon(ft.Icons.PLACE, color=self.tokens.accent, size=22),
        )

    def _markers(self) -> list[ftm.Marker]:
        rows = db.fetch_monuments(
            self.filter_heritage_type,
            self.filter_subtype,
            self.filter_style,
            self.century_min,
            self.century_max,
        )
        out: list[ftm.Marker] = []
        for m in rows:
            mid = int(m["id"])

            def on_marker_click(_e, monument_id: int = mid) -> None:
                self._open_detail(monument_id)

            out.append(
                ftm.Marker(
                    coordinates=ftm.MapLatitudeLongitude(m["latitude"], m["longitude"]),
                    content=ft.Container(
                        content=self._marker_icon(),
                        on_click=on_marker_click,
                    ),
                    data=mid,
                )
            )
        return out

    def _map_layers(self) -> list[ftm.MapLayer]:
        layers: list[ftm.MapLayer] = [
            ftm.TileLayer(url_template=self._tile_url()),
            self._attribution(),
            ftm.MarkerLayer(markers=self._markers()),
        ]
        if self.add_draft_latlng:
            layers.append(
                ftm.MarkerLayer(
                    markers=[
                        ftm.Marker(
                            coordinates=ftm.MapLatitudeLongitude(
                                self.add_draft_latlng[0], self.add_draft_latlng[1]
                            ),
                            content=ft.Icon(
                                ft.Icons.PLACE,
                                color=self.tokens.accent,
                                size=28,
                            ),
                        )
                    ]
                )
            )
        return layers

    def _sync_map_layers(self) -> None:
        m = self.map_ref.current
        if m is not None:
            m.layers = self._map_layers()
            m.update()

    def _sync_page_chrome(self) -> None:
        t = self.tokens
        self.page.bgcolor = t.bg_primary
        self.page.theme = theme.make_page_theme(theme.LIGHT)
        self.page.dark_theme = theme.make_page_theme(theme.DARK)
        self.page.theme_mode = ft.ThemeMode.DARK if self.dark else ft.ThemeMode.LIGHT

    def _open_detail(self, monument_id: int) -> None:
        row = db.get_monument(monument_id)
        if not row:
            return
        t = self.tokens
        lang, cyr = self._tax()
        syms = [s.strip() for s in (row["symbols"] or "").split(",") if s.strip()]

        def img_block(url: str, cap: str) -> ft.Control:
            return ft.Column(
                tight=True,
                spacing=4,
                controls=[
                    self._text(
                        cap,
                        size=11,
                        color=t.text_secondary,
                    ),
                    ft.Container(
                        border_radius=10,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        bgcolor=t.bg_secondary,
                        content=ft.Image(
                            src=url,
                            fit=ft.ImageFit.COVER,
                            width=420,
                            height=220,
                        ),
                    ),
                ],
            )

        def meta_line(lab: str, val: str) -> ft.Control:
            return ft.Row(
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=8,
                controls=[
                    ft.Container(
                        width=128,
                        content=self._text(
                            lab, size=11, color=t.text_secondary
                        ),
                    ),
                    ft.Container(
                        expand=True,
                        content=self._text(val, size=13),
                    ),
                ],
            )

        u = taxonomy.label_unesco(row["unesco_class"], lang=lang, cyrillic=cyr)
        h = taxonomy.label_heritage(row["heritage_type"], lang=lang, cyrillic=cyr)
        st_l = taxonomy.label_subtype(
            row["subtype"], lang=lang, cyrillic=cyr
        )
        f = taxonomy.label_form(row["form"], lang=lang, cyrillic=cyr)
        sty = taxonomy.label_style(
            row.get("style") or "medieval", lang=lang, cyrillic=cyr
        )
        loc = f"{row['region']}"
        try:
            loc = f"{row['region']} · {row['latitude']:.4f}, {row['longitude']:.4f}"
        except (TypeError, ValueError):
            pass

        image_source = (row.get("image_path") or "").strip() or row["image_url"]
        body: list[ft.Control] = [
            self._text(loc, size=12, color=t.text_secondary),
            img_block(image_source, self.tr("photo")),
        ]
        ill = (row.get("illustration_url") or "").strip()
        if ill:
            body.append(img_block(ill, self.tr("illustration")))
        body += [
            self._text(self.tr("description"), size=11, color=t.text_secondary),
            self._text(row["description"] or "", size=14),
            self._text(self.tr("metadata"), size=12, weight=ft.FontWeight.W_500),
            meta_line(self.tr("unesco_class"), u),
            meta_line(self.tr("heritage_type"), h),
            meta_line(self.tr("subtype"), st_l),
            meta_line(self.tr("form"), f),
            meta_line(self.tr("style"), sty),
            meta_line(self.tr("century"), f"{row['century']}"),
            meta_line(self.tr("material"), row["material"] or "—"),
        ]
        if syms:
            body.append(
                self._text(self.tr("symbols"), size=11, color=t.text_secondary)
            )
            body.append(
                ft.Row(
                    wrap=True,
                    spacing=6,
                    run_spacing=6,
                    controls=[
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            border_radius=8,
                            bgcolor=t.bg_secondary,
                            border=ft.border.all(1, t.border),
                            content=self._text(sym, size=12),
                        )
                        for sym in syms
                    ],
                )
            )

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=t.card_bg,
            title=self._text(
                row["title"] or "—", size=20, weight=ft.FontWeight.W_600
            ),
            content=ft.Container(
                width=460,
                content=ft.Column(
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=12,
                    controls=body,
                ),
            ),
            actions=[
                ft.TextButton(
                    self.tr("cancel"),
                    on_click=lambda e: self.page.close(dlg),
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def _snack(self, message: str) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color=self.tokens.text_primary),
            bgcolor=self.tokens.card_bg,
        )
        self.page.snack_bar.open = True
        self.page.update()

    def _filter_subtype_label(self, code: str, lang: str, cyr: bool) -> str:
        ht = taxonomy.HERITAGE_FOR_SUBTYPE[code]
        return (
            f"{taxonomy.label_heritage(ht, lang=lang, cyrillic=cyr)} · "
            f"{taxonomy.label_subtype(code, lang=lang, cyrillic=cyr)}"
        )

    def _open_filters(self) -> None:
        t = self.tokens
        lang, cyr = self._tax()
        heritage_opts: list[ft.dropdown.Option] = [
            ft.dropdown.Option("all", self.tr("all_heritage"))
        ]
        for h in taxonomy.HERITAGE_TYPES:
            heritage_opts.append(
                ft.dropdown.Option(
                    h, taxonomy.label_heritage(h, lang=lang, cyrillic=cyr)
                )
            )
        sub_opts: list[ft.dropdown.Option] = [
            ft.dropdown.Option("all", self.tr("all_subtypes"))
        ]
        for s in taxonomy.all_subtypes_sorted():
            sub_opts.append(
                ft.dropdown.Option(s, self._filter_subtype_label(s, lang, cyr))
            )
        style_opts: list[ft.dropdown.Option] = [
            ft.dropdown.Option("all", self.tr("all_styles"))
        ]
        for st in taxonomy.STYLE_OPTIONS:
            style_opts.append(
                ft.dropdown.Option(
                    st,
                    taxonomy.label_style(st, lang=lang, cyrillic=cyr),
                )
            )

        heritage_dd = ft.Dropdown(
            label=self.tr("heritage_type"),
            value=self.filter_heritage_type or "all",
            options=heritage_opts,
            border_color=t.border,
            filled=True,
            bgcolor=t.card_bg,
        )
        sub_dd = ft.Dropdown(
            label=self.tr("subtype"),
            value=self.filter_subtype or "all",
            options=sub_opts,
            border_color=t.border,
            filled=True,
            bgcolor=t.card_bg,
        )
        style_dd = ft.Dropdown(
            label=self.tr("style"),
            value=self.filter_style or "all",
            options=style_opts,
            border_color=t.border,
            filled=True,
            bgcolor=t.card_bg,
        )
        min_tf = ft.TextField(
            label=self.tr("min"),
            value=str(self.century_min),
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color=t.border,
            filled=True,
            bgcolor=t.card_bg,
        )
        max_tf = ft.TextField(
            label=self.tr("max"),
            value=str(self.century_max),
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color=t.border,
            filled=True,
            bgcolor=t.card_bg,
        )

        sheet = ft.BottomSheet(
            bgcolor=t.bg_secondary,
            content=ft.Container(
                padding=24,
                content=ft.Column(
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        self._text(
                            self.tr("filter"), size=18, weight=ft.FontWeight.W_600
                        ),
                        heritage_dd,
                        sub_dd,
                        style_dd,
                        self._text(
                            self.tr("century_range"), size=12, color=t.text_secondary
                        ),
                        ft.Row(controls=[min_tf, max_tf], spacing=12),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            spacing=12,
                            controls=[
                                ft.TextButton(
                                    self.tr("cancel"),
                                    on_click=lambda e: self.page.close(sheet),
                                ),
                                ft.FilledButton(
                                    self.tr("apply"),
                                    style=ft.ButtonStyle(
                                        bgcolor=t.accent, color=t.text_primary
                                    ),
                                    on_click=lambda e: self._apply_filters(
                                        sheet,
                                        heritage_dd.value,
                                        sub_dd.value,
                                        style_dd.value,
                                        min_tf.value,
                                        max_tf.value,
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        )
        self.page.open(sheet)

    def _apply_filters(
        self,
        sheet: ft.BottomSheet,
        heritage: str | None,
        subtype: str | None,
        style: str | None,
        cmin: str | None,
        cmax: str | None,
    ) -> None:
        self.filter_heritage_type = (
            None if heritage in (None, "all") else heritage
        )
        self.filter_subtype = None if subtype in (None, "all") else subtype
        self.filter_style = None if style in (None, "all") else style
        try:
            self.century_min = int(cmin or self.century_min)
            self.century_max = int(cmax or self.century_max)
        except ValueError:
            self._snack(self.tr("invalid_numbers"))
            return
        if self.century_min > self.century_max:
            self.century_min, self.century_max = self.century_max, self.century_min
        self._sync_map_layers()
        self.page.close(sheet)

    def _on_add_heritage_change(
        self,
        e: ft.ControlEvent,
        sub_ref: ft.Ref[ft.Dropdown],
        lang: str,
        cyr: bool,
    ) -> None:
        h = e.control.value
        dd = sub_ref.current
        if not h or not dd:
            return
        subs = taxonomy.subtypes_for_heritage(h)
        dd.options = [
            ft.dropdown.Option(
                s, taxonomy.label_subtype(s, lang=lang, cyrillic=cyr)
            )
            for s in subs
        ]
        dd.value = subs[0]
        dd.update()
        self.page.update()

    def _refresh_add_image_preview(self) -> None:
        if not self.add_fields or not self.add_image_preview_ref.current:
            return
        image_path = (self.add_fields["image_path"].value or "").strip()
        image_url = (self.add_fields["image_url"].value or "").strip()
        source = image_path or image_url
        if not source:
            self.add_image_preview_ref.current.content = ft.Container(
                height=140,
                border_radius=10,
                border=ft.border.all(1, self.tokens.border),
                bgcolor=self.tokens.bg_secondary,
                alignment=ft.alignment.center,
                content=self._text("—", size=18, color=self.tokens.text_secondary),
            )
        else:
            self.add_image_preview_ref.current.content = ft.Container(
                border_radius=10,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Image(src=source, fit=ft.ImageFit.COVER, height=160),
            )
        if self.add_image_preview_ref.current.page is not None:
            self.add_image_preview_ref.current.update()

    def _on_image_pick_result(self, e: ft.FilePickerResultEvent) -> None:
        if not self.add_fields or not e.files:
            return
        try:
            picked = Path(e.files[0].path)
            ext = picked.suffix.lower() or ".img"
            UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            stored = UPLOADS_DIR / f"{uuid.uuid4().hex}{ext}"
            shutil.copy2(picked, stored)
            self.add_fields["image_path"].value = f"/uploads/{stored.name}"
            self._refresh_add_image_preview()
            self.page.update()
        except Exception:
            self._snack(self.tr("image_pick_failed"))

    def _on_remove_uploaded_image(self, _e: ft.ControlEvent) -> None:
        if not self.add_fields:
            return
        self.add_fields["image_path"].value = ""
        self._refresh_add_image_preview()
        self.page.update()

    def _set_add_latlng(self, lat: float, lng: float) -> None:
        self.add_draft_latlng = (lat, lng)
        self._sync_map_layers()
        if not self.add_fields:
            return
        self.add_fields["latitude"].value = f"{lat:.6f}"
        self.add_fields["longitude"].value = f"{lng:.6f}"
        self.add_fields["latitude"].update()
        self.add_fields["longitude"].update()
        self.page.update()

    def _sync_latlng_from_fields(self, _e: ft.ControlEvent | None = None) -> None:
        if not self.add_fields:
            return
        try:
            lat = float(self.add_fields["latitude"].value or 0)
            lng = float(self.add_fields["longitude"].value or 0)
            self.add_draft_latlng = (lat, lng)
            self.page.update()
        except ValueError:
            return

    def _start_map_pick(self, _e: ft.ControlEvent) -> None:
        self.add_pick_mode = True
        self._snack(self.tr("map_pick_active"))

    def _use_map_center_for_location(self, _e: ft.ControlEvent) -> None:
        m = self.map_ref.current
        if m is None:
            return
        center = m.center
        if center is None:
            return
        self._set_add_latlng(center.latitude, center.longitude)

    def _on_map_tap(self, e: ftm.MapTapEvent) -> None:
        if not self.add_pick_mode:
            return
        self.add_pick_mode = False
        self._set_add_latlng(e.coordinates.latitude, e.coordinates.longitude)

    def _close_add_sheet(self, sheet: ft.BottomSheet) -> None:
        self.add_pick_mode = False
        self.add_draft_latlng = None
        self.add_fields = None
        self.add_symbol_choices = set()
        self._sync_map_layers()
        self.page.close(sheet)

    def _selected_symbols(self) -> str:
        if not self.add_fields:
            return ""
        custom = (self.add_fields["symbols_custom"].value or "").strip()
        custom_parts = [x.strip() for x in custom.split(",") if x.strip()]
        return ",".join(sorted(self.add_symbol_choices) + custom_parts)

    def _toggle_symbol_chip(self, key: str, _e: ft.ControlEvent) -> None:
        if key in self.add_symbol_choices:
            self.add_symbol_choices.remove(key)
        else:
            self.add_symbol_choices.add(key)

    def _open_add(self) -> None:
        t = self.tokens
        lang, cyr = self._tax()
        sub_ref = ft.Ref[ft.Dropdown]()
        fun_subs = taxonomy.subtypes_for_heritage("funerary")
        unesco_opts = [
            ft.dropdown.Option(
                c, taxonomy.label_unesco(c, lang=lang, cyrillic=cyr)
            )
            for c in taxonomy.UNESCO_CLASSES
        ]
        heritage_opts = [
            ft.dropdown.Option(
                h, taxonomy.label_heritage(h, lang=lang, cyrillic=cyr)
            )
            for h in taxonomy.HERITAGE_TYPES
        ]
        form_opts = [
            ft.dropdown.Option(
                f, taxonomy.label_form(f, lang=lang, cyrillic=cyr)
            )
            for f in taxonomy.FORM_OPTIONS
        ]
        style_opts = [
            ft.dropdown.Option(
                s, taxonomy.label_style(s, lang=lang, cyrillic=cyr)
            )
            for s in taxonomy.STYLE_OPTIONS
        ]
        fields: dict[str, ft.Control] = {
            "title": ft.TextField(
                label=self.tr("title"),
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "unesco_class": ft.Dropdown(
                label=self.tr("unesco_class"),
                value="monument",
                options=unesco_opts,
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "heritage_type": ft.Dropdown(
                label=self.tr("heritage_type"),
                value="funerary",
                options=heritage_opts,
                on_change=lambda e: self._on_add_heritage_change(
                    e, sub_ref, lang, cyr
                ),
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "subtype": ft.Dropdown(
                ref=sub_ref,
                label=self.tr("subtype"),
                value=fun_subs[0],
                options=[
                    ft.dropdown.Option(
                        s, taxonomy.label_subtype(s, lang=lang, cyrillic=cyr)
                    )
                    for s in fun_subs
                ],
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "form": ft.Dropdown(
                label=self.tr("form"),
                value="slab",
                options=form_opts,
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "style": ft.Dropdown(
                label=self.tr("style"),
                value="medieval",
                options=style_opts,
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "century": ft.TextField(
                label=self.tr("century"),
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "material": ft.TextField(
                label=self.tr("material"),
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "symbols": ft.TextField(
                label="",
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
                visible=False,
            ),
            "symbols_custom": ft.TextField(
                label=self.tr("symbols_custom"),
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "latitude": ft.TextField(
                label=self.tr("latitude"),
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
                on_change=self._sync_latlng_from_fields,
            ),
            "longitude": ft.TextField(
                label=self.tr("longitude"),
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
                on_change=self._sync_latlng_from_fields,
            ),
            "region": ft.TextField(
                label=self.tr("region"),
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "description": ft.TextField(
                label=self.tr("description"),
                multiline=True,
                min_lines=2,
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
            "image_url": ft.TextField(
                label=self.tr("image_url"),
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
                on_change=lambda e: self._refresh_add_image_preview(),
            ),
            "image_path": ft.TextField(
                label=self.tr("image_path"),
                border_color=t.border,
                filled=True,
                read_only=True,
                bgcolor=t.card_bg,
            ),
            "illustration_url": ft.TextField(
                label=self.tr("illustration_url"),
                border_color=t.border,
                filled=True,
                bgcolor=t.card_bg,
            ),
        }
        self.add_fields = fields
        self.add_sheet = None
        self.add_pick_mode = False
        self.add_draft_latlng = None
        self.add_symbol_choices = set()

        symbol_keys = [
            "cross",
            "rosette",
            "crescent",
            "flame",
            "star",
            "sword",
            "spiral",
        ]
        symbols_row = ft.Row(
            ref=self.add_symbols_row_ref,
            wrap=True,
            spacing=8,
            run_spacing=8,
            controls=[
                ft.Chip(
                    label=self._text(k, size=12),
                    selected=False,
                    on_select=lambda e, sym=k: self._toggle_symbol_chip(sym, e),
                )
                for k in symbol_keys
            ],
        )
        image_preview = ft.Container(ref=self.add_image_preview_ref)
        self._refresh_add_image_preview()

        basic_section = ft.ExpansionTile(
            title=self._text(self.tr("basic_section"), weight=ft.FontWeight.W_600),
            initially_expanded=True,
            controls=[
                fields["title"],
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.OutlinedButton(
                            self.tr("pick_image"),
                            icon=ft.Icons.UPLOAD_FILE,
                            on_click=lambda e: self.file_picker.pick_files(
                                allow_multiple=False
                            ),
                        ),
                        ft.OutlinedButton(
                            self.tr("replace_image"),
                            icon=ft.Icons.SYNC,
                            on_click=lambda e: self.file_picker.pick_files(
                                allow_multiple=False
                            ),
                        ),
                        ft.TextButton(
                            self.tr("remove_image"),
                            icon=ft.Icons.DELETE_OUTLINE,
                            on_click=self._on_remove_uploaded_image,
                        ),
                    ],
                ),
                image_preview,
                fields["image_path"],
                fields["image_url"],
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.OutlinedButton(
                            self.tr("pick_on_map"),
                            icon=ft.Icons.EDIT_LOCATION_ALT,
                            on_click=self._start_map_pick,
                        ),
                        ft.OutlinedButton(
                            self.tr("use_map_center"),
                            icon=ft.Icons.MY_LOCATION,
                            on_click=self._use_map_center_for_location,
                        ),
                    ],
                ),
                ft.Row(
                    controls=[fields["latitude"], fields["longitude"]],
                    spacing=12,
                ),
                fields["region"],
            ],
        )
        classification_section = ft.ExpansionTile(
            title=self._text(
                self.tr("classification_section"), weight=ft.FontWeight.W_600
            ),
            initially_expanded=True,
            controls=[
                ft.Row(
                    controls=[fields["unesco_class"], fields["heritage_type"]],
                    spacing=12,
                ),
                fields["subtype"],
            ],
        )
        details_section = ft.ExpansionTile(
            title=self._text(self.tr("details_section"), weight=ft.FontWeight.W_600),
            controls=[
                ft.Row(controls=[fields["form"], fields["style"]], spacing=12),
                ft.Row(controls=[fields["century"], fields["material"]], spacing=12),
            ],
        )
        symbols_section = ft.ExpansionTile(
            title=self._text(self.tr("symbols_section"), weight=ft.FontWeight.W_600),
            controls=[symbols_row, fields["symbols_custom"]],
        )
        description_section = ft.ExpansionTile(
            title=self._text(
                self.tr("description_section"), weight=ft.FontWeight.W_600
            ),
            controls=[fields["description"], fields["illustration_url"]],
        )

        sheet = ft.BottomSheet(
            bgcolor=t.bg_secondary,
            content=ft.Container(
                padding=24,
                content=ft.Column(
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=10,
                    controls=[
                        self._text(
                            self.tr("add_monument"),
                            size=18,
                            weight=ft.FontWeight.W_600,
                        ),
                        basic_section,
                        classification_section,
                        details_section,
                        symbols_section,
                        description_section,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            spacing=12,
                            controls=[
                                ft.TextButton(
                                    self.tr("cancel"),
                                    on_click=lambda e: self._close_add_sheet(sheet),
                                ),
                                ft.FilledButton(
                                    self.tr("save"),
                                    style=ft.ButtonStyle(
                                        bgcolor=t.accent, color=t.text_primary
                                    ),
                                    on_click=lambda e: self._save_monument(
                                        sheet, fields
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        )
        self.add_sheet = sheet
        self.page.open(sheet)

    def _save_monument(self, sheet: ft.BottomSheet, fields: dict[str, ft.Control]) -> None:
        try:
            ht = fields["heritage_type"].value or "funerary"
            sub = fields["subtype"].value or taxonomy.subtypes_for_heritage(ht)[0]
            form = fields["form"].value or "slab"
            sty = fields["style"].value or "medieval"
            data = {
                "title": (fields["title"].value or "").strip(),
                "unesco_class": fields["unesco_class"].value or "monument",
                "heritage_type": ht,
                "subtype": sub,
                "form": form,
                "style": sty,
                "century": int(fields["century"].value or 0),
                "material": (fields["material"].value or "").strip(),
                "symbols": self._selected_symbols(),
                "latitude": float(fields["latitude"].value or 0),
                "longitude": float(fields["longitude"].value or 0),
                "region": (fields["region"].value or "").strip(),
                "description": (fields["description"].value or "").strip(),
                "image_path": (fields["image_path"].value or "").strip(),
                "image_url": (fields["image_url"].value or "").strip(),
                "illustration_url": (fields["illustration_url"].value or "").strip(),
            }
        except ValueError:
            self._snack(self.tr("invalid_numbers"))
            return
        if not data["title"]:
            self._snack(self.tr("title_required"))
            return
        if not taxonomy.is_valid_triplet(
            data["heritage_type"],
            data["subtype"],
            data["form"],
            data["style"],
        ):
            self._snack(self.tr("invalid_taxonomy"))
            return
        try:
            db.insert_monument(data)
        except ValueError:
            self._snack(self.tr("invalid_taxonomy"))
            return
        self._sync_map_layers()
        self._close_add_sheet(sheet)
        self._snack(self.tr("saved_ok"))

    def _on_lang_change(self, e: ft.ControlEvent) -> None:
        ctrl = e.control
        if isinstance(ctrl, ft.SegmentedButton):
            sel = ctrl.selected
            if not sel:
                return
            self.lang = "yu" if "yu" in sel else "en"
            if self.script_seg.current:
                self.script_seg.current.visible = self.lang == "yu"
            if self.filter_btn.current:
                self.filter_btn.current.text = self.tr("filter")
                self.filter_btn.current.update()
        self.page.update()

    def _on_script_change(self, e: ft.ControlEvent) -> None:
        ctrl = e.control
        if isinstance(ctrl, ft.SegmentedButton):
            sel = ctrl.selected
            if not sel:
                return
            self.script = "cyrillic" if "cyrillic" in sel else "latin"
            if self.filter_btn.current:
                self.filter_btn.current.text = self.tr("filter")
                self.filter_btn.current.update()
        self.page.update()

    def _toggle_theme(self, _e: ft.ControlEvent | None) -> None:
        self.dark = not self.dark
        self._sync_page_chrome()
        self._sync_map_layers()
        self._refresh_top_overlay()
        self.page.update()

    def _refresh_top_overlay(self) -> None:
        st = self.stack_ref.current
        if st is None or len(st.controls) < 3:
            return
        c0, _, c2 = st.controls[0], st.controls[1], st.controls[2]
        st.controls = [
            c0,
            ft.Container(
                top=0,
                left=0,
                right=0,
                content=self._build_top(),
            ),
            c2,
        ]
        st.update()

    def _build_logo(self) -> ft.Control:
        """Wordmark + icon; light asset on light theme, dark asset on dark theme."""
        t = self.tokens
        src = "/logo_dark.png" if self.dark else "/logo_light.png"
        # Cap width so the header Row can keep logo + controls on one line; align
        # left inside the cap (avoids the old CONTAIN centering gap).
        return ft.Container(
            height=_LOGO_HEIGHT + 4,
            width=200,
            alignment=ft.alignment.center_left,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Image(
                src=src,
                height=_LOGO_HEIGHT,
                fit=ft.ImageFit.FIT_HEIGHT,
                filter_quality=ft.FilterQuality.HIGH,
                error_content=ft.Text(
                    "nakamen",
                    size=16,
                    weight=ft.FontWeight.W_600,
                    color=t.text_primary,
                    font_family=theme.editorial_font(
                        self.script if self.lang == "yu" else "latin"
                    ),
                ),
            ),
        )

    def _build_top(self) -> ft.Container:
        t = self.tokens
        return ft.Container(
            bgcolor=t.bg_primary,
            border=ft.border.only(
                bottom=ft.BorderSide(1, t.border),
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=_TOP_BAR_PADDING_V),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=False,
                spacing=12,
                controls=[
                    self._build_logo(),
                    ft.Row(
                        spacing=8,
                        wrap=False,
                        controls=[
                            ft.IconButton(
                                ref=self.theme_btn,
                                icon=ft.Icons.DARK_MODE
                                if not self.dark
                                else ft.Icons.LIGHT_MODE,
                                icon_color=t.text_primary,
                                tooltip="Theme",
                                style=ft.ButtonStyle(bgcolor=t.bg_secondary),
                                on_click=self._toggle_theme,
                            ),
                            ft.SegmentedButton(
                                ref=self.lang_seg,
                                selected={self.lang},
                                segments=[
                                    ft.Segment(value="en", label=ft.Text("EN")),
                                    ft.Segment(value="yu", label=ft.Text("YU")),
                                ],
                                on_change=self._on_lang_change,
                                style=ft.ButtonStyle(
                                    color=t.text_primary,
                                    bgcolor=t.bg_secondary,
                                    side=ft.BorderSide(1, t.border),
                                ),
                            ),
                            ft.SegmentedButton(
                                ref=self.script_seg,
                                selected={self.script},
                                visible=self.lang == "yu",
                                segments=[
                                    ft.Segment(value="latin", label=ft.Text("Latin")),
                                    ft.Segment(value="cyrillic", label=ft.Text("Cyrillic")),
                                ],
                                on_change=self._on_script_change,
                                style=ft.ButtonStyle(
                                    color=t.text_primary,
                                    bgcolor=t.bg_secondary,
                                    side=ft.BorderSide(1, t.border),
                                ),
                            ),
                            ft.OutlinedButton(
                                ref=self.filter_btn,
                                text=self.tr("filter"),
                                on_click=lambda e: self._open_filters(),
                                style=ft.ButtonStyle(
                                    color=t.text_primary,
                                    bgcolor=t.bg_secondary,
                                    side=ft.BorderSide(1, t.border),
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        )

    def _build_map(self) -> ftm.Map:
        return ftm.Map(
            ref=self.map_ref,
            expand=True,
            initial_center=ftm.MapLatitudeLongitude(44.2, 17.4),
            initial_zoom=6.8,
            interaction_configuration=ftm.MapInteractionConfiguration(
                flags=ftm.MapInteractiveFlag.ALL
            ),
            on_tap=self._on_map_tap,
            layers=self._map_layers(),
        )

    def mount(self) -> None:
        db.init_db()
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.page.padding = 0
        self.page.spacing = 0
        self._sync_page_chrome()
        self.page.overlay.append(self.file_picker)
        top = self._build_top()
        m = self._build_map()
        fab = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            bgcolor=self.tokens.accent,
            foreground_color=self.tokens.text_primary,
            on_click=lambda e: self._open_add(),
        )
        self.page.add(
            ft.Stack(
                ref=self.stack_ref,
                expand=True,
                controls=[
                    ft.Container(
                        content=m, expand=True, left=0, top=0, right=0, bottom=0
                    ),
                    ft.Container(top=0, left=0, right=0, content=top),
                    ft.Container(bottom=28, right=24, content=fab),
                ],
            )
        )


def main(page: ft.Page) -> None:
    NakamenApp(page).mount()


if sys.platform == "emscripten":
    ft.app(target=main, assets_dir=ASSETS_DIR)
elif __name__ == "__main__":
    ft.app(target=main, assets_dir=ASSETS_DIR)
