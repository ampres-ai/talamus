"""Workbench views — pure builders over the SDK, testable without a window (M9/F9).

Every ``build_*`` function takes the brain paths (plus callbacks where needed) and
returns a Flet control tree. No business logic lives here: views call the same SDK
functions the CLI uses (F9 acceptance: no duplicated logic). Builders are
constructible headless, which is what the smoke tests exercise; rendering is
verified at runtime via ``talamus ui`` (desktop) or ``talamus ui --web``.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable

import flet as ft

from talamus.domains import load_overview
from talamus.paths import TalamusPaths
from talamus.services.brains import list_brains, set_registered_brain_flags
from talamus.services.diagnostics import inspect_diagnostics
from talamus.services.engines import (
    list_engines,
    load_engine_settings,
    save_anthropic_api_key,
    update_engine_settings,
)
from talamus.services.graph import GraphNeighbor, list_graph_neighbors
from talamus.services.integrations import (
    build_hook_snippet,
    inspect_integrations,
    install_mcp_config,
)
from talamus.services.library import get_library_note, list_library_notes
from talamus.services.ontology import (
    apply_ontology_candidate,
    get_ontology_status,
    list_ontology_candidates,
    reject_ontology_candidate,
)
from talamus.services.readiness import EngineReadiness, NextAction, inspect_readiness
from talamus.services.review import apply_review_item, list_review_items, reject_review_item
from talamus.temporal import note_timeline

_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
MD = ft.MarkdownExtensionSet.GITHUB_WEB

OpenNote = Callable[[str], None]


def wikilinks_to_md(text: str) -> str:
    """Turn Obsidian [[Target]] / [[Target|Label]] into clickable Markdown links."""
    return _WIKILINK.sub(lambda m: f"[{m.group(2) or m.group(1)}](<{m.group(1).strip()}>)", text)


def heading(text: str) -> ft.Control:
    return ft.Text(text, size=22, weight=ft.FontWeight.BOLD)


def subtle(text: str) -> ft.Control:
    return ft.Text(text, size=12, opacity=0.7)


# ------------------------------------------------------------------- home


def build_home(paths: TalamusPaths, on_action: Callable[[str], None] | None = None) -> ft.Control:
    from talamus.ui import theme

    report = inspect_readiness(root=str(paths.project_root))
    tiles = ft.Row(
        [
            theme.stat("notes", str(report.notes)),
            theme.stat("sources", str(report.sources)),
            theme.stat(
                "review",
                str(report.reviews_pending),
                color=theme.WARN if report.reviews_pending else theme.TEXT,
            ),
            theme.stat(
                "job",
                str(report.jobs_active),
                color=theme.WARN if report.jobs_active else theme.TEXT,
            ),
            theme.stat("index", report.index_backend, color=theme.ACCENT),
        ],
        wrap=True,
        spacing=theme.GAP,
    )
    rows: list[ft.Control] = [
        heading("Talamus"),
        theme.muted(report.root),
        tiles,
        _moat_status_panel(report),
    ]
    if not report.config_exists:
        rows.append(
            theme.empty_state(
                ft.Icons.PSYCHOLOGY_ALT,
                "No brain selected",
                "Open an existing brain, try the demo, or create a new brain when you choose. "
                "This screen does not create files.",
            )
        )

    rows.append(theme.section("System status"))
    rows.extend(_engine_card(engine) for engine in report.engines)

    rows.append(theme.section("Next steps"))
    if report.next_actions:
        rows.extend(_next_action_card(action, on_action) for action in report.next_actions)
    else:
        rows.append(
            theme.card(
                ft.Column(
                    [
                        ft.Text("Ready", weight=ft.FontWeight.BOLD),
                        theme.muted("This brain is ready for questions."),
                    ],
                    spacing=4,
                ),
                padding=12,
            )
        )
    return ft.Column(rows, spacing=14)


def _moat_status_panel(report: object) -> ft.Control:
    from talamus.ui import theme

    notes = int(getattr(report, "notes", 0) or 0)
    sources = int(getattr(report, "sources", 0) or 0)
    reviews = int(getattr(report, "reviews_pending", 0) or 0)
    domains = int(getattr(report, "overview_domains", 0) or 0)
    candidates = int(getattr(report, "ontology_candidates", 0) or 0)
    budget = os.environ.get("TALAMUS_CONTEXT_BUDGET", "6000")
    items = [
        ("Time", "as-of ready" if notes else "waiting for notes"),
        ("Meaning", f"{domains} domains, {candidates} candidates"),
        ("Verifiability", f"{sources} sources, {reviews} reviews"),
        ("Cost", f"{budget} token budget"),
    ]
    return theme.card(
        ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(label, size=11, weight=ft.FontWeight.BOLD, color=theme.MUTED),
                        ft.Text(value, size=13, color=theme.TEXT),
                    ],
                    spacing=2,
                    tight=True,
                )
                for label, value in items
            ],
            wrap=True,
            spacing=theme.GAP * 1.5,
            run_spacing=theme.GAP,
        ),
        padding=12,
    )


def _engine_card(engine: EngineReadiness) -> ft.Control:
    from talamus.ui import theme

    marker = "selected" if engine.configured else engine.status
    return theme.card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(engine.label, weight=ft.FontWeight.BOLD),
                        theme.muted(marker),
                    ],
                    spacing=8,
                    wrap=True,
                ),
                theme.muted(engine.detail),
            ],
            spacing=4,
        ),
        padding=12,
    )


def _next_action_card(
    action: NextAction, on_action: Callable[[str], None] | None = None
) -> ft.Control:
    from talamus.ui import theme

    controls: list[ft.Control] = [
        ft.Text(action.label, weight=ft.FontWeight.BOLD),
        theme.muted(action.detail),
    ]
    if on_action is not None:
        callback = on_action
        controls.append(
            ft.TextButton("Open", on_click=lambda e, target=action.target: callback(target))
        )
    return theme.card(
        ft.Column(
            controls,
            spacing=4,
        ),
        padding=12,
    )


def build_sources_panel(paths: TalamusPaths, title: str) -> ft.Control:
    """Provenance of one note, for the right inspector (PRD 14.2)."""
    result = get_library_note(paths.project_root, title)
    if not result.success or result.data is None or not result.data.found:
        return subtle(result.message or "note not found")
    if not result.data.sources:
        return subtle("no registered sources")
    rows = []
    for source in result.data.sources:
        normalized = str(source.get("normalized_path", ""))
        locator = str(source.get("locator", ""))
        rows.append(subtle(f"{normalized}\n({locator})"))
    return ft.Column(rows, spacing=6)


# ------------------------------------------------------------------- notes


def build_notes(paths: TalamusPaths, open_note: OpenNote) -> ft.Control:
    result = list_library_notes(paths.project_root)
    if not result.success or result.data is None:
        return ft.Column([heading("Notes"), ft.Text(result.message)])
    notes = result.data.notes
    if not notes:
        return ft.Column([heading("Notes"), ft.Text("No notes yet.")])
    tiles: list[ft.Control] = [
        ft.ListTile(
            title=ft.Text(note.title),
            subtitle=ft.Text(note.summary),
            on_click=lambda e, t=note.title: open_note(t),
        )
        for note in notes
    ]
    return ft.Column([heading(f"Notes ({len(notes)})"), *tiles], spacing=2)


# ------------------------------------------------------------------- graph


def build_graph(paths: TalamusPaths, title: str, open_note: OpenNote) -> ft.Control:
    """Functional graph view: the typed neighborhood of a note, navigable."""
    rows: list[ft.Control] = [heading(f"Graph - {title}" if title else "Graph")]
    if not title:
        rows.append(ft.Text("Open a note from Notes or Search to explore its connections."))
        return ft.Column(rows, spacing=8)
    result = list_graph_neighbors(paths.project_root, title)
    if not result.success or result.data is None:
        rows.append(ft.Text(result.message))
        return ft.Column(rows, spacing=8)
    connected = result.data
    if not connected:
        rows.append(ft.Text("No typed connections for this note."))
        return ft.Column(rows, spacing=8)
    by_relation: dict[str, list[GraphNeighbor]] = {}
    for item in connected:
        by_relation.setdefault(str(item.relation), []).append(item)
    for relation, items in sorted(by_relation.items()):
        rows.append(ft.Text(relation, weight=ft.FontWeight.BOLD))
        for item in items:
            arrow = "->" if item.direction == "out" else "<-"
            rows.append(
                ft.TextButton(
                    f"{arrow} {item.title}",
                    on_click=lambda e, t=str(item.title): open_note(t),
                )
            )
    return ft.Column(rows, spacing=4)


# ------------------------------------------------------------------- timeline


def build_timeline(paths: TalamusPaths, title: str) -> ft.Control:
    rows: list[ft.Control] = [heading(f"Timeline - {title}" if title else "Timeline")]
    if not title:
        rows.append(ft.Text("Open a note to see its two timelines."))
        return ft.Column(rows, spacing=8)
    data = note_timeline(paths, title)
    rows.append(
        ft.Text("Transactions (when Talamus changed the record)", weight=ft.FontWeight.BOLD)
    )
    if not data["transaction"]:
        rows.append(subtle("no versions"))
    for event in data["transaction"]:
        rows.append(subtle(f"[{event['at']}] {event['summary']}"))
    rows.append(ft.Text("Fact validity", weight=ft.FontWeight.BOLD))
    if not data["valid"]:
        rows.append(subtle("no registered claims"))
    for claim in data["valid"]:
        marker = f" (invalidated by: {claim['invalidated_by']})" if claim["invalidated_by"] else ""
        rows.append(subtle(f"[{claim['from']} -> {claim['to']}] {claim['text']}{marker}"))
    return ft.Column(rows, spacing=4)


# ------------------------------------------------------------------- domains


def build_domains(paths: TalamusPaths, open_note: OpenNote) -> ft.Control:
    overview = load_overview(paths)
    rows: list[ft.Control] = [heading("Domains")]
    if not overview:
        rows.append(ft.Text("No domains yet. Run `talamus overview`."))
    for domain in overview:
        label = f"{domain.get('name', '?')}  ({len(domain.get('members', []))} notes)"
        rows.append(ft.Text(label, size=16, weight=ft.FontWeight.BOLD))
        if domain.get("description"):
            rows.append(subtle(str(domain["description"])))
        for member in domain.get("members", []):
            rows.append(ft.TextButton(str(member), on_click=lambda e, t=str(member): open_note(t)))
    return ft.Column(rows, spacing=4)


# ------------------------------------------------------------------- review


def build_review(paths: TalamusPaths, refresh: Callable[[], None]) -> ft.Control:
    result = list_review_items(paths.project_root, status="pending")
    if not result.success or result.data is None:
        return ft.Column([heading("Review"), ft.Text(result.message)], spacing=8)
    pending = result.data
    rows: list[ft.Control] = [heading(f"Review ({len(pending)} pending)")]
    if not pending:
        rows.append(ft.Text("Queue is empty: no decisions pending."))
        return ft.Column(rows, spacing=8)

    def _apply(item_id: str) -> None:
        apply_review_item(paths.project_root, item_id)
        refresh()

    def _reject(item_id: str) -> None:
        reject_review_item(paths.project_root, item_id)
        refresh()

    for item in pending:
        rows.append(
            ft.Column(
                [
                    ft.Text(f"[{item.kind}] {item.title}", weight=ft.FontWeight.BOLD),
                    subtle(str(item.detail)),
                    ft.Row(
                        [
                            ft.TextButton("Apply", on_click=lambda e, i=item.item_id: _apply(i)),
                            ft.TextButton("Reject", on_click=lambda e, i=item.item_id: _reject(i)),
                        ]
                    ),
                    ft.Divider(),
                ],
                spacing=2,
            )
        )
    return ft.Column(rows, spacing=4)


# ------------------------------------------------------------------- ontology


def build_ontology_lab(paths: TalamusPaths, refresh: Callable[[], None]) -> ft.Control:
    status_result = get_ontology_status(paths.project_root)
    if not status_result.success or status_result.data is None:
        return ft.Column([heading("Ontology Lab"), ft.Text(status_result.message)], spacing=8)
    status = status_result.data
    cov = status.coverage
    rows: list[ft.Control] = [
        heading("Ontology Lab"),
        ft.Text(f"Schema {status.schema_id} (v{status.version})"),
        ft.Text(
            f"Coverage: {cov['non_related']}/{cov['edges']} typed edges"
            f" ({cov['non_related_share']:.0%})"
            if cov["edges"]
            else "Coverage: no edges yet"
        ),
    ]

    def _promote(type_id: str) -> None:
        apply_ontology_candidate(paths.project_root, type_id, force=True)
        refresh()

    def _reject(type_id: str) -> None:
        reject_ontology_candidate(paths.project_root, type_id)
        refresh()

    for state in ("active", "candidate", "deprecated"):
        types_result = list_ontology_candidates(paths.project_root, status=state)
        if not types_result.success or types_result.data is None:
            rows.append(ft.Text(types_result.message))
            continue
        types = types_result.data
        if not types:
            continue
        rows.append(ft.Text(state.capitalize(), size=16, weight=ft.FontWeight.BOLD))
        for rel_type in types:
            detail = [
                ft.Text(f"{rel_type.name}  (support {rel_type.support})"),
                subtle(rel_type.definition or "(no definition)"),
            ]
            for example in rel_type.examples[:2]:
                detail.append(subtle(f"e.g. {example}"))
            if state == "candidate":
                detail.append(
                    ft.Row(
                        [
                            ft.TextButton("Promote", on_click=lambda e, i=rel_type.id: _promote(i)),
                            ft.TextButton("Reject", on_click=lambda e, i=rel_type.id: _reject(i)),
                        ]
                    )
                )
            detail.append(ft.Divider())
            rows.append(ft.Column(detail, spacing=2))
    return ft.Column(rows, spacing=4)


# ------------------------------------------------------------------- settings


def build_settings(paths: TalamusPaths, notify: Callable[[str], None] | None = None) -> ft.Control:
    """Everything configurable in-app (Phase R3): engine, model, API key, MCP,
    brain registry flags. Saves go to talamus.json / TALAMUS_HOME - the same
    files the CLI uses (no duplicated logic, just thin wiring)."""
    from talamus.ui import theme

    def _notify(message: str) -> None:
        if notify is not None:
            notify(message)

    settings_result = load_engine_settings(paths.project_root)
    settings = settings_result.data or {
        "llm_provider": "claude-cli",
        "llm_model": "",
        "language": "",
    }
    engines = list_engines(settings["llm_provider"], settings["llm_model"])

    engine_dd = ft.Dropdown(
        label="LLM engine",
        value=settings["llm_provider"],
        options=[ft.DropdownOption(key=engine.provider, text=engine.label) for engine in engines],
        width=320,
    )
    model_tf = ft.TextField(
        label="Model (optional, e.g. llama3)",
        value=settings["llm_model"],
        width=320,
    )
    language_tf = ft.TextField(
        label="Note language (empty = system auto-detect)",
        value=settings["language"],
        hint_text="e.g. Italian, English, German",
        width=320,
    )

    def save_engine(_e: object) -> None:
        result = update_engine_settings(
            paths.project_root,
            provider=engine_dd.value or settings["llm_provider"],
            model=model_tf.value or "",
            language=language_tf.value or "",
        )
        _notify(result.message)

    key_set = any(engine.provider == "anthropic-api" and engine.available for engine in engines)
    key_tf = ft.TextField(
        label="Anthropic API key (anthropic-api engine)",
        password=True,
        can_reveal_password=True,
        width=320,
        hint_text="already set via env" if key_set else "empty",
    )

    def save_key(_e: object) -> None:
        if key_tf.value:
            result = save_anthropic_api_key(key_tf.value)
            key_tf.value = ""
            _notify(result.message)

    def install_mcp(_e: object) -> None:
        result = install_mcp_config(paths.project_root)
        _notify(result.message)

    integrations_result = inspect_integrations(paths.project_root)
    hook_result = build_hook_snippet(paths.project_root)
    brains_result = list_brains()
    brain_rows: list[ft.Control] = []
    if brains_result.success and brains_result.data is not None:
        brains = brains_result.data.brains
    else:
        brains = []
        brain_rows.append(theme.muted(brains_result.message))

    for brain in brains:

        def _toggle(name: str, flag: str) -> Callable[[ft.Event[ft.Switch]], None]:
            def handler(e: ft.Event[ft.Switch]) -> None:
                value = bool(e.control.value)
                if flag == "federated":
                    result = set_registered_brain_flags(name, federated=value)
                else:
                    result = set_registered_brain_flags(name, sensitive=value)
                _notify(result.message)

            return handler

        brain_rows.append(
            theme.card(
                ft.Column(
                    [
                        ft.Text(f"{brain.name}  ({brain.type})", weight=ft.FontWeight.BOLD),
                        theme.muted(brain.path),
                        ft.Row(
                            [
                                ft.Switch(
                                    label="federated",
                                    value=brain.federated,
                                    on_change=_toggle(brain.name, "federated"),
                                ),
                                ft.Switch(
                                    label="sensitive",
                                    value=brain.sensitive,
                                    on_change=_toggle(brain.name, "sensitive"),
                                ),
                            ]
                        ),
                    ],
                    spacing=4,
                ),
                padding=12,
            )
        )
    if not brain_rows:
        brain_rows.append(theme.muted("no brains in the registry (`talamus init` registers one)"))

    diagnostics_result = inspect_diagnostics(paths.project_root)
    diagnostics = diagnostics_result.data
    index_backend = diagnostics.index_backend if diagnostics is not None else "none"
    index_bytes = diagnostics.index_bytes if diagnostics is not None else 0
    mcp_status = "installed"
    hook_command = "talamus hook"
    if integrations_result.data is not None:
        mcp_status = "installed" if integrations_result.data.mcp_installed else "not installed"
        hook_command = integrations_result.data.hook_command
    elif hook_result.data is not None:
        hook_command = hook_result.data.command

    budget = os.environ.get("TALAMUS_CONTEXT_BUDGET", "6000 (default)")
    return ft.Column(
        [
            heading("Settings"),
            *([] if settings_result.success else [theme.muted(settings_result.message)]),
            theme.section("Engine"),
            theme.card(
                ft.Column(
                    [
                        engine_dd,
                        model_tf,
                        language_tf,
                        ft.FilledButton("Save engine", on_click=save_engine),
                    ],
                    spacing=10,
                )
            ),
            theme.section("API key"),
            theme.card(
                ft.Column([key_tf, ft.FilledButton("Save key", on_click=save_key)], spacing=10)
            ),
            theme.section("Agent integrations"),
            theme.card(
                ft.Column(
                    [
                        ft.FilledButton("Install MCP in this project", on_click=install_mcp),
                        theme.muted(f"MCP: {mcp_status}"),
                        theme.muted(f"Capture hook: {hook_command}"),
                    ],
                    spacing=10,
                )
            ),
            theme.section("Registered brains"),
            *brain_rows,
            theme.section("System"),
            theme.card(
                ft.Column(
                    [
                        theme.muted(f"Index: {index_backend} ({index_bytes:,} bytes)"),
                        theme.muted(f"Context budget: {budget} tokens (TALAMUS_CONTEXT_BUDGET)"),
                    ],
                    spacing=4,
                )
            ),
        ],
        spacing=10,
    )
