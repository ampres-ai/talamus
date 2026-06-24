"""Talamus design system: dark-first, dense, calm (Phase R1, PRD 14.3).

One place for palette, spacing and reusable surfaces (cards, stat tiles, empty
states), so every view looks like the same product. Principles from the llm_wiki
study: quiet professional density, clear typographic hierarchy, restrained
accents, no decorative filler.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

# Palette: charcoal base, readable text, restrained multi-accent status colors.
BG = "#0F1216"
CANVAS = "#080A0D"
SIDEBAR = "#161B21"
SURFACE = "#171C22"
SURFACE_2 = "#202832"
BORDER = "#2C3540"
TEXT = "#E6EDF3"
MUTED = "#94A3B0"
ACCENT = "#5C8DFF"
ACCENT_2 = "#4FC3F7"
OK = "#82D37B"
WARN = "#FFB74D"
DANGER = "#FF8A8A"

PAD = 16
GAP = 12


def apply(page: ft.Page) -> None:
    """Page-level look: dark theme, charcoal background, no default padding."""
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0


def section(text: str) -> ft.Control:
    return ft.Text(text, size=11, weight=ft.FontWeight.BOLD, color=MUTED)


def muted(text: str, size: int = 12) -> ft.Control:
    return ft.Text(text, size=size, color=MUTED)


def panel(
    content: ft.Control,
    padding: int = PAD,
    *,
    bgcolor: str = SURFACE,
    border_color: str = BORDER,
    expand: bool | int | None = None,
    width: int | float | None = None,
    height: int | float | None = None,
) -> ft.Container:
    """A single framed workbench surface. Keep radius tight and reusable."""
    return ft.Container(
        content=content,
        bgcolor=bgcolor,
        border=ft.Border.all(1, border_color),
        border_radius=8,
        padding=padding,
        expand=expand,
        width=width,
        height=height,
    )


def card(content: ft.Control, padding: int = PAD) -> ft.Control:
    return panel(content, padding=padding)


def tone_color(tone: str) -> str:
    return {
        "ready": OK,
        "ok": OK,
        "warning": WARN,
        "warn": WARN,
        "danger": DANGER,
        "error": DANGER,
        "accent": ACCENT,
        "muted": MUTED,
    }.get(tone, MUTED)


def status_pill(label: str, tone: str = "neutral") -> ft.Container:
    """Compact status chip with text plus color, so color is never the only cue."""
    color = tone_color(tone)
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(width=7, height=7, bgcolor=color, border_radius=4),
                ft.Text(label, size=11, color=TEXT),
            ],
            spacing=6,
            tight=True,
        ),
        bgcolor=SURFACE_2,
        border=ft.Border.all(1, BORDER),
        border_radius=8,
        padding=ft.Padding(8, 5, 8, 5),
    )


def metric(label: str, value: str, detail: str = "", tone: str = "neutral") -> ft.Control:
    rows: list[ft.Control] = [
        ft.Text(label, size=11, weight=ft.FontWeight.BOLD, color=MUTED),
        ft.Text(value, size=18, weight=ft.FontWeight.BOLD, color=tone_color(tone)),
    ]
    if detail:
        rows.append(muted(detail))
    return panel(ft.Column(rows, spacing=3, tight=True), padding=12)


def stat(label: str, value: str, color: str = TEXT) -> ft.Control:
    """A compact stat tile for dashboards."""
    return panel(
        ft.Column(
            [
                ft.Text(value, size=24, weight=ft.FontWeight.BOLD, color=color),
                muted(label),
            ],
            spacing=2,
            tight=True,
        ),
        padding=14,
    )


def empty_state(
    icon: ft.IconData,
    headline: str,
    hint: str,
    action_label: str = "",
    on_action: Callable[[], None] | None = None,
) -> ft.Control:
    """A cared-for empty view: never just blank space (PRD 13.1/14.3)."""
    rows: list[ft.Control] = [
        ft.Icon(icon, size=44, color=MUTED),
        ft.Text(headline, size=16, weight=ft.FontWeight.BOLD, color=TEXT),
        muted(hint),
    ]
    if action_label and on_action is not None:
        rows.append(ft.FilledButton(action_label, on_click=lambda e: on_action()))
    return ft.Container(
        content=ft.Column(
            rows,
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment.CENTER,
        padding=48,
    )
