from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from talamus.linking import NoteRegistry
from talamus.models import CanonicalNote
from talamus.paths import TalamusPaths

# Keyword patterns; first match wins, so order matters.
_RELATION_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "is-a",
        ("is-a", "is a", "isa", "tipo di", "\u00e8 un", "e un", "sottotipo", "kind of", "subclass"),
    ),
    ("part-of", ("part-of", "part of", "parte di", "fa parte", "componente di")),
    (
        "contrasts-with",
        ("contrast", "a differenza", "differisce", "si contrappone", "opposto", "invece di"),
    ),
    ("depends-on", ("depend", "dipende", "richiede", "requires", "needs", "si basa", "basato su")),
    ("uses", ("uses", "use", "usa", "utilizza", "sfrutta", "impiega")),
]


def normalize_relation(rel: str, emergent_surfaces: dict[str, str] | None = None) -> str:
    """Map a raw relation surface to a canonical type.

    ``emergent_surfaces`` maps surface keys to active ontology-lab type names.
    It is consulted after the fixed patterns and before the fallback ``related``.
    """
    low = rel.strip().lower()
    if not low:
        return "related"
    for canonical, keywords in _RELATION_PATTERNS:
        if any(keyword in low for keyword in keywords):
            return canonical
    if emergent_surfaces:
        from talamus.textutil import tokens

        key = " ".join(tokens(low))
        if key in emergent_surfaces:
            return emergent_surfaces[key]
    return "related"


def _key(value: str) -> str:
    return value.strip().lower()


def build_ontology(
    notes: list[CanonicalNote], emergent_surfaces: dict[str, str] | None = None
) -> dict[str, Any]:
    """Build the derived concept map from canonical notes."""
    registry = NoteRegistry.from_notes(notes)
    concepts: dict[str, dict[str, Any]] = {
        note.title: {"aliases": list(note.aliases), "tags": list(note.tags)} for note in notes
    }
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for note in notes:
        targets: list[tuple[str, str]] = [
            (relation.target, normalize_relation(relation.relation, emergent_surfaces))
            for relation in note.relations
        ]
        targets += [(link.target, "related") for link in note.proposed_links]
        for raw_target, rel_type in targets:
            canonical = registry.resolve(raw_target)
            if canonical is None or canonical == note.title:
                continue
            edge = (note.title, rel_type, canonical)
            if edge in seen:
                continue
            seen.add(edge)
            edges.append({"source": note.title, "type": rel_type, "target": canonical})
    return {"concepts": concepts, "edges": edges}


def neighbors(
    ontology: dict[str, Any],
    concept_title: str,
    inferred_ontology: dict[str, Any] | None = None,
    *,
    include_inferred: bool = True,
) -> list[dict[str, Any]]:
    """Typed neighbors of a concept in both directions.

    Explicit edges keep the historical shape. Inferred edges add provenance fields
    so callers can mark them and explain the rule that created them.
    """
    key = _key(concept_title)
    out: list[dict[str, Any]] = []
    for edge in ontology.get("edges", []):
        if _key(str(edge["source"])) == key:
            out.append({"title": edge["target"], "relation": edge["type"], "direction": "out"})
        elif _key(str(edge["target"])) == key:
            out.append({"title": edge["source"], "relation": edge["type"], "direction": "in"})
    if include_inferred and inferred_ontology:
        for edge in inferred_ontology.get("edges", []):
            relation = str(edge.get("relation") or edge.get("type") or "")
            if _key(str(edge.get("source", ""))) == key:
                out.append(_inferred_neighbor(edge, str(edge.get("target", "")), relation, "out"))
            elif _key(str(edge.get("target", ""))) == key:
                out.append(_inferred_neighbor(edge, str(edge.get("source", "")), relation, "in"))
    return out


def _inferred_neighbor(
    edge: dict[str, Any], title: str, relation: str, direction: str
) -> dict[str, Any]:
    return {
        "title": title,
        "relation": relation,
        "direction": direction,
        "inferred": True,
        "rule": str(edge.get("rule", "")),
        "via": list(edge.get("via", [])),
        "schema_version": int(edge.get("schema_version", 0)),
    }


def save_ontology(path: Path, ontology: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(ontology, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )


def load_ontology(paths: TalamusPaths) -> dict[str, Any]:
    if not paths.ontology_file.is_file():
        return {"concepts": {}, "edges": []}
    return json.loads(paths.ontology_file.read_text(encoding="utf-8"))


def inferred_ontology_path(paths: TalamusPaths) -> Path:
    return paths.cache / "ontology_inferred.json"


def load_inferred_ontology(paths: TalamusPaths) -> dict[str, Any]:
    path = inferred_ontology_path(paths)
    if not path.is_file():
        return {"schema_version": 0, "edges": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"schema_version": 0, "edges": []}
    edges = data.get("edges", [])
    if not isinstance(edges, list):
        edges = []
    return {"schema_version": int(data.get("schema_version", 0)), "edges": edges}


def save_inferred_ontology(paths: TalamusPaths, inferred: dict[str, Any]) -> None:
    path = inferred_ontology_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(inferred, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
