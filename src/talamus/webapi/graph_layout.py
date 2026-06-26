"""Server-side note-graph layout for the web graph hero.

Mirrors the Flet graph (ui/graph.py): note titles are the nodes, the typed relations
from the ontology are the edges, laid out by the deterministic pure-Python force
layout (talamus.ui.physics) so the client only renders + pans/zooms."""

from __future__ import annotations

from pathlib import Path

from talamus.ontology import load_ontology
from talamus.paths import TalamusPaths
from talamus.store import load_notes
from talamus.ui import physics


def compute_note_graph(root: Path, width: float = 900.0, height: float = 600.0) -> dict:
    paths = TalamusPaths(Path(root))
    titles = [note.title for note in load_notes(paths)]
    ontology = load_ontology(paths)
    edges = [
        (str(edge["source"]), str(edge["target"]), str(edge.get("type", "related")))
        for edge in ontology.get("edges", [])
    ]
    layout = physics.build_layout(titles, edges, width=width, height=height)
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
    return {"nodes": nodes, "edges": out_edges, "width": width, "height": height}
