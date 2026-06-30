"""Server-side note-graph layout for the web graph hero.

Mirrors the Flet graph (ui/graph.py): note titles are the nodes, the typed relations
from the ontology are the edges, laid out by the deterministic pure-Python force
layout (talamus.ui.physics) so the client only renders + pans/zooms.

The force layout is O(steps x N^2), so big brains are capped to the most-connected
nodes (like the Flet global view) and the result — deterministic for a given set of
notes + edges — is memoised so repeat /api/graph calls are instant."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from talamus.ontology import load_ontology
from talamus.paths import TalamusPaths
from talamus.store import load_notes
from talamus.ui import physics

_NODE_CAP = 120
_CACHE: dict[str, dict] = {}


def compute_note_graph(root: Path, width: float = 900.0, height: float = 600.0) -> dict:
    paths = TalamusPaths(Path(root))
    titles = [note.title for note in load_notes(paths)]
    ontology = load_ontology(paths)
    edges = [
        (str(edge["source"]), str(edge["target"]), str(edge.get("type", "related")))
        for edge in ontology.get("edges", [])
    ]

    signature = hashlib.sha1(
        json.dumps([sorted(titles), sorted(edges)], ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    cache_key = f"{paths.project_root.resolve()}::{width}x{height}::{signature}"
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return cached

    # Cap to the most-connected notes so the layout stays fast on large brains.
    kept = set(physics.select_global(edges, titles, cap=_NODE_CAP))
    kept_edges = [(s, d, t) for (s, d, t) in edges if s in kept and d in kept]
    layout = physics.build_layout(sorted(kept), kept_edges, width=width, height=height)
    physics.settle(layout)

    nodes = [
        {
            "id": node_id,
            "label": node_id,
            "x": round(node.x, 1),
            "y": round(node.y, 1),
            "r": round(layout.radius(node_id), 1),
            "degree": node.degree,
        }
        for node_id, node in layout.nodes.items()
    ]
    out_edges = [
        {"source": src, "target": dst, "type": edge_type, "typed": edge_type != "related"}
        for src, dst, edge_type in layout.edges
    ]
    result = {
        "nodes": nodes,
        "edges": out_edges,
        "width": width,
        "height": height,
        "total": len(titles),
        "shown": len(nodes),
    }
    _CACHE[cache_key] = result
    return result
