from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from talamus.graph import load_graph
from talamus.paths import TalamusPaths
from talamus.recall import concept_neighbors
from talamus.services.result import ServiceResult

T = TypeVar("T")


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: str
    label: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GraphSnapshot:
    nodes: list[GraphNode]
    edges: list[GraphEdge]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }


@dataclass(frozen=True)
class GraphNeighbor:
    title: str
    relation: str
    direction: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def get_graph_snapshot(root: str | Path) -> ServiceResult[GraphSnapshot]:
    paths = TalamusPaths(Path(root))
    if not paths.graph_file.is_file():
        return ServiceResult(
            success=True,
            message="Graph cache not built",
            code="graph_snapshot_empty",
            data=GraphSnapshot(nodes=[], edges=[]),
        )
    try:
        raw = load_graph(paths.graph_file)
        snapshot = _snapshot(raw)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _graph_error(exc)
    return ServiceResult(
        success=True,
        message="Graph snapshot loaded",
        code="graph_snapshot_loaded",
        data=snapshot,
    )


def list_graph_neighbors(root: str | Path, concept: str) -> ServiceResult[list[GraphNeighbor]]:
    try:
        items = concept_neighbors(TalamusPaths(Path(root)), concept)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _graph_error(exc)
    return ServiceResult(
        success=True,
        message=f"Neighbors for {concept!r} loaded",
        code="graph_neighbors_loaded",
        data=[
            GraphNeighbor(
                title=str(item.get("title", "")),
                relation=str(item.get("relation", "")),
                direction=str(item.get("direction", "")),
            )
            for item in items
        ],
    )


def _snapshot(raw: dict[str, Any]) -> GraphSnapshot:
    if not isinstance(raw, dict):
        raise ValueError("graph snapshot must be an object")
    raw_nodes = raw.get("nodes")
    raw_edges = raw.get("edges")
    if not isinstance(raw_nodes, dict) or not isinstance(raw_edges, list):
        raise ValueError("graph snapshot must contain object nodes and list edges")
    nodes = [_node(_require_object(item, "graph node")) for item in raw_nodes.values()]
    edges = [_edge(_require_object(item, "graph edge")) for item in raw_edges]
    return GraphSnapshot(nodes=nodes, edges=edges)


def _node(item: dict[str, Any]) -> GraphNode:
    node_id = _require_text(item, "id", "graph node")
    kind = _require_text(item, "kind", "graph node")
    label = _require_text(item, "label", "graph node")
    data = {str(key): value for key, value in item.items() if key not in ("id", "kind", "label")}
    return GraphNode(id=node_id, kind=kind, label=label, data=data)


def _edge(item: dict[str, Any]) -> GraphEdge:
    source = _require_text(item, "source", "graph edge")
    target = _require_text(item, "target", "graph edge")
    edge_type = _require_text(item, "type", "graph edge")
    data = {
        str(key): value for key, value in item.items() if key not in ("source", "target", "type")
    }
    return GraphEdge(source=source, target=target, type=edge_type, data=data)


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_text(item: dict[str, Any], key: str, label: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must contain text field {key!r}")
    return value


def _graph_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Graph service error: {exc}",
        code="graph_service_error",
    )
