from __future__ import annotations

from dataclasses import dataclass

from talamus.models import CanonicalNote


@dataclass(frozen=True)
class NoteRegistry:
    title_by_key: dict[str, str]

    @staticmethod
    def _key(value: str) -> str:
        return value.strip().lower()

    @classmethod
    def from_notes(
        cls,
        notes: list[CanonicalNote],
        extra_aliases: dict[str, str] | None = None,
    ) -> NoteRegistry:
        title_by_key: dict[str, str] = {}
        for note in notes:
            title_by_key[cls._key(note.title)] = note.title
            for alias in note.aliases:
                title_by_key[cls._key(alias)] = note.title
        for alias, title in (extra_aliases or {}).items():
            title_by_key[cls._key(alias)] = title
        return cls(title_by_key)

    def resolve(self, target: str) -> str | None:
        return self.title_by_key.get(self._key(target))


def resolve_links(note: CanonicalNote, registry: NoteRegistry) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for proposed in note.proposed_links:
        title = registry.resolve(proposed.target)
        if title is None or title == note.title:
            continue  # irrisolvibile, o auto-link: una nota non si linka mai da sola
        resolved[proposed.anchor] = f"[[{title}|{proposed.anchor}]]"
    return resolved
