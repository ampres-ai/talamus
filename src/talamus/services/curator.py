"""The Curator, first pass: one health run over every registered brain.

Large collections cannot depend on the owner running N commands per brain.
This service walks the registry and reports, per brain, everything that needs
attention — pending review decisions, captures waiting for an engine retry,
ontology candidates, stale derived caches — in one readable result. Zero LLM
calls. With ``fix=True`` it also applies the one fix that is mechanically
safe by construction: rebuilding stale derived caches (`reindex` touches only
derived data, never the notes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from talamus.paths import TalamusPaths
from talamus.registry import load_registry
from talamus.services.result import ServiceResult


@dataclass(frozen=True)
class BrainHealth:
    name: str
    root: str
    brain_type: str
    reachable: bool
    notes: int = 0
    cache_current: bool = True
    pending_captures: int = 0
    reviews_pending: int = 0
    ontology_candidates: int = 0
    jobs_active: int = 0
    provenance_issues: int = -1  # -1 = not scanned (deep pass only)
    fixed: list[str] = field(default_factory=list)

    @property
    def attention(self) -> bool:
        return bool(
            not self.reachable
            or not self.cache_current
            or self.pending_captures
            or self.reviews_pending
            or self.ontology_candidates
            or self.jobs_active
            or self.provenance_issues > 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "root": self.root,
            "type": self.brain_type,
            "reachable": self.reachable,
            "notes": self.notes,
            "cache_current": self.cache_current,
            "pending_captures": self.pending_captures,
            "reviews_pending": self.reviews_pending,
            "ontology_candidates": self.ontology_candidates,
            "jobs_active": self.jobs_active,
            "provenance_issues": self.provenance_issues,
            "attention": self.attention,
            "fixed": list(self.fixed),
        }


def _inspect_brain(
    root: Path, name: str, brain_type: str, fix: bool, deep: bool = False
) -> BrainHealth:
    from talamus.ingest import pending_captures
    from talamus.services.readiness import inspect_readiness

    if not (root / "talamus.json").is_file():
        return BrainHealth(name=name, root=str(root), brain_type=brain_type, reachable=False)
    report = inspect_readiness(root=str(root))
    fixed: list[str] = []
    cache_current = report.cache_current
    if fix and not cache_current:
        from talamus.services.diagnostics import reindex_brain

        result = reindex_brain(root)
        if result.success:
            fixed.append("reindexed stale cache")
            cache_current = True
    provenance_issues = -1
    if deep:
        provenance_issues = _provenance_issues(TalamusPaths(root))
    return BrainHealth(
        name=name,
        root=str(root),
        brain_type=brain_type,
        reachable=True,
        notes=report.notes,
        cache_current=cache_current,
        pending_captures=len(pending_captures(TalamusPaths(root))),
        reviews_pending=report.reviews_pending,
        ontology_candidates=report.ontology_candidates,
        jobs_active=report.jobs_active,
        provenance_issues=provenance_issues,
        fixed=fixed,
    )


def _provenance_issues(paths: TalamusPaths) -> int:
    """Deterministic provenance health across the brain: notes whose source is
    missing, changed or low-confidence. Re-extracts sources — slower on big
    brains, still zero LLM calls (that is why it lives behind --deep)."""
    from talamus.correct import provenance_status
    from talamus.store import load_notes

    issues = 0
    for note in load_notes(paths):
        try:
            status = provenance_status(paths, note).get("status", "ok")
        except (OSError, ValueError):
            status = "unreadable"
        if status != "ok":
            issues += 1
    return issues


def curate_brains(fix: bool = False, deep: bool = False) -> ServiceResult[list[BrainHealth]]:
    """One health pass over every registered brain (report-first; safe fixes
    only with ``fix=True``). Missing brains degrade to a row, never a failure."""
    try:
        registry = load_registry()
    except (OSError, ValueError) as exc:
        return ServiceResult(
            success=False, message=f"cannot read the brain registry: {exc}", code="registry_error"
        )
    rows = [
        _inspect_brain(brain.root(), brain.name, brain.type, fix, deep=deep)
        for brain in registry.brains
    ]
    needing = sum(1 for row in rows if row.attention)
    return ServiceResult(
        success=True,
        message=f"{len(rows)} brain(s) checked, {needing} need attention",
        code="curator_report",
        data=rows,
    )
