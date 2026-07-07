from __future__ import annotations

import json
from pathlib import Path

from talamus.linking import NoteRegistry
from talamus.models import CanonicalNote
from talamus.paths import TalamusPaths

# Pattern per parole chiave; il primo che combacia vince (l'ordine conta).
_RELATION_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "is-a",
        ("is-a", "is a", "isa", "tipo di", "è un", "e un", "sottotipo", "kind of", "subclass"),
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
    """Map a raw relation surface to a type. ``emergent_surfaces`` (surface key ->
    type name, from the Ontology Lab's ACTIVE schema) is consulted before falling
    back to ``related`` — promoted emergent types reclaim what the fixed patterns
    would flatten away."""
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
) -> dict:
    """Mappa concettuale: le note sono i concetti; i bersagli sono risolti al titolo canonico.

    ``emergent_surfaces`` re-tipizza con lo schema emergente ATTIVO le superfici che
    altrimenti finirebbero in ``related`` (Ontology Lab, F5.10)."""
    registry = NoteRegistry.from_notes(notes)
    concepts: dict[str, dict] = {
        note.title: {"aliases": list(note.aliases), "tags": list(note.tags)} for note in notes
    }
    edges: list[dict] = []
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


def neighbors(ontology: dict, concept_title: str) -> list[dict]:
    """Vicini tipizzati di un concetto, in entrambe le direzioni."""
    key = _key(concept_title)
    out: list[dict] = []
    for edge in ontology.get("edges", []):
        if _key(edge["source"]) == key:
            out.append({"title": edge["target"], "relation": edge["type"], "direction": "out"})
        elif _key(edge["target"]) == key:
            out.append({"title": edge["source"], "relation": edge["type"], "direction": "in"})
    return out


def save_ontology(path: Path, ontology: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(ontology, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )


def load_ontology(paths: TalamusPaths) -> dict:
    if not paths.ontology_file.is_file():
        return {"concepts": {}, "edges": []}
    return json.loads(paths.ontology_file.read_text(encoding="utf-8"))
