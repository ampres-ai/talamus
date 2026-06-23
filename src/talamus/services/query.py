from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from talamus.paths import TalamusPaths
from talamus.recall import read_note_text, recall_context
from talamus.scope import default_scope, scoped_context_items, scoped_search
from talamus.services.result import ServiceResult
from talamus.timeline import note_as_of, note_history

T = TypeVar("T")


@dataclass(frozen=True)
class SearchHit:
    title: str
    summary: str
    scope: str = ""
    brain_id: str = ""
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        payload = {"title": self.title, "summary": self.summary}
        if self.scope:
            payload["scope"] = self.scope
        if self.brain_id:
            payload["brain_id"] = self.brain_id
        if self.path:
            payload["path"] = self.path
        return payload


@dataclass(frozen=True)
class SearchReport:
    query: str
    scope: str
    hits: list[SearchHit]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "scope": self.scope,
            "hits": [hit.to_dict() for hit in self.hits],
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class ReadNoteResult:
    title: str
    found: bool
    markdown: str | None = None
    as_of: str = ""
    version: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecallResult:
    context: str
    scope: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OverviewResult:
    domains: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"domains": self.domains}


@dataclass(frozen=True)
class NoteHistoryResult:
    title: str
    versions: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def search_brain(
    root: str | Path,
    query: str,
    *,
    policy: str | None = None,
    limit: int = 5,
) -> ServiceResult[SearchReport]:
    root_path = Path(root)
    resolved_policy = policy or default_scope(root_path)
    try:
        results, warnings = scoped_search(root_path, query, resolved_policy, limit=limit)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _query_error(exc)
    report = SearchReport(
        query=query,
        scope=resolved_policy,
        hits=[_search_hit(item) for item in results],
        warnings=warnings,
    )
    return ServiceResult(
        success=True, message="Search completed", code="search_completed", data=report
    )


def read_note(
    root: str | Path, title: str, *, as_of: str | None = None
) -> ServiceResult[ReadNoteResult]:
    paths = TalamusPaths(Path(root))
    if as_of:
        try:
            version = note_as_of(paths, title, as_of)
        except (OSError, TypeError, ValueError, AttributeError) as exc:
            return _query_error(exc)
        result = ReadNoteResult(
            title=title, found=version is not None, as_of=as_of, version=version
        )
        if version is None:
            return ServiceResult(
                success=False,
                message=f"No version of {title!r} at {as_of}",
                code="note_version_not_found",
                data=result,
            )
        return ServiceResult(
            success=True,
            message=f"Note {title!r} version loaded",
            code="note_version_loaded",
            data=result,
        )
    try:
        markdown = read_note_text(paths, title)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _query_error(exc)
    result = ReadNoteResult(title=title, found=markdown is not None, markdown=markdown)
    if markdown is None:
        return ServiceResult(
            success=False,
            message=f"Note not found: {title}",
            code="note_not_found",
            data=result,
        )
    return ServiceResult(
        success=True, message=f"Note {title!r} loaded", code="note_loaded", data=result
    )


def recall_brain(
    root: str | Path,
    question: str,
    *,
    policy: str | None = None,
    limit: int = 5,
) -> ServiceResult[RecallResult]:
    root_path = Path(root)
    resolved_policy = policy or default_scope(root_path)
    warnings: list[str] = []
    try:
        if resolved_policy == "central-only":
            items, warnings = scoped_context_items(root_path, question, "central-only", limit=limit)
            context = _render_scoped_items(items) or "No relevant context found in the brain."
        else:
            context = recall_context(TalamusPaths(root_path), question, limit=limit)
            if resolved_policy in ("project+central", "all"):
                sub_policy = "central-only" if resolved_policy == "project+central" else "all"
                extra, warnings = scoped_context_items(
                    root_path, question, sub_policy, limit=limit, exclude_roots=[root_path]
                )
                if extra:
                    context += "\n\n" + _render_scoped_items(extra)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _query_error(exc)
    return ServiceResult(
        success=True,
        message="Recall context built",
        code="recall_completed",
        data=RecallResult(context=context, scope=resolved_policy, warnings=warnings),
    )


def brain_overview(root: str | Path) -> ServiceResult[OverviewResult]:
    """The brain's domain map (name, description, members): read-only, no LLM."""
    from talamus.domains import load_overview

    paths = TalamusPaths(Path(root))
    try:
        domains = load_overview(paths)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _query_error(exc)
    return ServiceResult(
        success=True,
        message="Overview loaded",
        code="overview_loaded",
        data=OverviewResult(domains=list(domains)),
    )


def note_history_view(root: str | Path, title: str) -> ServiceResult[NoteHistoryResult]:
    """A note's past versions (transaction time), oldest first."""
    paths = TalamusPaths(Path(root))
    try:
        versions = note_history(paths, title)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return _query_error(exc)
    return ServiceResult(
        success=True,
        message="Note history loaded",
        code="note_history_loaded",
        data=NoteHistoryResult(title=title, versions=list(versions)),
    )


def _search_hit(item: dict[str, Any]) -> SearchHit:
    return SearchHit(
        title=str(item.get("title", "")),
        summary=str(item.get("summary", "")),
        scope=str(item.get("scope", "")),
        brain_id=str(item.get("brain_id", "")),
        path=str(item.get("path", "")),
    )


def _render_scoped_items(items: list[dict]) -> str:
    return "\n".join(
        f"[{idx}] {item['path']}\n{item['content']}" for idx, item in enumerate(items, start=1)
    )


def _query_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Query service error: {exc}",
        code="query_service_error",
    )
