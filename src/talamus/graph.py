from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from talamus.models import CanonicalNote


def _node_id(kind: str, value: str) -> str:
    slug = re.sub(r"[^a-z0-9._/-]+", "-", value.lower()).strip("-")
    return f"{kind}:{slug}"


def build_graph(notes: list[CanonicalNote]) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(node_id: str, **attrs: object) -> None:
        nodes[node_id] = {"id": node_id, **attrs}

    def add_edge(source: str, target: str, edge_type: str, **attrs: object) -> None:
        edges.append({"source": source, "target": target, "type": edge_type, **attrs})

    for note in notes:
        note_id = _node_id("note", note.note_id)
        add_node(
            note_id,
            kind="note",
            label=note.title,
            aliases=note.aliases,
            tags=note.tags,
            summary=note.summary,
            retrieval_text=note.retrieval_text,
            confidence=note.confidence,
        )
        for alias in note.aliases:
            alias_id = _node_id("alias", alias)
            add_node(alias_id, kind="alias", label=alias)
            add_edge(note_id, alias_id, "has_alias")
        for tag in note.tags:
            tag_id = _node_id("tag", tag)
            add_node(tag_id, kind="tag", label=tag)
            add_edge(note_id, tag_id, "tagged")
        for source in note.sources:
            source_id = _node_id("source", source.normalized_path)
            add_node(source_id, kind="source", label=source.normalized_path, raw_path=source.raw_path)
            add_edge(source_id, note_id, "supports", locator=source.locator)
        for relation in note.relations:
            target_id = _node_id("concept", relation.target)
            add_node(target_id, kind="concept", label=relation.target)
            add_edge(note_id, target_id, relation.relation, confidence=relation.confidence)

    return {"nodes": nodes, "edges": edges}


def _terms(text: str) -> Counter[str]:
    return Counter(re.findall(r"[a-z0-9][a-z0-9-]{2,}", text.lower()))


def query_graph(graph: dict, question: str, limit: int = 5) -> list[dict]:
    q_terms = _terms(question)
    scored: list[tuple[int, dict]] = []
    for node in graph["nodes"].values():
        if node.get("kind") != "note":
            continue
        haystack = " ".join(
            [
                str(node.get("label", "")),
                " ".join(node.get("aliases", [])),
                " ".join(node.get("tags", [])),
                str(node.get("summary", "")),
                str(node.get("retrieval_text", "")),
            ]
        )
        score = sum(_terms(haystack).get(term, 0) * count for term, count in q_terms.items())
        if score > 0:
            scored.append((score, node))
    return [node for _score, node in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]


def save_graph(path: Path, graph: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, indent=2, sort_keys=True), encoding="utf-8")


def load_graph(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
