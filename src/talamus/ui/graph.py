"""The living graph view: force-directed canvas, Obsidian-style (Phase R2).

Rendering layer over ``talamus.ui.physics``: nodes colored by domain (overview),
sized by degree, typed edges brighter than ``related`` ones, animated until the
layout settles. **Tap a node to open its note.** Pure Python on ``flet.canvas``
- no JS, no extra dependencies.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import flet as ft
import flet.canvas as cv

from talamus.domains import load_overview
from talamus.ontology import load_ontology
from talamus.paths import TalamusPaths
from talamus.ui import physics

CANVAS_W = 880.0
CANVAS_H = 560.0
_EDGE_RELATED = "#3A4148"
_EDGE_TYPED = "#7E8A96"
_NODE_DEFAULT = "#90A4AE"
_LABEL = "#C8D2DA"

# one animation at a time: bumping the generation stops the previous loop
_generation = {"value": 0}


def _edges_from_ontology(paths: TalamusPaths) -> list[tuple[str, str, str]]:
    ontology = load_ontology(paths)
    return [
        (str(e["source"]), str(e["target"]), str(e.get("type", "related")))
        for e in ontology.get("edges", [])
    ]


def _domain_of(paths: TalamusPaths) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for domain in load_overview(paths):
        for member in domain.get("members", []):
            mapping[str(member)] = str(domain.get("name", ""))
    return mapping


def _shapes(layout: physics.Layout, colors: dict[str, str], focus: str) -> list[cv.Shape]:
    shapes: list[cv.Shape] = []
    for src, dst, edge_type in layout.edges:
        a, b = layout.nodes[src], layout.nodes[dst]
        typed = edge_type != "related"
        shapes.append(
            cv.Line(
                a.x,
                a.y,
                b.x,
                b.y,
                paint=ft.Paint(
                    color=_EDGE_TYPED if typed else _EDGE_RELATED,
                    stroke_width=1.6 if typed else 1.0,
                ),
            )
        )
    for node in layout.nodes.values():
        radius = layout.radius(node.id)
        color = colors.get(node.domain, _NODE_DEFAULT)
        if node.id == focus:
            shapes.append(cv.Circle(node.x, node.y, radius + 4, ft.Paint(color="#FFFFFF55")))
        shapes.append(cv.Circle(node.x, node.y, radius, ft.Paint(color=color)))
        if radius >= 8 or node.id == focus:  # label only the notable nodes
            shapes.append(
                cv.Text(
                    node.x + radius + 3,
                    node.y - 7,
                    node.id,
                    ft.TextStyle(size=11, color=_LABEL),
                )
            )
    return shapes


def _count_label(count: int, singular: str, plural: str | None = None) -> str:
    suffix = singular if count == 1 else plural or f"{singular}s"
    return f"{count} {suffix}"


def _accessible_node_list(
    layout: physics.Layout,
    open_note: Callable[[str], None],
) -> ft.Control:
    from talamus.ui import theme

    rows: list[ft.Control] = [
        theme.section("Accessible graph list"),
        theme.muted(
            f"{_count_label(len(layout.nodes), 'node')}; "
            f"{_count_label(len(layout.edges), 'relation')} in the visible graph."
        ),
    ]
    for node_id in sorted(layout.nodes):
        node = layout.nodes[node_id]
        degree = sum(1 for src, dst, _ in layout.edges if node_id in (src, dst))
        domain = node.domain or "No domain"
        rows.append(
            ft.Row(
                [
                    ft.TextButton(
                        f"Open {node_id}",
                        on_click=lambda e, title=node_id: open_note(title),
                    ),
                    theme.muted(f"{domain}; {_count_label(degree, 'edge')}"),
                ],
                spacing=8,
                wrap=True,
            )
        )
    return theme.panel(ft.Column(rows, spacing=8), padding=12)


def build_graph_canvas(
    paths: TalamusPaths,
    focus: str,
    open_note: Callable[[str], None],
    page: ft.Page | None = None,
    animate: bool = True,
) -> ft.Control:
    """The graph view: global (most connected notes) or focused (neighborhood).

    ``animate=False`` settles synchronously — used by headless tests and when no
    page is available; with a page, a background loop animates ~30fps until calm.
    """
    edges = _edges_from_ontology(paths)
    domains = _domain_of(paths)
    all_nodes = sorted({n for s, d, _ in edges for n in (s, d)})
    if focus and any(focus in (s, d) for s, d, _ in edges):
        node_ids = physics.select_neighborhood(edges, focus)
        subtitle = f'neighborhood of "{focus}" (tap a node to open it)'
    else:
        node_ids = physics.select_global(edges, all_nodes)
        subtitle = "most connected notes (tap a node to open one)"
    if not node_ids:
        return ft.Column(
            [
                ft.Text("Graph", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("No connections yet: ingest something and come back here."),
            ]
        )
    layout = physics.build_layout(node_ids, edges, width=CANVAS_W, height=CANVAS_H, domains=domains)
    colors = physics.domain_colors(list(domains.values()))
    canvas = cv.Canvas(shapes=_shapes(layout, colors, focus), width=CANVAS_W, height=CANVAS_H)

    def on_tap(event: ft.TapEvent[ft.GestureDetector]) -> None:
        position = getattr(event, "local_position", None)
        if position is not None:
            x, y = float(position.x), float(position.y)
        else:
            x = float(getattr(event, "local_x", 0.0))
            y = float(getattr(event, "local_y", 0.0))
        hit = physics.hit_test(layout, x, y)
        if hit:
            open_note(hit)

    surface = ft.GestureDetector(content=canvas, on_tap_down=on_tap)

    if animate and page is not None:
        _generation["value"] += 1
        my_generation = _generation["value"]

        def loop() -> None:
            for _ in range(240):  # ~8s max, then the layout is settled anyway
                if _generation["value"] != my_generation:
                    return
                movement = physics.step(layout)
                canvas.shapes = _shapes(layout, colors, focus)
                try:
                    page.update()
                except Exception:
                    return  # the page is gone (view changed / app closed)
                if movement / max(len(layout.nodes), 1) < 0.4:
                    return
                time.sleep(1 / 30)

        threading.Thread(target=loop, daemon=True).start()
    else:
        physics.settle(layout)
        canvas.shapes = _shapes(layout, colors, focus)

    legend_items: list[ft.Control] = []
    for name, color in sorted(colors.items()):
        legend_items.append(
            ft.Row(
                [ft.Container(width=10, height=10, bgcolor=color, border_radius=5),
                 ft.Text(name, size=11)],
                spacing=4,
                tight=True,
            )
        )  # fmt: skip
    header: list[ft.Control] = [
        ft.Text("Graph", size=22, weight=ft.FontWeight.BOLD),
        ft.Text(subtitle, size=12, opacity=0.7),
    ]
    if legend_items:
        header.append(ft.Row(legend_items, wrap=True, spacing=12))
    return ft.Column(
        [
            *header,
            ft.Container(surface, border_radius=8),
            _accessible_node_list(layout, open_note),
        ],
        spacing=8,
    )
