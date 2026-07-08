"""Ontology Lab — the self-emerging type system, versioned and measured (PRD 9.3/F5).

The extraction LLM emits *free-form* relation surfaces ("alimenta", "sostituisce",
"deriva da", ...). The fixed normalizer flattens everything it doesn't know to
``related`` — pure information loss. This lab recovers it:

1. **Evidence** (deterministic): every raw relation surface on every note becomes
   an evidence record with subject/object/context/source ref.
2. **Induction**: surfaces the fixed types can't explain are clustered
   deterministically (stemmed surface key); clusters with enough support become
   *candidate* relation types, named/defined by one LLM call.
3. **Versioned schema**: candidate → active → deprecated, never deleted; every
   transition is a history event with timestamps (the schema itself is temporal).
4. **Runtime**: `build_ontology` maps surfaces of ACTIVE types to their type, so
   promoted knowledge immediately improves edge typing — and retrieval expansion
   prefers typed edges over ``related`` ones, making promotion measurable.
5. **Metrics**: coverage (non-``related`` share), stability (Jaccard of cluster
   keys across runs), review burden, and retrieval lift via the eval harness.

Candidates never affect runtime without promotion (F5.10).
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from talamus.model_json import json_array
from talamus.models import CanonicalNote
from talamus.ontology import (
    build_ontology,
    load_ontology,
    neighbors,
    normalize_relation,
    save_inferred_ontology,
)
from talamus.paths import TalamusPaths
from talamus.routing import Router, TaskClass
from talamus.store import load_notes, save_ontology
from talamus.textutil import tokens

DEFAULT_MIN_SUPPORT = 3  # evidence items needed to even become a candidate
PROMOTION_MIN_SUPPORT = 8  # PRD 12.6 defaults
PROMOTION_MIN_NOTES = 3


def lab_dir(paths: TalamusPaths) -> Path:
    return paths.cache / "ontology"


def _ontology_scope(paths: TalamusPaths) -> str:
    """ "global" (default): ONE schema shared across all brains; "brain": isolated.

    Read from the brain's config on every call (cheap, and config edits apply
    immediately); a malformed config never blocks the lab — default wins."""
    from talamus.config import load_or_default

    try:
        scope = load_or_default(paths.config_path).ontology_scope
    except Exception:
        return "global"
    return scope if scope in ("global", "brain") else "global"


def _global_lab_dir() -> Path:
    from talamus.registry import talamus_home

    return talamus_home() / "ontology"


def schema_path(paths: TalamusPaths) -> Path:
    """Where the relation-type schema lives for this brain's scope.

    The schema (learned types) is the user's personal semantic layer, shared
    machine-wide by default so a type learned anywhere improves every brain
    (dev/specs/2026-07-02-global-ontology-design.md). Evidence stays per brain."""
    if _ontology_scope(paths) == "brain":
        return lab_dir(paths) / "schema.json"
    return _global_lab_dir() / "schema.json"


def evidence_path(paths: TalamusPaths) -> Path:
    return lab_dir(paths) / "evidence.jsonl"


def history_path(paths: TalamusPaths) -> Path:
    """Schema events follow the schema: global scope logs beside the shared file."""
    if _ontology_scope(paths) == "brain":
        return lab_dir(paths) / "history.jsonl"
    return _global_lab_dir() / "history.jsonl"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def surface_key(surface: str) -> str:
    """Canonical key for a relation surface: stemmed tokens, order preserved."""
    return " ".join(tokens(surface))


@dataclass
class Evidence:
    source_note: str
    source_ref: str
    subject: str
    predicate_surface: str
    object: str
    context: str
    suggested_type: str
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RelationType:
    id: str
    name: str
    definition: str = ""
    inverse: str = ""
    inverse_of: str = ""
    transitive: bool = False
    symmetric: bool = False
    surfaces: list[str] = field(default_factory=list)  # surface keys it canonicalizes
    examples: list[str] = field(default_factory=list)
    support: int = 0
    distinct_notes: int = 0
    confidence: float = 0.0
    status: str = "candidate"  # candidate | active | deprecated
    valid_from: str = ""
    valid_to: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RelationPropertyCandidate:
    id: str
    property: str
    type_id: str
    value: str = ""
    witnesses: list[dict] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    support: int = 0
    distinct_notes: int = 0
    confidence: float = 0.0
    status: str = "candidate"  # candidate | active | deprecated
    valid_from: str = ""
    valid_to: str = ""
    kind: str = "property"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Schema:
    version: int = 1
    schema_id: str = ""
    created_at: str = ""
    relation_types: list[RelationType] = field(default_factory=list)
    property_candidates: list[RelationPropertyCandidate] = field(default_factory=list)

    def by_id(self, type_id: str) -> RelationType | None:
        for rel_type in self.relation_types:
            if rel_type.id == type_id:
                return rel_type
        return None

    def by_property_id(self, candidate_id: str) -> RelationPropertyCandidate | None:
        for candidate in self.property_candidates:
            if candidate.id == candidate_id:
                return candidate
        return None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "schema_id": self.schema_id,
            "created_at": self.created_at,
            "relation_types": [t.to_dict() for t in self.relation_types],
            "property_candidates": [c.to_dict() for c in self.property_candidates],
        }


def _read_schema_file(path: Path) -> Schema | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    known = {f for f in RelationType.__dataclass_fields__}
    types = [
        RelationType(**{k: v for k, v in entry.items() if k in known})
        for entry in data.get("relation_types", [])
    ]
    known_property = {f for f in RelationPropertyCandidate.__dataclass_fields__}
    properties = [
        RelationPropertyCandidate(**{k: v for k, v in entry.items() if k in known_property})
        for entry in data.get("property_candidates", [])
    ]
    return Schema(
        version=int(data.get("version", 1)),
        schema_id=str(data.get("schema_id", "")),
        created_at=str(data.get("created_at", "")),
        relation_types=types,
        property_candidates=properties,
    )


def load_schema(paths: TalamusPaths) -> Schema:
    path = schema_path(paths)
    schema = _read_schema_file(path)
    if schema is not None:
        return schema
    # Migration: a pre-global brain has its schema in the legacy per-brain spot —
    # the first global read seeds the shared file from it (non-destructive: the
    # local file stays, it simply stops being read).
    legacy = lab_dir(paths) / "schema.json"
    if path != legacy:
        migrated = _read_schema_file(legacy)
        if migrated is not None:
            save_schema(paths, migrated)
            _log_event(paths, "schema_migrated_to_global", {"from": str(legacy)})
            return migrated
    return Schema(schema_id=f"schema-{time.strftime('%Y%m%d')}-v1", created_at=_now())


def save_schema(paths: TalamusPaths, schema: Schema) -> None:
    target = schema_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(schema.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)


def _log_event(paths: TalamusPaths, event: str, detail: dict) -> None:
    target = history_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": _now(), "event": event, **detail}, ensure_ascii=False))
        handle.write("\n")


def read_history(paths: TalamusPaths) -> list[dict]:
    path = history_path(paths)
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


# ---------------------------------------------------------------- evidence


def collect_evidence(
    paths: TalamusPaths, notes: list[CanonicalNote] | None = None
) -> list[Evidence]:
    """Deterministic evidence pass: every raw relation surface becomes a record."""
    notes = notes if notes is not None else load_notes(paths)
    records: list[Evidence] = []
    now = _now()
    for note in notes:
        ref = note.sources[0].normalized_path if note.sources else ""
        for relation in note.relations:
            if not relation.target.strip() or not relation.relation.strip():
                continue
            records.append(
                Evidence(
                    source_note=note.title,
                    source_ref=ref,
                    subject=relation.source or note.title,
                    predicate_surface=relation.relation.strip(),
                    object=relation.target,
                    context=note.summary,
                    suggested_type=normalize_relation(relation.relation),
                    created_at=now,
                )
            )
    lab_dir(paths).mkdir(parents=True, exist_ok=True)
    with evidence_path(paths).open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False))
            handle.write("\n")
    return records


def cluster_unexplained(evidence: list[Evidence]) -> dict[str, list[Evidence]]:
    """Group the surfaces the fixed types flatten to ``related``, by stemmed key."""
    clusters: dict[str, list[Evidence]] = {}
    for record in evidence:
        if record.suggested_type != "related":
            continue  # the fixed baseline already explains it
        key = surface_key(record.predicate_surface)
        if not key:
            continue
        clusters.setdefault(key, []).append(record)
    return clusters


# ---------------------------------------------------------------- induction

_NAMING_PROMPT = """You are an ontologist. For each CLUSTER of relations observed in the
corpus (same surface form), propose a reusable relation type. Use ENGLISH for the
type name and definition (the schema is the machine layer: one canonical language
keeps it consistent across corpora). Return ONLY a JSON array, one object per cluster:
[{{"cluster_key": "<key>", "name": "<short-kebab-name>", "definition": "<one sentence>",
  "inverse": "<inverse name or empty>"}}]

OBSERVED CLUSTERS:
{clusters}
"""


def induce_candidates(
    paths: TalamusPaths,
    router: Router,
    min_support: int = DEFAULT_MIN_SUPPORT,
) -> list[RelationType]:
    """Induce candidate relation types from unexplained surfaces. One LLM call.

    Deterministic clustering decides WHAT becomes a candidate (support thresholds);
    the LLM only names and defines. Candidates are appended to the schema with
    status ``candidate`` and queued for review — runtime is untouched (F5.10).
    """
    evidence = collect_evidence(paths)
    clusters = cluster_unexplained(evidence)
    eligible = {
        key: records
        for key, records in clusters.items()
        if len(records) >= min_support and len({r.source_note for r in records}) >= 2
    }
    if not eligible:
        return []
    schema = load_schema(paths)
    known_surfaces = {s for t in schema.relation_types for s in t.surfaces}
    eligible = {k: v for k, v in eligible.items() if k not in known_surfaces}
    if not eligible:
        return []
    cluster_text = "\n".join(
        f'- chiave "{key}": {len(records)} osservazioni, es. '
        f'"{records[0].subject} {records[0].predicate_surface} {records[0].object}"'
        for key, records in sorted(eligible.items())
    )
    llm = router.for_task(TaskClass.ONTOLOGY_NAMING)
    raw = llm.complete(_NAMING_PROMPT.format(clusters=cluster_text))
    try:
        proposals = json_array(raw)
    except (ValueError, json.JSONDecodeError):
        proposals = []
    by_key = {str(p.get("cluster_key", "")): p for p in proposals if isinstance(p, dict)}
    created: list[RelationType] = []
    for key, records in sorted(eligible.items()):
        proposal = by_key.get(key, {})
        name = str(proposal.get("name", "")).strip() or re.sub(r"\s+", "-", key)
        type_id = "rel:" + re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
        if schema.by_id(type_id) is not None:
            continue
        candidate = RelationType(
            id=type_id,
            name=name,
            definition=str(proposal.get("definition", "")).strip(),
            inverse=str(proposal.get("inverse", "")).strip(),
            surfaces=[key],
            examples=[
                f"{r.subject} —{r.predicate_surface}→ {r.object} ({r.source_ref})"
                for r in records[:3]
            ],
            support=len(records),
            distinct_notes=len({r.source_note for r in records}),
            confidence=min(0.95, 0.5 + 0.05 * len(records)),
            status="candidate",
            valid_from=_now(),
        )
        schema.relation_types.append(candidate)
        created.append(candidate)
        _log_event(
            paths,
            "candidate_induced",
            {"type": type_id, "support": candidate.support, "surfaces": candidate.surfaces},
        )
    if created:
        save_schema(paths, schema)
        try:
            from talamus.review import ReviewQueue

            queue = ReviewQueue(paths)
            for candidate in created:
                queue.add(
                    "ontology_candidate",
                    f"Nuovo tipo di relazione proposto: {candidate.name}",
                    {"type_id": candidate.id, "support": candidate.support},
                )
        except Exception:  # review queue is a convenience mirror, never fatal
            pass
    return created


# ---------------------------------------------------------------- property induction


def _property_id(property_name: str, type_id: str, value: str = "") -> str:
    return f"prop:{property_name}:{type_id}{':' + value if value else ''}"


def _edge_ref(edge: dict) -> str:
    return f"{edge['source']}-[{edge['relation']}]->{edge['target']}"


def _schema_edges(paths: TalamusPaths, schema: Schema) -> list[dict]:
    active_names = {
        rel_type.name for rel_type in schema.relation_types if rel_type.status == "active"
    }
    if not active_names:
        return []
    ontology = build_ontology(load_notes(paths), active_surface_map(paths))
    edges: list[dict] = []
    for edge in ontology.get("edges", []):
        relation = str(edge.get("type", ""))
        if relation not in active_names:
            continue
        item = {
            "source": str(edge.get("source", "")),
            "relation": relation,
            "target": str(edge.get("target", "")),
        }
        item["ref"] = _edge_ref(item)
        edges.append(item)
    return sorted(edges, key=lambda item: (item["source"], item["relation"], item["target"]))


def _witness_note_count(witnesses: list[dict]) -> int:
    notes: set[str] = set()
    for witness in witnesses:
        for edge in witness.get("edges", []):
            source = str(edge.get("source", "")).strip()
            if source:
                notes.add(source)
    return len(notes)


def _candidate_known(schema: Schema, property_name: str, type_id: str, value: str = "") -> bool:
    rel_type = schema.by_id(type_id)
    if rel_type is not None:
        if property_name == "inverse_of" and rel_type.inverse_of == value:
            return True
        if property_name == "transitive" and rel_type.transitive:
            return True
        if property_name == "symmetric" and rel_type.symmetric:
            return True
    for candidate in schema.property_candidates:
        if candidate.status not in ("candidate", "active"):
            continue
        if candidate.property != property_name:
            continue
        if candidate.type_id == type_id and candidate.value == value:
            return True
        # inverse_of pairs are unordered: the mirrored candidate covers both types.
        if (
            property_name == "inverse_of"
            and candidate.type_id == value
            and candidate.value == type_id
        ):
            return True
    return False


def _property_candidate(
    property_name: str,
    type_id: str,
    witnesses: list[dict],
    value: str = "",
) -> RelationPropertyCandidate:
    examples = [str(witness.get("example", "")) for witness in witnesses[:3]]
    return RelationPropertyCandidate(
        id=_property_id(property_name, type_id, value),
        property=property_name,
        type_id=type_id,
        value=value,
        witnesses=witnesses,
        examples=examples,
        support=len(witnesses),
        distinct_notes=_witness_note_count(witnesses),
        confidence=min(0.95, 0.5 + 0.05 * len(witnesses)),
        status="candidate",
        valid_from=_now(),
    )


def infer_property_candidates(
    paths: TalamusPaths,
    min_support: int = PROMOTION_MIN_SUPPORT,
    min_notes: int = PROMOTION_MIN_NOTES,
) -> list[RelationPropertyCandidate]:
    """Induce inverse/transitive/symmetric property candidates structurally.

    This never calls an LLM. A property enters runtime only after the existing
    ontology apply flow promotes the candidate.
    """
    schema = load_schema(paths)
    active = [rel_type for rel_type in schema.relation_types if rel_type.status == "active"]
    if not active:
        return []
    edges = _schema_edges(paths, schema)
    by_relation: dict[str, list[dict]] = {}
    by_key: dict[tuple[str, str, str], dict] = {}
    for edge in edges:
        by_relation.setdefault(edge["relation"], []).append(edge)
        by_key[(edge["source"], edge["relation"], edge["target"])] = edge

    created: list[RelationPropertyCandidate] = []

    for left_index, left_type in enumerate(active):
        left_edges = by_relation.get(left_type.name, [])
        for right_type in active[left_index + 1 :]:
            if _candidate_known(schema, "inverse_of", left_type.id, right_type.id):
                continue
            witnesses: list[dict] = []
            for edge in left_edges:
                reverse = by_key.get((edge["target"], right_type.name, edge["source"]))
                if reverse is None:
                    continue
                witnesses.append(
                    {
                        "source": edge["source"],
                        "target": edge["target"],
                        "edges": [edge, reverse],
                        "via": [edge["ref"], reverse["ref"]],
                        "example": (
                            f"{edge['source']} -[{left_type.name}]-> {edge['target']} "
                            f"and {reverse['source']} -[{right_type.name}]-> {reverse['target']}"
                        ),
                    }
                )
            if len(witnesses) >= min_support and _witness_note_count(witnesses) >= min_notes:
                created.append(
                    _property_candidate("inverse_of", left_type.id, witnesses, right_type.id)
                )

    for rel_type in active:
        if not _candidate_known(schema, "transitive", rel_type.id):
            witnesses = []
            relation_edges = by_relation.get(rel_type.name, [])
            for first in relation_edges:
                for second in relation_edges:
                    if first["target"] != second["source"] or first["source"] == second["target"]:
                        continue
                    witness = by_key.get((first["source"], rel_type.name, second["target"]))
                    if witness is None:
                        continue
                    witnesses.append(
                        {
                            "source": first["source"],
                            "middle": first["target"],
                            "target": second["target"],
                            "edges": [first, second, witness],
                            "via": [first["ref"], second["ref"], witness["ref"]],
                            "example": (
                                f"{first['source']} -[{rel_type.name}]-> {first['target']} "
                                f"-[{rel_type.name}]-> {second['target']} "
                                f"witnessed by {witness['ref']}"
                            ),
                        }
                    )
            if len(witnesses) >= min_support and _witness_note_count(witnesses) >= min_notes:
                created.append(_property_candidate("transitive", rel_type.id, witnesses))

        if not _candidate_known(schema, "symmetric", rel_type.id):
            witnesses = []
            seen_pairs: set[tuple[str, str]] = set()
            for edge in by_relation.get(rel_type.name, []):
                reverse = by_key.get((edge["target"], rel_type.name, edge["source"]))
                if reverse is None:
                    continue
                pair = tuple(sorted((edge["source"], edge["target"])))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                witnesses.append(
                    {
                        "source": edge["source"],
                        "target": edge["target"],
                        "edges": [edge, reverse],
                        "via": [edge["ref"], reverse["ref"]],
                        "example": (
                            f"{edge['source']} -[{rel_type.name}]-> {edge['target']} "
                            f"and {reverse['source']} -[{rel_type.name}]-> {reverse['target']}"
                        ),
                    }
                )
            if len(witnesses) >= min_support and _witness_note_count(witnesses) >= min_notes:
                created.append(_property_candidate("symmetric", rel_type.id, witnesses))

    if created:
        known_ids = {candidate.id for candidate in schema.property_candidates}
        created = [candidate for candidate in created if candidate.id not in known_ids]
    if not created:
        return []
    schema.property_candidates.extend(created)
    save_schema(paths, schema)
    for candidate in created:
        _log_event(
            paths,
            "property_candidate_induced",
            {
                "candidate": candidate.id,
                "property": candidate.property,
                "type": candidate.type_id,
                "value": candidate.value,
                "support": candidate.support,
            },
        )
    try:
        from talamus.review import ReviewQueue

        queue = ReviewQueue(paths)
        for candidate in created:
            queue.add(
                "property",
                f"Ontology property proposed: {candidate.property} on {candidate.type_id}",
                candidate.to_dict(),
            )
    except Exception:
        pass
    return created


# ---------------------------------------------------------------- closure


def _explicit_edges_for_closure(ontology: dict, active_names: set[str]) -> list[dict]:
    edges: list[dict] = []
    for edge in ontology.get("edges", []):
        relation = str(edge.get("type", ""))
        if relation not in active_names:
            continue
        item = {
            "source": str(edge.get("source", "")),
            "relation": relation,
            "target": str(edge.get("target", "")),
        }
        item["ref"] = _edge_ref(item)
        edges.append(item)
    return sorted(edges, key=lambda item: (item["source"], item["relation"], item["target"]))


def rebuild_inferred_ontology(paths: TalamusPaths, ontology: dict | None = None) -> dict:
    """Rebuild the derived closure cache from active relation properties."""
    schema = load_schema(paths)
    ontology = ontology if ontology is not None else load_ontology(paths)
    active = [rel_type for rel_type in schema.relation_types if rel_type.status == "active"]
    active_by_id = {rel_type.id: rel_type for rel_type in active}
    active_by_name = {rel_type.name: rel_type for rel_type in active}
    explicit_edges = _explicit_edges_for_closure(ontology, set(active_by_name))
    explicit_keys = {(e["source"], e["relation"], e["target"]) for e in explicit_edges}
    by_relation: dict[str, list[dict]] = {}
    for edge in explicit_edges:
        by_relation.setdefault(edge["relation"], []).append(edge)
    inferred_by_key: dict[tuple[str, str, str], dict] = {}

    def add_edge(source: str, relation: str, target: str, rule: str, via: list[str]) -> None:
        key = (source, relation, target)
        if source == target or key in explicit_keys or key in inferred_by_key:
            return
        inferred_by_key[key] = {
            "source": source,
            "relation": relation,
            "type": relation,
            "target": target,
            "inferred": True,
            "rule": rule,
            "via": via,
            "schema_version": schema.version,
        }

    for rel_type in active:
        relation_edges = by_relation.get(rel_type.name, [])
        inverse_type = active_by_id.get(rel_type.inverse_of)
        if inverse_type is not None:
            for edge in relation_edges:
                add_edge(
                    edge["target"], inverse_type.name, edge["source"], "inverse_of", [edge["ref"]]
                )
        if rel_type.symmetric:
            for edge in relation_edges:
                add_edge(edge["target"], rel_type.name, edge["source"], "symmetric", [edge["ref"]])
        if rel_type.transitive:
            for first in relation_edges:
                for second in relation_edges:
                    if first["target"] == second["source"]:
                        add_edge(
                            first["source"],
                            rel_type.name,
                            second["target"],
                            "transitive",
                            [first["ref"], second["ref"]],
                        )

    edges = sorted(
        inferred_by_key.values(),
        key=lambda edge: (edge["source"], edge["relation"], edge["target"], edge["rule"]),
    )
    inferred = {"schema_version": schema.version, "edges": edges}
    save_inferred_ontology(paths, inferred)
    return inferred


# ---------------------------------------------------------------- promotion


def _promotion_blocker(candidate: RelationType | RelationPropertyCandidate, force: bool) -> str:
    if force:
        return ""
    if candidate.support < PROMOTION_MIN_SUPPORT:
        return (
            f"support {candidate.support} < {PROMOTION_MIN_SUPPORT} "
            f"(rule 12.6; use --force to override)"
        )
    if candidate.distinct_notes < PROMOTION_MIN_NOTES:
        return (
            f"distinct notes {candidate.distinct_notes} < {PROMOTION_MIN_NOTES} "
            f"(rule 12.6; use --force to override)"
        )
    return ""


def promote_candidate(paths: TalamusPaths, type_id: str, force: bool = False) -> tuple[bool, str]:
    """Promote a relation-type or property candidate into the active schema."""
    schema = load_schema(paths)
    candidate = schema.by_id(type_id)
    if candidate is not None:
        if candidate.status == "active":
            return False, f"'{type_id}' is already active"
        blocker = _promotion_blocker(candidate, force)
        if blocker:
            return False, blocker
        if not force:
            active_names = {
                t.name for t in schema.relation_types if t.status == "active" and t.id != type_id
            }
            if candidate.name in active_names:
                return False, f"name '{candidate.name}' conflicts with an active type"
        candidate.status = "active"
        candidate.valid_from = _now()
        schema.version += 1
        save_schema(paths, schema)
        _log_event(paths, "promoted", {"type": type_id, "schema_version": schema.version})
        _rebuild_with_schema(paths)
        return True, f"'{type_id}' is now active (schema v{schema.version})"

    property_candidate = schema.by_property_id(type_id)
    if property_candidate is None:
        return False, f"no pending candidate '{type_id}'"
    if property_candidate.status == "active":
        return False, f"'{type_id}' is already active"
    if property_candidate.status != "candidate":
        return False, f"no pending candidate '{type_id}'"
    blocker = _promotion_blocker(property_candidate, force)
    if blocker:
        return False, blocker
    rel_type = schema.by_id(property_candidate.type_id)
    if rel_type is None or rel_type.status != "active":
        return False, f"no active type '{property_candidate.type_id}'"
    if property_candidate.property == "inverse_of":
        inverse_type = schema.by_id(property_candidate.value)
        if inverse_type is None or inverse_type.status != "active":
            return False, f"no active inverse type '{property_candidate.value}'"
        rel_type.inverse_of = inverse_type.id
        inverse_type.inverse_of = rel_type.id
    elif property_candidate.property == "transitive":
        rel_type.transitive = True
    elif property_candidate.property == "symmetric":
        rel_type.symmetric = True
    else:
        return False, f"unknown property '{property_candidate.property}'"
    property_candidate.status = "active"
    property_candidate.valid_from = _now()
    schema.version += 1
    save_schema(paths, schema)
    _log_event(
        paths,
        "property_promoted",
        {
            "candidate": property_candidate.id,
            "property": property_candidate.property,
            "type": property_candidate.type_id,
            "value": property_candidate.value,
            "schema_version": schema.version,
        },
    )
    _rebuild_with_schema(paths)
    return True, f"'{type_id}' is now active (schema v{schema.version})"


def reject_candidate(paths: TalamusPaths, type_id: str, reason: str = "") -> tuple[bool, str]:
    schema = load_schema(paths)
    candidate = schema.by_id(type_id)
    if candidate is not None and candidate.status == "candidate":
        candidate.status = "deprecated"  # kept, never deleted
        candidate.valid_to = _now()
        save_schema(paths, schema)
        _log_event(paths, "rejected", {"type": type_id, "reason": reason})
        return True, f"'{type_id}' rejected (kept in schema history)"
    property_candidate = schema.by_property_id(type_id)
    if property_candidate is not None and property_candidate.status == "candidate":
        property_candidate.status = "deprecated"
        property_candidate.valid_to = _now()
        save_schema(paths, schema)
        _log_event(
            paths,
            "property_rejected",
            {"candidate": type_id, "property": property_candidate.property, "reason": reason},
        )
        return True, f"'{type_id}' rejected (kept in schema history)"
    return False, f"no pending candidate '{type_id}'"


def deprecate_type(paths: TalamusPaths, type_id: str, reason: str = "") -> tuple[bool, str]:
    schema = load_schema(paths)
    rel_type = schema.by_id(type_id)
    if rel_type is None or rel_type.status != "active":
        return False, f"no active type '{type_id}'"
    rel_type.status = "deprecated"
    rel_type.valid_to = _now()
    schema.version += 1
    save_schema(paths, schema)
    _log_event(paths, "deprecated", {"type": type_id, "reason": reason})
    _rebuild_with_schema(paths)
    return True, f"'{type_id}' deprecated (schema v{schema.version})"


# ---------------------------------------------------------------- runtime hook


def active_surface_map(paths: TalamusPaths) -> dict[str, str]:
    """surface key -> type name, for ACTIVE types only (candidates need opt-in)."""
    schema = load_schema(paths)
    mapping: dict[str, str] = {}
    for rel_type in schema.relation_types:
        if rel_type.status != "active":
            continue
        for surface in rel_type.surfaces:
            mapping[surface] = rel_type.name
    return mapping


def _rebuild_with_schema(paths: TalamusPaths) -> None:
    """Re-type the concept map after a schema change (notes never move)."""
    notes = load_notes(paths)
    ontology = build_ontology(notes, active_surface_map(paths))
    save_ontology(paths.ontology_file, ontology)
    rebuild_inferred_ontology(paths, ontology)


# ---------------------------------------------------------------- metrics


def coverage(paths: TalamusPaths) -> dict:
    """Share of edges carrying a real type instead of ``related`` (F5.7)."""
    ontology = load_ontology(paths)
    edges = ontology.get("edges", [])
    if not edges:
        return {"edges": 0, "non_related": 0, "non_related_share": 0.0}
    non_related = sum(1 for e in edges if e.get("type") != "related")
    return {
        "edges": len(edges),
        "non_related": non_related,
        "non_related_share": round(non_related / len(edges), 4),
    }


def stability(paths: TalamusPaths, runs: int = 3) -> dict:
    """Jaccard similarity of eligible cluster keys across repeated runs (E1)."""
    key_sets: list[set[str]] = []
    notes = load_notes(paths)
    for _ in range(runs):
        clusters = cluster_unexplained(collect_evidence(paths, notes))
        key_sets.append(set(clusters))
    if not key_sets or not any(key_sets):
        return {"runs": runs, "jaccard": 1.0}
    union = set().union(*key_sets)
    intersection = set(key_sets[0]).intersection(*key_sets[1:])
    return {"runs": runs, "jaccard": round(len(intersection) / max(len(union), 1), 4)}


def expansion_retriever(paths: TalamusPaths):
    """Retriever (question, k) -> titles AFTER ontology expansion — the surface the
    emergent schema actually changes (typed edges are expanded before ``related``)."""
    from talamus.indexes import search_index

    def run(question: str, k: int) -> list[str]:
        seeds = [h["title"] for h in search_index(paths, question, limit=k)]
        ontology = load_ontology(paths)
        ranked = list(seeds)
        for title in seeds:
            connected = sorted(
                neighbors(ontology, title),
                key=lambda n: 0 if n.get("relation") != "related" else 1,
            )
            for neighbor in connected:
                if neighbor["title"] not in ranked:
                    ranked.append(neighbor["title"])
        return ranked[:k]

    return run


def ontology_eval(paths: TalamusPaths, cases_file: Path, k: int = 5) -> dict:
    """Retrieval with the fixed baseline vs the active emergent schema (E3).

    Rebuilds the concept map twice (without/with active surfaces), measures both,
    then restores the active state. Deterministic, no LLM.
    """
    from talamus.eval import evaluate, load_cases

    cases = load_cases(cases_file)
    notes = load_notes(paths)
    save_ontology(paths.ontology_file, build_ontology(notes, None))
    baseline = evaluate(cases, expansion_retriever(paths), k=k)
    save_ontology(paths.ontology_file, build_ontology(notes, active_surface_map(paths)))
    emergent = evaluate(cases, expansion_retriever(paths), k=k)
    return {
        "k": k,
        "n_cases": len(cases),
        "baseline": {
            "recall_at_k": round(baseline.recall_at_k, 4),
            "mrr": round(baseline.mrr, 4),
            "hit_rate": round(baseline.hit_rate, 4),
        },
        "emergent": {
            "recall_at_k": round(emergent.recall_at_k, 4),
            "mrr": round(emergent.mrr, 4),
            "hit_rate": round(emergent.hit_rate, 4),
        },
        "lift": {
            "recall_at_k": round(emergent.recall_at_k - baseline.recall_at_k, 4),
            "mrr": round(emergent.mrr - baseline.mrr, 4),
        },
        "coverage": coverage(paths),
    }


def schema_status(paths: TalamusPaths) -> dict:
    schema = load_schema(paths)
    by_status: dict[str, int] = {}
    for rel_type in schema.relation_types:
        by_status[rel_type.status] = by_status.get(rel_type.status, 0) + 1
    for candidate in schema.property_candidates:
        key = f"property_{candidate.status}"
        by_status[key] = by_status.get(key, 0) + 1
    return {
        "schema_id": schema.schema_id,
        "version": schema.version,
        "types": by_status,
        "coverage": coverage(paths),
    }
