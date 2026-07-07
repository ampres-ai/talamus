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
from talamus.ontology import build_ontology, load_ontology, neighbors, normalize_relation
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
class Schema:
    version: int = 1
    schema_id: str = ""
    created_at: str = ""
    relation_types: list[RelationType] = field(default_factory=list)

    def by_id(self, type_id: str) -> RelationType | None:
        for rel_type in self.relation_types:
            if rel_type.id == type_id:
                return rel_type
        return None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "schema_id": self.schema_id,
            "created_at": self.created_at,
            "relation_types": [t.to_dict() for t in self.relation_types],
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
    return Schema(
        version=int(data.get("version", 1)),
        schema_id=str(data.get("schema_id", "")),
        created_at=str(data.get("created_at", "")),
        relation_types=types,
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


# ---------------------------------------------------------------- promotion


def promote_candidate(paths: TalamusPaths, type_id: str, force: bool = False) -> tuple[bool, str]:
    """Candidate -> active, enforcing the PRD 12.6 promotion rules (unless forced)."""
    schema = load_schema(paths)
    candidate = schema.by_id(type_id)
    if candidate is None:
        return False, f"no relation type '{type_id}' in the schema"
    if candidate.status == "active":
        return False, f"'{type_id}' is already active"
    if not force:
        if candidate.support < PROMOTION_MIN_SUPPORT:
            return False, (
                f"support {candidate.support} < {PROMOTION_MIN_SUPPORT} "
                f"(rule 12.6; use --force to override)"
            )
        if candidate.distinct_notes < PROMOTION_MIN_NOTES:
            return False, (
                f"distinct notes {candidate.distinct_notes} < {PROMOTION_MIN_NOTES} "
                f"(rule 12.6; use --force to override)"
            )
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


def reject_candidate(paths: TalamusPaths, type_id: str, reason: str = "") -> tuple[bool, str]:
    schema = load_schema(paths)
    candidate = schema.by_id(type_id)
    if candidate is None or candidate.status != "candidate":
        return False, f"no pending candidate '{type_id}'"
    candidate.status = "deprecated"  # kept, never deleted
    candidate.valid_to = _now()
    save_schema(paths, schema)
    _log_event(paths, "rejected", {"type": type_id, "reason": reason})
    return True, f"'{type_id}' rejected (kept in schema history)"


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
    save_ontology(paths.ontology_file, build_ontology(notes, active_surface_map(paths)))


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
    return {
        "schema_id": schema.schema_id,
        "version": schema.version,
        "types": by_status,
        "coverage": coverage(paths),
    }
