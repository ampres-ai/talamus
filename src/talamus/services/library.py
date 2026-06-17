from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from talamus.models import CanonicalNote
from talamus.naming import note_filename
from talamus.paths import TalamusPaths
from talamus.services.result import ServiceResult
from talamus.store import load_notes

T = TypeVar("T")


@dataclass(frozen=True)
class LibraryNoteSummary:
    title: str
    summary: str
    aliases: list[str]
    tags: list[str]
    confidence: float
    updated_at: str
    source_count: int
    relation_count: int
    proposed_link_count: int
    markdown_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LibraryReport:
    root: str
    notes: list[LibraryNoteSummary]

    @property
    def note_count(self) -> int:
        return len(self.notes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "note_count": self.note_count,
            "notes": [note.to_dict() for note in self.notes],
        }


@dataclass(frozen=True)
class LibraryNoteDetail:
    title: str
    found: bool
    summary: str = ""
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    updated_at: str = ""
    markdown: str = ""
    markdown_path: str = ""
    body_sections: dict[str, str] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    proposed_links: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_library_notes(root: str | Path) -> ServiceResult[LibraryReport]:
    paths = TalamusPaths(Path(root))
    try:
        notes = load_notes(paths)
    except (OSError, TypeError, ValueError, AttributeError, json.JSONDecodeError) as exc:
        return _library_error(exc)
    report = LibraryReport(
        root=str(paths.project_root.resolve()),
        notes=[
            _summary(paths, note) for note in sorted(notes, key=lambda item: item.title.lower())
        ],
    )
    return ServiceResult(
        success=True,
        message="Library notes loaded",
        code="library_notes_loaded",
        data=report,
    )


def get_library_note(root: str | Path, title: str) -> ServiceResult[LibraryNoteDetail]:
    paths = TalamusPaths(Path(root))
    try:
        notes = load_notes(paths)
        note = _find_note(notes, title)
        if note is None:
            return ServiceResult(
                success=False,
                message=f"Note not found: {title}",
                code="library_note_not_found",
                data=LibraryNoteDetail(title=title, found=False),
            )
        detail = _detail(paths, note)
    except (OSError, TypeError, ValueError, AttributeError, json.JSONDecodeError) as exc:
        return _library_error(exc)
    return ServiceResult(
        success=True,
        message=f"Note {note.title!r} loaded",
        code="library_note_loaded",
        data=detail,
    )


def _summary(paths: TalamusPaths, note: CanonicalNote) -> LibraryNoteSummary:
    return LibraryNoteSummary(
        title=note.title,
        summary=note.summary,
        aliases=list(note.aliases),
        tags=list(note.tags),
        confidence=note.confidence,
        updated_at=note.updated_at,
        source_count=len(note.sources),
        relation_count=len(note.relations),
        proposed_link_count=len(note.proposed_links),
        markdown_path=str(paths.notes / note_filename(note.title)),
    )


def _detail(paths: TalamusPaths, note: CanonicalNote) -> LibraryNoteDetail:
    markdown_path = paths.notes / note_filename(note.title)
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.is_file() else ""
    return LibraryNoteDetail(
        title=note.title,
        found=True,
        summary=note.summary,
        aliases=list(note.aliases),
        tags=list(note.tags),
        confidence=note.confidence,
        updated_at=note.updated_at,
        markdown=markdown,
        markdown_path=str(markdown_path),
        body_sections=dict(note.body_sections),
        sources=[asdict(source) for source in note.sources],
        relations=[asdict(relation) for relation in note.relations],
        proposed_links=[asdict(link) for link in note.proposed_links],
    )


def _find_note(notes: list[CanonicalNote], title: str) -> CanonicalNote | None:
    wanted = title.strip().lower()
    for note in notes:
        if note.title.lower() == wanted:
            return note
    return None


def _library_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Library service error: {exc}",
        code="library_service_error",
    )
