"""Flet desktop/web/mobile UI for Talamus — a thin layer over the SDK.

Run with `talamus ui`. Package native installers with `flet build <target>`.
The UI calls the SDK directly (no API); all logic lives in the tested core.
"""

from __future__ import annotations

import re
import threading

import flet as ft

from talamus.adapters.llm import build_provider
from talamus.ask import answer_question
from talamus.config import load_or_default
from talamus.domains import load_overview
from talamus.paths import TalamusPaths
from talamus.recall import read_note_text, search_notes

_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_MD = ft.MarkdownExtensionSet.GITHUB_WEB


def _wikilinks_to_md(text: str) -> str:
    """Turn Obsidian [[Target]] / [[Target|Label]] into clickable Markdown links.

    The target is wrapped in angle brackets so titles with spaces stay a single URL
    (`[Label](<Vector Store>)`), which the tap handler then normalizes.
    """
    return _WIKILINK.sub(lambda m: f"[{m.group(2) or m.group(1)}](<{m.group(1).strip()}>)", text)


def _provider(paths: TalamusPaths):
    config = load_or_default(paths.config_path)
    return build_provider(config.llm_provider, config.llm_model)


def _build(page: ft.Page, paths: TalamusPaths) -> None:
    page.title = "Talamus"
    page.theme_mode = ft.ThemeMode.SYSTEM
    content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=12)

    def show(controls: list) -> None:
        content.controls = controls
        page.update()

    def heading(text: str) -> ft.Control:
        return ft.Text(text, size=24, weight=ft.FontWeight.BOLD)

    def open_note(title: str) -> None:
        title = title.strip().strip("<>").strip()
        text = read_note_text(paths, title)
        if text is None:
            show([heading(title or "?"), ft.Text("Scheda non trovata.")])
            return
        body = ft.Markdown(
            _wikilinks_to_md(text),
            selectable=True,
            extension_set=_MD,
            on_tap_link=lambda e: open_note(str(e.data)),
        )
        show([heading(title), ft.Divider(), body])

    def search_view() -> None:
        results_box = ft.Column(spacing=4)
        query = ft.TextField(label="Cerca nel brain")

        def run_search() -> None:
            if not (query.value or "").strip():
                return
            results = search_notes(paths, query.value or "")
            results_box.controls = [
                ft.ListTile(
                    title=ft.Text(r["title"]),
                    subtitle=ft.Text(r["summary"]),
                    on_click=lambda e, t=r["title"]: open_note(t),
                )
                for r in results
            ] or [ft.Text("Nessuna scheda pertinente.")]
            page.update()

        query.on_submit = lambda e: run_search()
        show([heading("Cerca"), query, results_box])

    def chat_view() -> None:
        answer = ft.Markdown("", selectable=True, extension_set=_MD)
        box = ft.TextField(label="Chiedi alla tua memoria")

        def ask() -> None:
            question = (box.value or "").strip()
            if not question:
                return
            answer.value = "…"
            page.update()

            def work() -> None:
                try:
                    answer.value = answer_question(paths, question, _provider(paths))
                except Exception as exc:  # surface engine/config errors instead of hanging on "…"
                    answer.value = f"**Errore dal motore:** {exc}"
                page.update()

            threading.Thread(target=work, daemon=True).start()

        box.on_submit = lambda e: ask()
        show([heading("Chat sulla memoria"), box, ft.Divider(), answer])

    def domains_view() -> None:
        overview = load_overview(paths)
        controls: list = [heading("Domini")]
        if not overview:
            controls.append(ft.Text("Nessun dominio ancora. Esegui `talamus overview`."))
        for domain in overview:
            controls.append(ft.Text(domain["name"], size=18, weight=ft.FontWeight.BOLD))
            if domain.get("description"):
                controls.append(ft.Text(domain["description"]))
            for member in domain.get("members", []):
                controls.append(ft.TextButton(member, on_click=lambda e, t=member: open_note(t)))
        show(controls)

    views = [chat_view, search_view, domains_view]
    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.CHAT, label="Chat"),
            ft.NavigationRailDestination(icon=ft.Icons.SEARCH, label="Cerca"),
            ft.NavigationRailDestination(icon=ft.Icons.ACCOUNT_TREE, label="Domini"),
        ],
        on_change=lambda e: views[e.control.selected_index or 0](),
    )
    page.add(ft.Row([rail, ft.VerticalDivider(width=1), content], expand=True))
    chat_view()


def run_app(paths: TalamusPaths) -> None:
    ft.app(target=lambda page: _build(page, paths))
