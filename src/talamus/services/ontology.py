from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypeVar

from talamus.ontology_lab import (
    deprecate_type,
    load_schema,
    promote_candidate,
    read_history,
    reject_candidate,
    schema_status,
)
from talamus.paths import TalamusPaths
from talamus.services.result import ServiceResult

T = TypeVar("T")


@dataclass(frozen=True)
class OntologyStatusReport:
    schema_id: str
    version: int
    types: dict[str, int]
    coverage: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OntologyRelationType:
    id: str
    name: str
    definition: str
    inverse: str
    surfaces: list[str]
    examples: list[str]
    support: int
    distinct_notes: int
    confidence: float
    status: str
    valid_from: str
    valid_to: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OntologyPropertyCandidate:
    id: str
    kind: str
    property: str
    type_id: str
    value: str
    witnesses: list[dict[str, Any]]
    examples: list[str]
    support: int
    distinct_notes: int
    confidence: float
    status: str
    valid_from: str
    valid_to: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OntologyDecision:
    type_id: str
    action: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class OntologyHistoryReport:
    events: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"events": self.events}


@dataclass(frozen=True)
class OntologySchemaExport:
    schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.schema


def get_ontology_status(root: str | Path) -> ServiceResult[OntologyStatusReport]:
    paths = TalamusPaths(Path(root))
    try:
        status = schema_status(paths)
        report = OntologyStatusReport(
            schema_id=str(status.get("schema_id", "")),
            version=int(status.get("version", 1)),
            types={str(key): int(value) for key, value in status.get("types", {}).items()},
            coverage=dict(status.get("coverage", {})),
        )
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _ontology_error(exc)
    return ServiceResult(
        success=True,
        message="Ontology status loaded",
        code="ontology_status_loaded",
        data=report,
    )


def list_ontology_candidates(
    root: str | Path, status: str = "candidate"
) -> ServiceResult[list[OntologyRelationType | OntologyPropertyCandidate]]:
    paths = TalamusPaths(Path(root))
    try:
        schema = load_schema(paths)
        items: list[OntologyRelationType | OntologyPropertyCandidate] = [
            _relation_type(rel_type)
            for rel_type in schema.relation_types
            if rel_type.status == status
        ]
        items.extend(
            _property_candidate(candidate)
            for candidate in schema.property_candidates
            if candidate.status == status
        )
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _ontology_error(exc)
    return ServiceResult(
        success=True,
        message="Ontology candidates loaded",
        code="ontology_candidates_loaded",
        data=items,
    )


def apply_ontology_candidate(
    root: str | Path, type_id: str, *, force: bool = False
) -> ServiceResult[OntologyDecision]:
    paths = TalamusPaths(Path(root))
    try:
        ok, message = promote_candidate(paths, type_id, force=force)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _ontology_error(exc)
    return _decision_result(ok, type_id, "applied", "apply_failed", message)


def reject_ontology_candidate(
    root: str | Path, type_id: str, *, reason: str = ""
) -> ServiceResult[OntologyDecision]:
    paths = TalamusPaths(Path(root))
    try:
        ok, message = reject_candidate(paths, type_id, reason)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _ontology_error(exc)
    return _decision_result(ok, type_id, "rejected", "reject_failed", message)


def deprecate_ontology_type(
    root: str | Path, type_id: str, *, reason: str = ""
) -> ServiceResult[OntologyDecision]:
    paths = TalamusPaths(Path(root))
    try:
        ok, message = deprecate_type(paths, type_id, reason)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _ontology_error(exc)
    return _decision_result(ok, type_id, "deprecated", "deprecate_failed", message)


def get_ontology_history(root: str | Path) -> ServiceResult[OntologyHistoryReport]:
    paths = TalamusPaths(Path(root))
    try:
        events = read_history(paths)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _ontology_error(exc)
    return ServiceResult(
        success=True,
        message="Ontology history loaded",
        code="ontology_history_loaded",
        data=OntologyHistoryReport(events=events),
    )


def export_ontology_schema(root: str | Path) -> ServiceResult[OntologySchemaExport]:
    paths = TalamusPaths(Path(root))
    try:
        schema = load_schema(paths).to_dict()
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _ontology_error(exc)
    return ServiceResult(
        success=True,
        message="Ontology schema exported",
        code="ontology_schema_exported",
        data=OntologySchemaExport(schema=schema),
    )


def _relation_type(rel_type: Any) -> OntologyRelationType:
    return OntologyRelationType(
        id=str(rel_type.id),
        name=str(rel_type.name),
        definition=str(rel_type.definition),
        inverse=str(rel_type.inverse),
        surfaces=list(rel_type.surfaces),
        examples=list(rel_type.examples),
        support=int(rel_type.support),
        distinct_notes=int(rel_type.distinct_notes),
        confidence=float(rel_type.confidence),
        status=str(rel_type.status),
        valid_from=str(rel_type.valid_from),
        valid_to=str(rel_type.valid_to),
    )


def _property_candidate(candidate: Any) -> OntologyPropertyCandidate:
    return OntologyPropertyCandidate(
        id=str(candidate.id),
        kind=str(candidate.kind),
        property=str(candidate.property),
        type_id=str(candidate.type_id),
        value=str(candidate.value),
        witnesses=[dict(witness) for witness in candidate.witnesses],
        examples=list(candidate.examples),
        support=int(candidate.support),
        distinct_notes=int(candidate.distinct_notes),
        confidence=float(candidate.confidence),
        status=str(candidate.status),
        valid_from=str(candidate.valid_from),
        valid_to=str(candidate.valid_to),
    )


def _decision_result(
    ok: bool,
    type_id: str,
    success_action: str,
    failure_action: str,
    message: str,
) -> ServiceResult[OntologyDecision]:
    return ServiceResult(
        success=ok,
        message=message,
        code="ontology_decision_applied" if ok else "ontology_decision_failed",
        data=OntologyDecision(
            type_id=type_id,
            action=success_action if ok else failure_action,
            message=message,
        ),
    )


def _ontology_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Ontology service error: {exc}",
        code="ontology_service_error",
    )
