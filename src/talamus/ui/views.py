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
from talamus.services.library import LibraryNoteSummary, get_library_note, list_library_notes
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
    engine_ready = any(
        bool(getattr(engine, "configured", False)) and bool(getattr(engine, "available", False))
        for engine in getattr(report, "engines", [])
    )
    setup_state = (
        "Ready" if getattr(report, "config_exists", False) and engine_ready else "Needs setup"
    )
    access_ready = bool(getattr(report, "mcp_installed", False))
    access_state = "MCP installed" if access_ready else "MCP not installed"
    tiles = ft.Row(
        [
            theme.metric(
                "Engine", setup_state, "detected on launch", "ready" if engine_ready else "warn"
            ),
            theme.metric(
                "Brain",
                f"{getattr(report, 'notes', 0)} notes",
                "pick or create deliberately",
                "accent",
            ),
            theme.metric(
                "Access",
                access_state,
                "agent-native co-launch",
                "ready" if access_ready else "warn",
            ),
            theme.metric(
                "Review",
                str(getattr(report, "reviews_pending", 0)),
                "pending decisions",
                "warn" if getattr(report, "reviews_pending", 0) else "muted",
            ),
        ],
        wrap=True,
        spacing=theme.GAP,
        run_spacing=theme.GAP,
    )
    rows: list[ft.Control] = [
        ft.Column(
            [
                heading("Command Center"),
                theme.muted(
                    f"{report.root} - No brain is created automatically. "
                    "Choose a setup path when you are ready."
                ),
            ],
            spacing=4,
        ),
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

    action_rows: list[ft.Control] = [theme.section("Next best actions")]
    if report.next_actions:
        action_rows.extend(_next_action_card(action, on_action) for action in report.next_actions)
    else:
        action_rows.append(
            theme.panel(
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

    system_rows: list[ft.Control] = [theme.section("System status")]
    system_rows.extend(_engine_card(engine) for engine in report.engines)
    if not getattr(report, "engines", []):
        system_rows.append(theme.muted("No engine report available yet."))
    system_rows.append(
        theme.panel(
            ft.Column(
                [
                    theme.muted(f"Index: {getattr(report, 'index_backend', 'none')}"),
                    theme.muted(
                        f"Active jobs: {getattr(report, 'jobs_active', 0)}; "
                        f"sources: {getattr(report, 'sources', 0)}"
                    ),
                ],
                spacing=3,
            ),
            padding=12,
        )
    )

    rows.append(
        ft.Row(
            [
                theme.panel(ft.Column(action_rows, spacing=10), width=300),
                _graph_preview_panel(report),
            ],
            wrap=True,
            spacing=theme.GAP,
            run_spacing=theme.GAP,
        )
    )
    rows.append(theme.panel(ft.Column(system_rows, spacing=10)))
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
        ("Language", "Language-native memory"),
        ("Token cost", f"Cost promise: {budget} token budget"),
    ]
    return theme.panel(
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


def _graph_preview_panel(report: object) -> ft.Control:
    from talamus.ui import theme

    notes = int(getattr(report, "notes", 0) or 0)
    domains = int(getattr(report, "overview_domains", 0) or 0)
    reviews = int(getattr(report, "reviews_pending", 0) or 0)
    legend = [
        ("Retrieval", theme.ACCENT_2),
        ("Ontology", theme.OK),
        ("Review", theme.DANGER if reviews else theme.WARN),
    ]
    return theme.panel(
        ft.Column(
            [
                theme.section("Graph preview"),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        width=28,
                                        height=28,
                                        bgcolor="#B7A7FF",
                                        border_radius=14,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text("Local graph", weight=ft.FontWeight.BOLD),
                                            theme.muted(f"{notes} notes, {domains} domains"),
                                        ],
                                        spacing=2,
                                        tight=True,
                                    ),
                                ],
                                spacing=10,
                            ),
                            ft.Row(
                                [
                                    ft.Container(
                                        width=13, height=13, bgcolor=theme.ACCENT_2, border_radius=7
                                    ),
                                    ft.Container(
                                        width=13, height=13, bgcolor=theme.WARN, border_radius=7
                                    ),
                                    ft.Container(
                                        width=13, height=13, bgcolor=theme.OK, border_radius=7
                                    ),
                                    ft.Container(
                                        width=13, height=13, bgcolor=theme.DANGER, border_radius=7
                                    ),
                                ],
                                spacing=24,
                            ),
                            ft.Row(
                                [
                                    ft.Row(
                                        [
                                            ft.Container(
                                                width=8, height=8, bgcolor=color, border_radius=4
                                            ),
                                            ft.Text(label, size=11, color=theme.MUTED),
                                        ],
                                        spacing=5,
                                        tight=True,
                                    )
                                    for label, color in legend
                                ],
                                wrap=True,
                                spacing=10,
                                run_spacing=6,
                            ),
                        ],
                        spacing=14,
                    ),
                    bgcolor=theme.CANVAS,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=8,
                    padding=14,
                ),
                theme.muted(
                    "Pan, zoom, focus, provenance and typed relations stay in the graph view."
                ),
            ],
            spacing=10,
        ),
        width=300,
    )


def _engine_card(engine: EngineReadiness) -> ft.Control:
    from talamus.ui import theme

    marker = "selected" if engine.configured else engine.status
    tone = "ready" if getattr(engine, "available", False) else "warn"
    if getattr(engine, "needs_secret", False) or getattr(engine, "status", "") == "not_installed":
        tone = "warning"
    return theme.panel(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(engine.label, weight=ft.FontWeight.BOLD),
                        theme.status_pill(marker, tone=tone),
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
    return theme.panel(
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


def build_verification_panel(paths: TalamusPaths, title: str) -> ft.Control:
    from talamus.ui import theme

    note_result = get_library_note(paths.project_root, title)
    if not note_result.success or note_result.data is None or not note_result.data.found:
        return theme.panel(
            ft.Column(
                [
                    theme.section("Verification moat"),
                    theme.muted(note_result.message or "Note not found."),
                ],
                spacing=5,
                tight=True,
            ),
            padding=12,
        )
    sources = list(getattr(note_result.data, "sources", []) or [])
    review_result = list_review_items(paths.project_root, status="pending")
    pending = [
        item
        for item in (review_result.data or [])
        if review_result.success and _review_item_matches_title(item, title)
    ]
    rows: list[ft.Control] = [
        theme.section("Verification moat"),
        ft.Text("Source truth stays separate from machine truth.", weight=ft.FontWeight.BOLD),
        theme.muted(f"{_count_label(len(sources), 'registered source')} tracked for this note."),
    ]
    if not pending:
        rows.append(theme.muted("No stale-source or correction review is pending."))
    for item in pending:
        detail = getattr(item, "detail", {}) or {}
        rows.append(
            ft.Row(
                [
                    theme.status_pill(str(getattr(item, "kind", "review")), "warn"),
                    theme.muted(str(detail.get("why") or getattr(item, "item_id", ""))),
                ],
                spacing=8,
                wrap=True,
            )
        )
    rows.append(theme.muted("Review keeps corrections explicit before anything is applied."))
    return theme.panel(ft.Column(rows, spacing=6, tight=True), padding=12)


def _review_item_matches_title(item: object, title: str) -> bool:
    if str(getattr(item, "title", "")) == title:
        return True
    detail = getattr(item, "detail", {}) or {}
    return isinstance(detail, dict) and str(detail.get("title", "")) == title


# ------------------------------------------------------------------- notes


def build_notes(paths: TalamusPaths, open_note: OpenNote) -> ft.Control:
    from talamus.ui import theme

    result = list_library_notes(paths.project_root)
    if not result.success or result.data is None:
        return ft.Column([heading("Notes"), ft.Text(result.message)])
    notes = result.data.notes
    if not notes:
        return ft.Column([heading("Notes"), ft.Text("No notes yet.")])
    cards = [_note_card(note, open_note) for note in notes]
    return ft.Column(
        [
            ft.Column(
                [
                    heading(f"Notes ({len(notes)})"),
                    theme.muted(
                        "Browse markdown truth with provenance, relations and review signals."
                    ),
                ],
                spacing=4,
            ),
            *cards,
        ],
        spacing=8,
    )


def _count_label(count: int, singular: str, plural: str | None = None) -> str:
    suffix = singular if count == 1 else plural or f"{singular}s"
    return f"{count} {suffix}"


def _note_card(note: LibraryNoteSummary, open_note: OpenNote) -> ft.Control:
    from talamus.ui import theme

    confidence_tone = "ready" if note.confidence >= 0.75 else "warn"
    meta: list[ft.Control] = [
        theme.status_pill(_count_label(note.source_count, "source"), "accent"),
        theme.status_pill(_count_label(note.relation_count, "relation"), "ready"),
        theme.status_pill(_count_label(note.proposed_link_count, "proposed link"), "warn"),
        theme.status_pill(f"confidence {note.confidence:.2f}", confidence_tone),
    ]
    rows: list[ft.Control] = [
        ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(note.title, size=16, weight=ft.FontWeight.BOLD),
                        theme.muted(note.summary or "No summary yet."),
                    ],
                    spacing=3,
                    expand=True,
                ),
                ft.TextButton("Open", on_click=lambda e, title=note.title: open_note(title)),
            ],
            spacing=10,
            wrap=True,
        ),
        ft.Row(meta, wrap=True, spacing=8, run_spacing=6),
    ]
    if note.tags:
        rows.append(
            ft.Row(
                [theme.status_pill(tag, "muted") for tag in note.tags[:6]],
                wrap=True,
                spacing=6,
                run_spacing=6,
            )
        )
    detail = []
    if note.updated_at:
        detail.append(f"updated {note.updated_at}")
    if note.markdown_path:
        detail.append(note.markdown_path)
    if detail:
        rows.append(theme.muted(" - ".join(detail)))
    return theme.panel(ft.Column(rows, spacing=8), padding=12)


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
    from talamus.ui import theme

    rows: list[ft.Control] = [heading(f"Timeline - {title}" if title else "Timeline")]
    if not title:
        rows.append(ft.Text("Open a note to see its two timelines."))
        return ft.Column(rows, spacing=8)
    data = note_timeline(paths, title)
    transactions = data["transaction"]
    claims = data["valid"]
    transaction_count = len(transactions)
    claim_count = len(claims)
    rows.append(
        theme.panel(
            ft.Column(
                [
                    theme.section("As-of moat"),
                    ft.Text(
                        "Ask can replay this note as it looked at a past date.",
                        weight=ft.FontWeight.BOLD,
                    ),
                    theme.muted(
                        f"History: {transaction_count} "
                        f"{'version' if transaction_count == 1 else 'versions'}; "
                        f"validity: {claim_count} {'claim' if claim_count == 1 else 'claims'}."
                    ),
                ],
                spacing=5,
                tight=True,
            ),
            padding=12,
        )
    )
    transaction_rows: list[ft.Control] = [
        theme.section("Transaction history"),
        ft.Text(
            f"{transaction_count} {'version' if transaction_count == 1 else 'versions'}",
            weight=ft.FontWeight.BOLD,
        ),
    ]
    if not transactions:
        transaction_rows.append(theme.muted("No versions"))
    for event in transactions:
        transaction_rows.append(theme.muted(f"[{event['at']}] {event['summary']}"))
    rows.append(theme.panel(ft.Column(transaction_rows, spacing=5, tight=True), padding=12))

    validity_rows: list[ft.Control] = [
        theme.section("Fact validity"),
        ft.Text(
            f"{claim_count} {'claim' if claim_count == 1 else 'claims'}", weight=ft.FontWeight.BOLD
        ),
    ]
    if not claims:
        validity_rows.append(theme.muted("No registered claims"))
    for claim in claims:
        marker = f" (invalidated by: {claim['invalidated_by']})" if claim["invalidated_by"] else ""
        validity_rows.append(
            theme.muted(f"[{claim['from']} -> {claim['to']}] {claim['text']}{marker}")
        )
    rows.append(theme.panel(ft.Column(validity_rows, spacing=5, tight=True), padding=12))
    return ft.Column(rows, spacing=8)


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
    from talamus.ui import theme

    result = list_review_items(paths.project_root, status="pending")
    if not result.success or result.data is None:
        return ft.Column([heading("Review"), ft.Text(result.message)], spacing=8)
    pending = result.data
    rows: list[ft.Control] = [
        heading(f"Review ({len(pending)} pending)"),
        theme.panel(
            ft.Column(
                [
                    theme.section("Review guardrail"),
                    ft.Text(
                        "Proposed changes are never auto-applied.",
                        weight=ft.FontWeight.BOLD,
                    ),
                    theme.muted("Apply writes a reviewed correction; Reject records the decision."),
                ],
                spacing=5,
            ),
            padding=12,
        ),
    ]
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
            theme.panel(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(item.title, weight=ft.FontWeight.BOLD),
                                        theme.muted(f"{item.kind} - {item.item_id}"),
                                    ],
                                    spacing=3,
                                    expand=True,
                                ),
                                theme.status_pill(getattr(item, "status", "pending"), "warn"),
                            ],
                            spacing=8,
                            wrap=True,
                        ),
                        theme.section("Evidence"),
                        ft.Column(_review_detail_controls(item.detail), spacing=3),
                        theme.muted(f"Created {getattr(item, 'created_at', '')}".strip()),
                        ft.Row(
                            [
                                ft.TextButton(
                                    "Apply", on_click=lambda e, i=item.item_id: _apply(i)
                                ),
                                ft.TextButton(
                                    "Reject", on_click=lambda e, i=item.item_id: _reject(i)
                                ),
                            ],
                            spacing=8,
                        ),
                    ],
                    spacing=8,
                ),
                padding=12,
            )
        )
    return ft.Column(rows, spacing=8)


def _review_detail_controls(detail: object) -> list[ft.Control]:
    if not isinstance(detail, dict) or not detail:
        return [subtle("No evidence detail recorded.")]
    controls: list[ft.Control] = []
    for key in sorted(detail):
        value = detail[key]
        if value in ("", None, [], {}):
            continue
        controls.append(subtle(f"{key}: {value}"))
    return controls or [subtle("No evidence detail recorded.")]


# ------------------------------------------------------------------- ontology


def build_ontology_lab(paths: TalamusPaths, refresh: Callable[[], None]) -> ft.Control:
    from talamus.ui import theme

    status_result = get_ontology_status(paths.project_root)
    if not status_result.success or status_result.data is None:
        return ft.Column([heading("Ontology Lab"), ft.Text(status_result.message)], spacing=8)
    status = status_result.data
    cov = status.coverage
    coverage = (
        f"{cov['non_related']}/{cov['edges']} typed edges ({cov['non_related_share']:.0%})"
        if cov["edges"]
        else "no edges yet"
    )
    rows: list[ft.Control] = [
        heading("Ontology Lab"),
        theme.panel(
            ft.Column(
                [
                    theme.section("Ontology insights"),
                    ft.Text(f"Schema {status.schema_id} (v{status.version})"),
                    ft.Row(
                        [
                            theme.status_pill("Typed coverage", "accent"),
                            theme.muted(coverage),
                        ],
                        spacing=8,
                        wrap=True,
                    ),
                    theme.muted(
                        "Promotion is a schema decision: candidates stay reviewable until "
                        "you promote or reject them."
                    ),
                ],
                spacing=6,
            ),
            padding=12,
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
        rows.append(theme.section(state.capitalize()))
        for rel_type in types:
            rows.append(_ontology_type_card(rel_type, state, _promote, _reject))
    return ft.Column(rows, spacing=8)


def _ontology_type_card(
    rel_type: object,
    state: str,
    promote: Callable[[str], None],
    reject: Callable[[str], None],
) -> ft.Control:
    from talamus.ui import theme

    type_id = str(getattr(rel_type, "id", ""))
    examples = list(getattr(rel_type, "examples", []) or [])
    rows: list[ft.Control] = [
        ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(str(getattr(rel_type, "name", "?")), weight=ft.FontWeight.BOLD),
                        theme.muted(str(getattr(rel_type, "definition", "") or "(no definition)")),
                    ],
                    spacing=3,
                    expand=True,
                ),
                theme.status_pill(
                    f"support {getattr(rel_type, 'support', 0)}",
                    "ready" if state == "active" else "warn",
                ),
            ],
            spacing=8,
            wrap=True,
        )
    ]
    if examples:
        rows.append(theme.section("Candidate evidence" if state == "candidate" else "Evidence"))
        rows.extend(subtle(f"e.g. {example}") for example in examples[:2])
    if state == "candidate":
        rows.append(
            ft.Row(
                [
                    ft.TextButton("Promote", on_click=lambda e, i=type_id: promote(i)),
                    ft.TextButton("Reject", on_click=lambda e, i=type_id: reject(i)),
                ],
                spacing=8,
            )
        )
    return theme.panel(ft.Column(rows, spacing=8), padding=12)


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
        selected_brain = brains_result.data.selected
        registry_path = brains_result.data.registry_path
    else:
        brains = []
        selected_brain = ""
        registry_path = ""
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

        scope_pills: list[ft.Control] = []
        if brain.name == selected_brain:
            scope_pills.append(theme.status_pill("selected", "ready"))
        scope_pills.append(
            theme.status_pill(
                "shared retrieval" if brain.federated else "project-only",
                "accent" if brain.federated else "muted",
            )
        )
        scope_pills.append(
            theme.status_pill(
                "sensitive" if brain.sensitive else "not sensitive",
                "warn" if brain.sensitive else "ready",
            )
        )
        brain_rows.append(
            theme.card(
                ft.Column(
                    [
                        ft.Text(f"{brain.name}  ({brain.type})", weight=ft.FontWeight.BOLD),
                        theme.muted(brain.path),
                        ft.Row(scope_pills, wrap=True, spacing=8, run_spacing=6),
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
    cache_current = bool(getattr(diagnostics, "cache_current", False))
    note_count = int(getattr(diagnostics, "notes", 0) or 0)
    domain_count = int(getattr(diagnostics, "overview_domains", 0) or 0)
    llm_provider = str(getattr(diagnostics, "llm_provider", "unknown"))
    llm_status = str(getattr(diagnostics, "llm_status", "unknown"))
    search_provider = str(getattr(diagnostics, "search_provider", "unknown"))
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
                        theme.section("Agent-native co-launch"),
                        ft.Text("the memory your agent already has", weight=ft.FontWeight.BOLD),
                        theme.muted(
                            "MCP and the capture hook let agents read and remember through "
                            "the same local brain."
                        ),
                        ft.FilledButton("Install MCP in this project", on_click=install_mcp),
                        theme.muted(f"MCP: {mcp_status}"),
                        theme.muted(f"Capture hook: {hook_command}"),
                    ],
                    spacing=10,
                )
            ),
            theme.section("Registered brains"),
            theme.card(
                ft.Column(
                    [
                        theme.section("Scope guardrails"),
                        theme.muted(f"Registry: {registry_path or 'not configured'}"),
                        theme.muted(
                            "Federated brains can answer shared queries; sensitive brains stay "
                            "out of broad retrieval."
                        ),
                    ],
                    spacing=4,
                ),
                padding=12,
            ),
            *brain_rows,
            theme.section("System"),
            theme.card(
                ft.Column(
                    [
                        theme.section("Diagnostics"),
                        theme.muted(f"Index: {index_backend} ({index_bytes:,} bytes)"),
                        theme.muted(f"Cache: {'fresh' if cache_current else 'stale'}"),
                        theme.muted(
                            f"{_count_label(note_count, 'note')}; "
                            f"{_count_label(domain_count, 'domain')}"
                        ),
                        theme.muted(f"Engine: {llm_provider} ({llm_status})"),
                        theme.muted(f"Search: {search_provider}"),
                        theme.muted(f"Context budget: {budget} tokens (TALAMUS_CONTEXT_BUDGET)"),
                    ],
                    spacing=4,
                )
            ),
        ],
        spacing=10,
    )
