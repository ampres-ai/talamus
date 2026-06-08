from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SourceRef:
    raw_path: str
    normalized_path: str
    locator: str
    source_hash: str
    supported_claims: list[str]


@dataclass(frozen=True)
class ProposedLink:
    anchor: str
    target: str
    reason: str


@dataclass(frozen=True)
class Relation:
    source: str
    relation: str
    target: str
    confidence: float


@dataclass(frozen=True)
class CanonicalNote:
    note_id: str
    title: str
    aliases: list[str]
    folder: str
    tags: list[str]
    summary: str
    retrieval_text: str
    body_sections: dict[str, str]
    proposed_links: list[ProposedLink]
    relations: list[Relation]
    sources: list[SourceRef]
    confidence: float

    @classmethod
    def minimal(
        cls,
        title: str,
        *,
        confidence: float = 0.8,
        sources: list[SourceRef] | None = None,
    ) -> "CanonicalNote":
        note_id = title.lower().replace(" ", "-")
        return cls(
            note_id=note_id,
            title=title,
            aliases=[],
            folder="",
            tags=[],
            summary=f"{title}.",
            retrieval_text=title,
            body_sections={"summary": f"{title}."},
            proposed_links=[],
            relations=[],
            sources=sources or [],
            confidence=confidence,
        )

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.title.strip():
            errors.append("title is required")
        if not self.retrieval_text.strip():
            errors.append("retrieval_text is required")
        if not self.sources:
            errors.append("note has no sources")
        if self.confidence < 0 or self.confidence > 1:
            errors.append("confidence must be between 0 and 1")
        return errors

    def to_dict(self) -> dict:
        return asdict(self)
