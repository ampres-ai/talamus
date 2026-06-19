"""Talamus workbench: Flet desktop/web UI, a thin shell over the SDK (M9/F9).

Eleven views (Home, Chat, Search, Notes, Domains, Graph, Timeline, Ingest, Review,
Ontology, Settings) built from the pure builders in ``talamus.ui.views``;
the shell only wires navigation, input fields and threading. Run with
``talamus ui`` (desktop) or ``talamus ui --web --port 8550`` (browser test mode,
F9.1). No API layer: every action calls the same SDK functions as the CLI.
"""

from __future__ import annotations

import threading
from pathlib import Path

import flet as ft

from talamus.adapters.llm import build_provider
from talamus.ask import answer_question
from talamus.config import load_or_default
from talamus.paths import TalamusPaths
from talamus.recall import read_note_text, search_notes
from talamus.services.ingestion import (
    IngestPreview,
    IngestRunResult,
    preview_ingest,
)
from talamus.services.ingestion import (
    run_ingest as run_ingest_service,
)
from talamus.services.scan import ScanActionResult, ScanPreview, preview_scan, run_scan
from talamus.ui import views

_HOME_ACTION_ALIASES = {
    "ask": "chat",
    "import": "ingest",
    "system": "settings",
    "demo": "home",
    "brains": "settings",
    "ontology": "ontology",
}


def _view_name_for_home_action(name: str) -> str:
    return _HOME_ACTION_ALIASES.get(name, name)


def _provider(paths: TalamusPaths):
    config = load_or_default(paths.config_path)
    return build_provider(config.llm_provider, config.llm_model)


def _format_ingest_preview(preview: IngestPreview) -> str:
    lines = [
        f"Target: {preview.target}",
        f"Type: {preview.target_type}",
        f"Estimated LLM calls: {preview.est_llm_calls}",
        f"Estimated input tokens: {preview.est_input_tokens}",
    ]
    if preview.requires_confirmation:
        lines.append("Confirmation required before running.")
    return "\n".join(lines)


def _format_ingest_result(result: IngestRunResult) -> str:
    parts = [
        "Ingest completed.",
        f"Notes written: {result.notes_written}",
    ]
    if result.job_id:
        parts.append(f"Job: {result.job_id} ({result.state})")
    if result.failed:
        parts.append(f"Failed items: {len(result.failed)}")
    return "\n".join(parts)


def _format_scan_preview(preview: ScanPreview) -> str:
    lines = [
        f"Repository: {preview.target_root}",
        f"Files: {preview.files}",
        f"Skipped: {preview.skipped}",
        f"Estimated LLM calls: {preview.est_llm_calls}",
        f"Estimated tokens: {preview.est_tokens}",
    ]
    if preview.secret_files:
        lines.append(f"Secret warnings: {len(preview.secret_files)} files")
    lines.append("Confirmation required before running.")
    return "\n".join(lines)


def _format_scan_result(result: ScanActionResult) -> str:
    parts = [
        "Scan completed.",
        f"State: {result.state}",
        f"Files: {result.files}",
        f"Notes written: {result.notes_written}",
    ]
    if result.job_id:
        parts.append(f"Job: {result.job_id}")
    if result.failed:
        parts.append(f"Failed items: {len(result.failed)}")
    return "\n".join(parts)


def _build(page: ft.Page, paths: TalamusPaths) -> None:
    from talamus.ui import theme

    page.title = "Talamus"
    theme.apply(page)
    content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=12)
    inspector = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    inspector_panel = ft.Container(
        content=inspector,
        width=300,
        bgcolor=theme.SURFACE,
        border=ft.Border(left=ft.BorderSide(1, theme.BORDER)),
        padding=theme.PAD,
        visible=False,
    )
    state = {"note": ""}  # the note the Graph/Timeline/inspector focus on

    def show(control: ft.Control) -> None:
        content.controls = [control]
        page.update()

    def _refresh_inspector() -> None:
        title = state["note"]
        if not title:
            inspector_panel.visible = False
            return
        inspector.controls = [
            ft.Row(
                [
                    ft.Text(title, weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(
                        ft.Icons.CLOSE,
                        icon_size=16,
                        on_click=lambda e: _close_inspector(),
                    ),
                ]
            ),
            theme.section("Sources"),
            views.build_sources_panel(paths, title),
            theme.section("Relations"),
            views.build_graph(paths, title, open_note),
            theme.section("Timeline"),
            views.build_timeline(paths, title),
        ]
        inspector_panel.visible = True

    def _close_inspector() -> None:
        inspector_panel.visible = False
        page.update()

    def open_note(title: str) -> None:
        title = title.strip().strip("<>").strip()
        state["note"] = title
        text = read_note_text(paths, title)
        if text is None:
            show(
                theme.empty_state(
                    ft.Icons.SEARCH_OFF,
                    title or "?",
                    "Note not found in this brain.",
                )
            )
            return
        body = ft.Markdown(
            views.wikilinks_to_md(text),
            selectable=True,
            extension_set=views.MD,
            on_tap_link=lambda e: open_note(str(e.data)),
        )
        actions = ft.Row(
            [
                ft.TextButton("Graph", on_click=lambda e: show_view("graph")),
                ft.TextButton("Timeline", on_click=lambda e: show_view("timeline")),
            ]
        )
        _refresh_inspector()
        show(ft.Column([views.heading(title), actions, ft.Divider(), theme.card(body)]))

    # ---------------------------------------------------------------- chat
    def chat_view() -> ft.Control:
        answer = ft.Markdown("", selectable=True, extension_set=views.MD)
        box = ft.TextField(label="Ask your memory")
        as_of = ft.TextField(label="as-of (optional: 2026, 2026-01, ...)", width=260)

        def ask() -> None:
            question = (box.value or "").strip()
            if not question:
                return
            answer.value = "..."
            page.update()

            def work() -> None:
                try:
                    if (as_of.value or "").strip():
                        from talamus.ask import answer_from_items
                        from talamus.temporal import parse_when
                        from talamus.timeline import note_as_of

                        parse_when(as_of.value.strip())  # validate early
                        items = []
                        for hit in search_notes(paths, question, limit=5):
                            version = note_as_of(paths, hit["title"], as_of.value.strip())
                            if version is None:
                                continue
                            joiner = chr(10)
                            body = joiner.join(
                                str(v) for v in version.get("body_sections", {}).values()
                            )
                            items.append(
                                {
                                    "route": "as-of",
                                    "path": f"[as-of {as_of.value}] {hit['title']}",
                                    "content": f"{version.get('summary', '')}{joiner}{body}",
                                }
                            )
                        if items:
                            answer.value = answer_from_items(question, items, _provider(paths))
                        else:
                            answer.value = f"No knowledge in the brain as of {as_of.value}."
                    else:
                        answer.value = answer_question(paths, question, _provider(paths))
                except Exception as exc:  # surface engine errors instead of hanging
                    answer.value = f"**Engine error:** {exc}"
                page.update()

            threading.Thread(target=work, daemon=True).start()

        box.on_submit = lambda e: ask()
        return ft.Column(
            [views.heading("Memory chat"), box, as_of, ft.Divider(), answer], spacing=10
        )

    # ---------------------------------------------------------------- search
    def search_view() -> ft.Control:
        results_box = ft.Column(spacing=4)
        query = ft.TextField(label="Search the brain")

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
            ] or [ft.Text("No relevant notes.")]
            page.update()

        query.on_submit = lambda e: run_search()
        return ft.Column([views.heading("Search"), query, results_box], spacing=10)

    # ---------------------------------------------------------------- ingest
    def ingest_view() -> ft.Control:
        target = ft.TextField(label="File, folder, or URL (or . for this repo)")
        output = ft.Text("", selectable=True)
        confirmed = {"target": "", "kind": ""}

        def _target_value() -> str:
            return (target.value or ".").strip() or "."

        def _local_or_url(value: str) -> str:
            if "://" in value:
                return value
            path = Path(value)
            return str(path if path.is_absolute() else paths.project_root / path)

        def dry_run() -> None:
            value = _target_value()
            try:
                if value == ".":
                    scan_preview = preview_scan(paths.project_root, paths.project_root)
                    if scan_preview.success and scan_preview.data is not None:
                        confirmed.update({"target": value, "kind": "scan"})
                        output.value = _format_scan_preview(scan_preview.data)
                    else:
                        output.value = scan_preview.message
                else:
                    service_target = _local_or_url(value)
                    ingest_preview = preview_ingest(paths.project_root, service_target)
                    if ingest_preview.success and ingest_preview.data is not None:
                        confirmed.update({"target": value, "kind": "ingest"})
                        output.value = _format_ingest_preview(ingest_preview.data)
                    else:
                        output.value = ingest_preview.message
            except Exception as exc:
                output.value = f"Error: {exc}"
            page.update()

        def run_ingest() -> None:
            value = _target_value()
            if not value:
                return
            output.value = "Ingesting..."
            page.update()

            def work() -> None:
                try:
                    if value == ".":
                        scan_result = run_scan(
                            paths.project_root,
                            paths.project_root,
                            lambda: _provider(paths),
                            confirmed=confirmed == {"target": value, "kind": "scan"},
                        )
                        if scan_result.data is not None and isinstance(
                            scan_result.data, ScanPreview
                        ):
                            output.value = _format_scan_preview(scan_result.data)
                        elif scan_result.data is not None and isinstance(
                            scan_result.data, ScanActionResult
                        ):
                            output.value = _format_scan_result(scan_result.data)
                        else:
                            output.value = scan_result.message
                    else:
                        service_target = _local_or_url(value)
                        ingest_result = run_ingest_service(
                            paths.project_root,
                            service_target,
                            _provider(paths),
                            confirmed=confirmed == {"target": value, "kind": "ingest"},
                        )
                        if ingest_result.data is not None and isinstance(
                            ingest_result.data, IngestPreview
                        ):
                            output.value = _format_ingest_preview(ingest_result.data)
                        elif ingest_result.data is not None and isinstance(
                            ingest_result.data, IngestRunResult
                        ):
                            output.value = _format_ingest_result(ingest_result.data)
                        else:
                            output.value = ingest_result.message
                except Exception as exc:
                    output.value = f"Error: {exc}"
                page.update()

            threading.Thread(target=work, daemon=True).start()

        buttons = ft.Row(
            [
                ft.TextButton("Preview cost", on_click=lambda e: dry_run()),
                ft.ElevatedButton("Run with consent", on_click=lambda e: run_ingest()),
            ]
        )
        return ft.Column([views.heading("Ingest"), target, buttons, output], spacing=10)

    # ---------------------------------------------------------------- graph
    def _graph() -> ft.Control:
        from talamus.ui.graph import build_graph_canvas

        return build_graph_canvas(paths, state["note"], open_note, page=page)

    # ---------------------------------------------------------------- routing
    builders: dict[str, object] = {}

    def show_view(name: str) -> None:
        name = _view_name_for_home_action(name)
        builder = builders[name]
        show(builder())  # type: ignore[operator]

    builders.update(
        {
            "home": lambda: views.build_home(paths, show_view),
            "chat": chat_view,
            "search": search_view,
            "notes": lambda: views.build_notes(paths, open_note),
            "domains": lambda: views.build_domains(paths, open_note),
            "graph": lambda: _graph(),
            "timeline": lambda: views.build_timeline(paths, state["note"]),
            "ingest": ingest_view,
            "review": lambda: views.build_review(paths, lambda: show_view("review")),
            "ontology": lambda: views.build_ontology_lab(paths, lambda: show_view("ontology")),
            "settings": lambda: views.build_settings(paths),
        }
    )
    order = list(builders)
    destinations = [
        ("home", ft.Icons.HOME),
        ("chat", ft.Icons.CHAT),
        ("search", ft.Icons.SEARCH),
        ("notes", ft.Icons.DESCRIPTION),
        ("domains", ft.Icons.ACCOUNT_TREE),
        ("graph", ft.Icons.HUB),
        ("timeline", ft.Icons.HISTORY),
        ("ingest", ft.Icons.UPLOAD_FILE),
        ("review", ft.Icons.CHECKLIST),
        ("ontology", ft.Icons.SCHEMA),
        ("settings", ft.Icons.SETTINGS),
    ]
    from talamus.ui import theme as _theme

    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        bgcolor=_theme.SURFACE,
        indicator_color=_theme.SURFACE_2,
        destinations=[
            ft.NavigationRailDestination(icon=icon, label=name.capitalize())
            for name, icon in destinations
        ],
        on_change=lambda e: show_view(order[e.control.selected_index or 0]),
    )
    main_pane = ft.Container(content=content, expand=True, padding=_theme.PAD * 1.5)
    page.add(ft.Row([rail, main_pane, inspector_panel], expand=True, spacing=0))
    show_view("home")


def run_app(paths: TalamusPaths, web: bool = False, port: int = 8550) -> None:
    """Launch the workbench: native window, or browser mode for deterministic
    testing/screenshots (``talamus ui --web --port N``)."""
    target = lambda page: _build(page, paths)  # noqa: E731
    if web:
        ft.app(target=target, view=ft.AppView.WEB_BROWSER, port=port)
    else:
        ft.app(target=target)
