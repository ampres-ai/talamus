"""Talamus workbench: Flet desktop/web UI, a thin shell over the SDK (M9/F9).

The primary chrome is task-first (Home, Ask, Library, Import, Graph, Review,
Ontology, Brains, System) while the implementation remains a thin wrapper over
the pure builders in ``talamus.ui.views``. Run with ``talamus ui`` (desktop) or
``talamus ui --web --port 8550`` (browser test mode, F9.1). No API layer: every
action calls the same SDK functions as the CLI.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import flet as ft

from talamus.adapters.llm import build_provider
from talamus.ask import answer_question
from talamus.config import load_or_default, resolve_language
from talamus.paths import TalamusPaths
from talamus.routing import StaticRouter
from talamus.services.ingestion import (
    IngestPreview,
    IngestRunResult,
    preview_ingest,
)
from talamus.services.ingestion import (
    run_ingest as run_ingest_service,
)
from talamus.services.query import read_note, search_brain
from talamus.services.scan import ScanActionResult, ScanPreview, preview_scan, run_scan
from talamus.ui import views


@dataclass(frozen=True)
class NavDestination:
    view: str
    label: str
    icon: ft.IconData


PRIMARY_NAV_DESTINATIONS = [
    NavDestination("home", "Home", ft.Icons.HOME),
    NavDestination("ask", "Ask", ft.Icons.CHAT),
    NavDestination("library", "Library", ft.Icons.DESCRIPTION),
    NavDestination("import", "Import", ft.Icons.UPLOAD_FILE),
    NavDestination("graph", "Graph", ft.Icons.HUB),
    NavDestination("review", "Review", ft.Icons.CHECKLIST),
    NavDestination("ontology", "Ontology", ft.Icons.SCHEMA),
    NavDestination("brains", "Brains", ft.Icons.ACCOUNT_TREE),
    NavDestination("system", "System", ft.Icons.SETTINGS),
]

_HOME_ACTION_ALIASES = {
    "ask": "chat",
    "library": "notes",
    "import": "ingest",
    "system": "settings",
    "demo": "home",
    "brains": "settings",
    "ontology": "ontology",
}


def _view_name_for_home_action(name: str) -> str:
    return _HOME_ACTION_ALIASES.get(name, name)


def _title_for_view(name: str) -> str:
    for destination in PRIMARY_NAV_DESTINATIONS:
        if destination.view == name:
            return destination.label
    for destination in PRIMARY_NAV_DESTINATIONS:
        if _view_name_for_home_action(destination.view) == name:
            return destination.label
    return name.capitalize()


def _build_content_slot() -> ft.Container:
    from talamus.ui import theme

    return ft.Container(bgcolor=theme.BG, padding=0)


def _build_top_bar(
    main_title: ft.Control,
    main_subtitle: ft.Control,
    mobile_nav: ft.Control | None = None,
) -> ft.Container:
    from talamus.ui import theme

    controls: list[ft.Control] = [ft.Column([main_title, main_subtitle], spacing=2)]
    if mobile_nav is not None:
        controls.append(mobile_nav)
    return theme.panel(
        ft.Column(controls, spacing=8),
        padding=12,
    )


def _build_main_pane(top_bar: ft.Control, content: ft.Control) -> ft.Container:
    from talamus.ui import theme

    return theme.panel(
        ft.Column(
            controls=[top_bar, content],
            expand=True,
            spacing=theme.GAP,
        ),
        expand=True,
        bgcolor=theme.BG,
        padding=theme.PAD,
    )


INSPECTOR_COLLAPSE_WIDTH = 1040
SIDEBAR_COLLAPSE_WIDTH = 720


def _show_inspector_for_width(width: int | float | str | None) -> bool:
    if width is None:
        return True
    if not isinstance(width, (int, float, str)):
        return True
    try:
        width_value = float(width)
    except ValueError:
        return True
    return width_value >= INSPECTOR_COLLAPSE_WIDTH


def _show_sidebar_for_width(width: int | float | str | None) -> bool:
    if width is None:
        return True
    if not isinstance(width, (int, float, str)):
        return True
    try:
        width_value = float(width)
    except ValueError:
        return True
    return width_value >= SIDEBAR_COLLAPSE_WIDTH


def _provider(paths: TalamusPaths):
    config = load_or_default(paths.config_path)
    return build_provider(config.llm_provider, config.llm_model)


def _format_import_guardrail() -> str:
    return (
        "Preview cost first. "
        "No bulk LLM action before consent. "
        "Jobs and partial failures stay visible."
    )


def _format_import_consent_status(target: str, confirmed: dict[str, str]) -> str:
    current = target.strip() or "."
    confirmed_target = confirmed.get("target", "")
    confirmed_kind = confirmed.get("kind", "")
    if not confirmed_target:
        return "Preview required. Run with consent is blocked until Preview cost succeeds."
    if confirmed_target != current:
        return "Target changed. Preview cost again before running."
    preview = "scan preview" if confirmed_kind == "scan" else "ingest preview"
    return f"Consent ready from {preview}. Run with consent will use this target."


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


def _format_ask_token_promise(question: str, as_of: str) -> str:
    from talamus.budget import context_budget, estimate_tokens

    text = "\n".join(part for part in (question.strip(), as_of.strip()) if part)
    prompt_tokens = estimate_tokens(text) if text else 0
    return (
        "No LLM call until Ask. "
        f"Current question text: ~{prompt_tokens} tokens; "
        f"answer context cap: {context_budget()} tokens."
    )


def _format_ask_language_promise(language: str) -> str:
    user_language = language.strip() or "your language"
    return (
        f"Language-native recall: notes stay in {user_language}; "
        "context is built from your prose and citations stay traceable."
    )


def _format_search_trace(query: str, result_count: int) -> str:
    if not query.strip():
        return "Local search trace appears after a query. No LLM call."
    return f"Local search: {result_count} results for {query.strip()!r}. No LLM call."


def _format_answer_trace(trace: dict) -> str:
    if not trace:
        return "Trace appears after an answer."
    lines = [f"Route: {trace.get('route', 'unknown')}"]
    if trace.get("as_of"):
        lines.append(f"As-of: {trace['as_of']}")
    if "context_tokens" in trace:
        lines.append(f"Context: {trace['context_tokens']} tokens")
    items = trace.get("items_read") or []
    lines.append(f"Notes read: {len(items)}")
    if items:
        note_names = [Path(str(item)).stem or str(item) for item in items[:4]]
        suffix = f" (+{len(items) - 4} more)" if len(items) > 4 else ""
        lines.append(f"Traceable notes: {', '.join(note_names)}{suffix}")
    domains = trace.get("domains_chosen") or []
    if domains:
        lines.append(f"Domains: {', '.join(str(domain) for domain in domains)}")
    if trace.get("areas_chosen"):
        lines.append(f"Areas: {', '.join(str(area) for area in trace['areas_chosen'])}")
    if trace.get("routing_fallback"):
        lines.append("Routing fallback: yes")
    if trace.get("extra_items"):
        lines.append(f"Extra context items: {trace['extra_items']}")
    return "\n".join(lines)


def _build(page: ft.Page, paths: TalamusPaths) -> None:
    from talamus.ui import theme

    page.title = "Talamus"
    theme.apply(page)
    content = _build_content_slot()
    main_title = ft.Text("Home", size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT)
    main_subtitle = ft.Text(str(paths.project_root), size=12, color=theme.MUTED)
    mobile_nav = ft.Row([], wrap=True, spacing=6, run_spacing=6, visible=False)
    top_bar = _build_top_bar(main_title, main_subtitle, mobile_nav)

    inspector = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    inspector_panel = theme.panel(
        inspector,
        width=330,
        bgcolor=theme.SIDEBAR,
        padding=theme.PAD,
    )
    sidebar = theme.panel(
        ft.Column([], spacing=10),
        width=236,
        bgcolor=theme.SIDEBAR,
        padding=14,
    )
    state = {
        "note": "",  # the note the Graph/Timeline/inspector focus on
        "view": "home",
    }

    def _sync_shell_width() -> None:
        sidebar_visible = _show_sidebar_for_width(page.width)
        sidebar.visible = sidebar_visible
        mobile_nav.visible = not sidebar_visible
        # The inspector is contextual: it only appears once something is selected,
        # so browsing views (Home/Ask/Library/Graph) get the full width.
        inspector_panel.visible = _show_inspector_for_width(page.width) and bool(state["note"])

    def _on_resize(e) -> None:
        _sync_shell_width()
        page.update()

    page.on_resize = _on_resize

    def show(control: ft.Control) -> None:
        _sync_shell_width()
        content.content = control
        page.update()

    def _nav_item(destination: NavDestination) -> ft.Control:
        selected = state["view"] == destination.view
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        destination.icon, size=17, color=theme.TEXT if selected else theme.MUTED
                    ),
                    ft.Text(
                        destination.label,
                        size=13,
                        weight=ft.FontWeight.BOLD if selected else ft.FontWeight.NORMAL,
                        color=theme.TEXT if selected else theme.MUTED,
                    ),
                ],
                spacing=9,
            ),
            bgcolor=theme.SURFACE_2 if selected else theme.SURFACE,
            border=ft.Border.all(1, theme.BORDER),
            border_radius=8,
            padding=ft.Padding(10, 9, 10, 9),
            on_click=lambda e, view=destination.view: show_view(view),
        )

    def _mobile_nav_item(destination: NavDestination) -> ft.Control:
        selected = state["view"] == destination.view
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        destination.icon, size=15, color=theme.TEXT if selected else theme.MUTED
                    ),
                    ft.Text(
                        destination.label,
                        size=12,
                        weight=ft.FontWeight.BOLD if selected else ft.FontWeight.NORMAL,
                        color=theme.TEXT if selected else theme.MUTED,
                    ),
                ],
                spacing=5,
                tight=True,
            ),
            bgcolor=theme.SURFACE_2 if selected else theme.BG,
            border=ft.Border.all(1, theme.BORDER),
            border_radius=8,
            padding=ft.Padding(8, 7, 8, 7),
            on_click=lambda e, view=destination.view: show_view(view),
        )

    def _refresh_sidebar() -> None:
        mobile_nav.controls = [
            _mobile_nav_item(destination) for destination in PRIMARY_NAV_DESTINATIONS
        ]
        sidebar.content = ft.Column(
            [
                ft.Column(
                    [
                        ft.Text("Talamus", size=19, weight=ft.FontWeight.BOLD, color=theme.TEXT),
                        theme.muted(paths.project_root.name or "brain", size=11),
                    ],
                    spacing=3,
                ),
                ft.Divider(height=1, color=theme.BORDER),
                *[_nav_item(destination) for destination in PRIMARY_NAV_DESTINATIONS],
                ft.Container(expand=True),
            ],
            spacing=10,
            expand=True,
        )

    def _refresh_topbar(canonical_name: str) -> None:
        main_title.value = _title_for_view(canonical_name)
        main_subtitle.value = paths.project_root.name or "brain"

    def _refresh_inspector() -> None:
        title = state["note"]
        if not title:
            inspector.controls = [
                theme.section("Inspector"),
                ft.Text("Context follows selection", size=19, weight=ft.FontWeight.BOLD),
                theme.muted(
                    "Select a note, source, job, review item, relation, brain, or engine "
                    "to see evidence and safe actions here."
                ),
                ft.Divider(height=1, color=theme.BORDER),
                theme.section("Examples"),
                theme.panel(ft.Text("Sources and citations", size=12), padding=10),
                theme.panel(ft.Text("Job progress and logs", size=12), padding=10),
                theme.panel(ft.Text("Review decisions", size=12), padding=10),
                theme.panel(ft.Text("CLI-equivalent trace", size=12), padding=10),
            ]
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
            theme.section("Verification"),
            views.build_verification_panel(paths, title),
            theme.section("Relations"),
            views.build_graph(paths, title, open_note),
            theme.section("Timeline"),
            views.build_timeline(paths, title),
        ]

    def _close_inspector() -> None:
        state["note"] = ""
        _refresh_inspector()
        _sync_shell_width()
        page.update()

    def open_note(title: str) -> None:
        title = title.strip().strip("<>").strip()
        state["note"] = title
        note_result = read_note(paths.project_root, title)
        if not note_result.success or note_result.data is None or not note_result.data.markdown:
            show(
                theme.empty_state(
                    ft.Icons.SEARCH_OFF,
                    title or "?",
                    note_result.message or "Note not found in this brain.",
                )
            )
            return
        body = ft.Markdown(
            views.wikilinks_to_md(note_result.data.markdown),
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
        cost_line = ft.Text(
            _format_ask_token_promise("", ""),
            size=12,
            color=theme.MUTED,
        )
        trace_text = ft.Text(
            _format_answer_trace({}),
            size=12,
            color=theme.TEXT,
            selectable=True,
        )
        language_line = ft.Text(
            _format_ask_language_promise(resolve_language(load_or_default(paths.config_path))),
            size=12,
            color=theme.MUTED,
        )
        run_button = ft.ElevatedButton("Ask", icon=ft.Icons.PSYCHOLOGY)

        def refresh_cost() -> None:
            cost_line.value = _format_ask_token_promise(box.value or "", as_of.value or "")

        def ask() -> None:
            question = (box.value or "").strip()
            if not question:
                return
            refresh_cost()
            answer.value = "..."
            trace_text.value = "Building route and context..."
            page.update()

            def work() -> None:
                trace: dict = {}
                try:
                    if (as_of.value or "").strip():
                        from talamus.ask import answer_from_items
                        from talamus.temporal import parse_when
                        from talamus.timeline import note_as_of

                        as_of_value = as_of.value.strip()
                        parse_when(as_of_value)  # validate early
                        items = []
                        search_result = search_brain(paths.project_root, question, limit=5)
                        hits = (
                            search_result.data.hits
                            if search_result.success and search_result.data
                            else []
                        )
                        for hit in hits:
                            version = note_as_of(paths, hit.title, as_of_value)
                            if version is None:
                                continue
                            joiner = chr(10)
                            body = joiner.join(
                                str(v) for v in version.get("body_sections", {}).values()
                            )
                            items.append(
                                {
                                    "route": "as-of",
                                    "path": f"[as-of {as_of_value}] {hit.title}",
                                    "content": f"{version.get('summary', '')}{joiner}{body}",
                                }
                            )
                        trace["route"] = "as-of"
                        trace["as_of"] = as_of_value
                        if items:
                            answer.value = answer_from_items(
                                question, items, StaticRouter(_provider(paths)), trace=trace
                            )
                        else:
                            trace["items_read"] = []
                            trace["context_tokens"] = 0
                            answer.value = f"No knowledge in the brain as of {as_of_value}."
                    else:
                        answer.value = answer_question(
                            paths, question, StaticRouter(_provider(paths)), trace=trace
                        )
                    trace_text.value = _format_answer_trace(trace)
                except Exception as exc:  # surface engine errors instead of hanging
                    answer.value = f"**Engine error:** {exc}"
                    trace_text.value = f"Trace unavailable: {exc}"
                page.update()

            threading.Thread(target=work, daemon=True).start()

        def refresh_cost_and_update(e) -> None:
            refresh_cost()
            page.update()

        box.on_submit = lambda e: ask()
        box.on_change = refresh_cost_and_update
        as_of.on_change = refresh_cost_and_update
        run_button.on_click = lambda e: ask()
        return ft.Column(
            [
                views.heading("Memory chat"),
                theme.panel(
                    ft.Column(
                        [
                            theme.section("Token promise"),
                            cost_line,
                            theme.muted(
                                "The answer may call your selected engine only after this action."
                            ),
                        ],
                        spacing=6,
                    ),
                    padding=12,
                ),
                theme.panel(
                    ft.Column(
                        [
                            theme.section("Language moat"),
                            language_line,
                        ],
                        spacing=6,
                    ),
                    padding=12,
                ),
                ft.Row([box, as_of, run_button], wrap=True, spacing=10, run_spacing=10),
                theme.panel(
                    ft.Column([theme.section("Readable trace"), trace_text], spacing=6),
                    padding=12,
                ),
                ft.Divider(),
                answer,
            ],
            spacing=10,
        )

    # ---------------------------------------------------------------- search
    def search_view() -> ft.Control:
        results_box = ft.Column(spacing=4)
        query = ft.TextField(label="Search the brain")
        trace = ft.Text(
            _format_search_trace("", 0),
            size=12,
            color=theme.MUTED,
            selectable=True,
        )

        def run_search() -> None:
            if not (query.value or "").strip():
                return
            result = search_brain(paths.project_root, query.value or "")
            hits = result.data.hits if result.success and result.data is not None else []
            trace.value = _format_search_trace(query.value or "", len(hits))
            if result.success:
                results_box.controls = [
                    ft.ListTile(
                        title=ft.Text(hit.title),
                        subtitle=ft.Text(hit.summary),
                        on_click=lambda e, t=hit.title: open_note(t),
                    )
                    for hit in hits
                ] or [ft.Text("No relevant notes.")]
            else:
                results_box.controls = [ft.Text(result.message)]
            page.update()

        query.on_submit = lambda e: run_search()
        return ft.Column(
            [
                views.heading("Search"),
                theme.panel(ft.Column([theme.section("Retrieval trace"), trace], spacing=6)),
                query,
                results_box,
            ],
            spacing=10,
        )

    # ---------------------------------------------------------------- ingest
    def ingest_view() -> ft.Control:
        from talamus.ui import theme

        target = ft.TextField(label="File, folder, or URL (or . for this repo)")
        output = ft.Text("", selectable=True)
        confirmed = {"target": "", "kind": ""}
        consent_status = ft.Text(
            _format_import_consent_status(".", confirmed),
            size=12,
            color=theme.MUTED,
            selectable=True,
        )

        def _target_value() -> str:
            return (target.value or ".").strip() or "."

        def _refresh_consent_status() -> None:
            consent_status.value = _format_import_consent_status(_target_value(), confirmed)

        def _local_or_url(value: str) -> str:
            if "://" in value:
                return value
            path = Path(value)
            return str(path if path.is_absolute() else paths.project_root / path)

        def dry_run() -> None:
            value = _target_value()
            confirmed.update({"target": "", "kind": ""})
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
            _refresh_consent_status()
            page.update()

        def run_ingest() -> None:
            value = _target_value()
            if not value:
                return
            output.value = "Ingesting..."
            _refresh_consent_status()
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
                            confirmed.update({"target": value, "kind": "scan"})
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
                            confirmed.update({"target": value, "kind": "ingest"})
                            output.value = _format_ingest_preview(ingest_result.data)
                        elif ingest_result.data is not None and isinstance(
                            ingest_result.data, IngestRunResult
                        ):
                            output.value = _format_ingest_result(ingest_result.data)
                        else:
                            output.value = ingest_result.message
                except Exception as exc:
                    output.value = f"Error: {exc}"
                _refresh_consent_status()
                page.update()

            threading.Thread(target=work, daemon=True).start()

        buttons = ft.Row(
            [
                ft.TextButton("Preview cost", on_click=lambda e: dry_run()),
                ft.ElevatedButton("Run with consent", on_click=lambda e: run_ingest()),
            ]
        )
        guardrail = theme.panel(
            ft.Column(
                [
                    theme.section("Import guardrail"),
                    theme.muted(_format_import_guardrail()),
                ],
                spacing=6,
                tight=True,
            ),
            padding=12,
        )
        status_panel = theme.panel(
            ft.Column([theme.section("Consent status"), consent_status], spacing=6),
            padding=12,
        )

        def refresh_consent_and_update(e) -> None:
            _refresh_consent_status()
            page.update()

        target.on_change = refresh_consent_and_update
        return ft.Column(
            [views.heading("Ingest"), guardrail, status_panel, target, buttons, output],
            spacing=10,
        )

    # ---------------------------------------------------------------- graph
    def _graph() -> ft.Control:
        from talamus.ui.graph import build_graph_canvas

        return build_graph_canvas(paths, state["note"], open_note, page=page)

    def home_view() -> ft.Control:
        try:
            return views.build_home(paths, show_view)
        except Exception as exc:
            return theme.panel(
                ft.Column(
                    [
                        ft.Text("Readiness failed", weight=ft.FontWeight.BOLD),
                        theme.muted(str(exc)),
                    ],
                    spacing=6,
                ),
                padding=12,
            )

    # ---------------------------------------------------------------- routing
    builders: dict[str, object] = {}

    def show_view(name: str) -> None:
        canonical_name = name
        resolved_name = _view_name_for_home_action(name)
        builder = builders[resolved_name]
        state["view"] = canonical_name
        _refresh_topbar(canonical_name)
        _refresh_sidebar()
        show(builder())  # type: ignore[operator]

    builders.update(
        {
            "home": home_view,
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
    _refresh_sidebar()
    _refresh_inspector()
    _sync_shell_width()
    main_pane = _build_main_pane(top_bar, content)
    page.add(
        ft.Container(
            content=ft.Row(
                [sidebar, main_pane, inspector_panel],
                expand=True,
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            expand=True,
            bgcolor=theme.BG,
        )
    )
    show_view("home")


def run_app(paths: TalamusPaths, web: bool = False, port: int = 8550) -> None:
    """Launch the workbench: native window, or browser mode for deterministic
    testing/screenshots (``talamus ui --web --port N``)."""
    target = lambda page: _build(page, paths)  # noqa: E731
    if web:
        ft.app(target=target, view=ft.AppView.WEB_BROWSER, port=port)
    else:
        ft.app(target=target)
