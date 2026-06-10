"""Brain resolution and scoped (multi-brain) retrieval — PRD 9.1 / F1.

Resolution order: ``--root > --brain > --global > project ancestor > selected
global > global default``. The result carries *where it came from* so ``where
--json`` and traces can explain the decision.

Scope policies for read commands: ``project-only``, ``central-only``,
``project+central`` (default inside a project), ``all`` (default from the
central brain; sensitive brains excluded unless opted in). Cross-brain results
are pointers + markers — answers always read the real notes from the owning
brain (the federated index is never source truth).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from talamus.federation import search_federated
from talamus.recall import read_note_text, search_notes
from talamus.registry import central_brain, load_registry, selected_brain, talamus_home

SCOPE_POLICIES = ("project-only", "central-only", "project+central", "all")


@dataclass(frozen=True)
class ResolvedBrain:
    root: Path
    scope: str  # project | global | named | explicit
    source: str  # --root | --brain | --global | project-ancestor | selected-global | default-global


def _find_project_root(start: Path) -> Path | None:
    for directory in [start, *start.parents]:
        if (directory / "talamus.json").exists():
            return directory
    return None


def resolve_brain(
    root: str | None,
    brain: str | None,
    use_global: bool,
    cwd: Path | None = None,
    home: Path | None = None,
) -> ResolvedBrain:
    home = home or talamus_home()
    if root is not None:
        return ResolvedBrain(Path(root).resolve(), "explicit", "--root")
    if brain is not None:
        registered = load_registry(home).by_name(brain)
        target = registered.root() if registered is not None else home / brain
        return ResolvedBrain(target.resolve(), "named", "--brain")
    if use_global:
        return ResolvedBrain((home / "default").resolve(), "global", "--global")
    project = _find_project_root((cwd or Path.cwd()).resolve())
    if project is not None:
        return ResolvedBrain(project, "project", "project-ancestor")
    selected = selected_brain(home)
    if selected is not None:
        return ResolvedBrain(selected.root().resolve(), "named", "selected-global")
    return ResolvedBrain((home / "default").resolve(), "global", "default-global")


def resolve_init_root(
    root: str | None, brain: str | None, use_global: bool, cwd: Path | None = None
) -> ResolvedBrain:
    """``init`` never falls through scoping: no flags means the current directory."""
    if root is not None:
        return ResolvedBrain(Path(root).resolve(), "explicit", "--root")
    if brain is not None:
        return ResolvedBrain((talamus_home() / brain).resolve(), "named", "--brain")
    if use_global:
        return ResolvedBrain((talamus_home() / "default").resolve(), "global", "--global")
    return ResolvedBrain((cwd or Path.cwd()).resolve(), "project", "current-directory")


def default_scope(current_root: Path, home: Path | None = None) -> str:
    """F1.6: inside a project -> project+central; from the central brain -> all."""
    central = central_brain(home)
    if central is not None and central.root().resolve() == current_root.resolve():
        return "all"
    return "project+central"


def _marker(brain_name: str, brain_type: str) -> str:
    if brain_type == "central":
        return "[central]"
    if brain_type == "archive":
        return f"[archive:{brain_name}]"
    return f"[project:{brain_name}]"


def scoped_search(
    current_root: Path,
    query: str,
    policy: str,
    limit: int = 5,
    home: Path | None = None,
    include_sensitive: bool = False,
) -> tuple[list[dict], list[str]]:
    """Search under a scope policy. Returns ({title, summary, scope, brain_id?, path?}, warnings).

    Local results come from each brain's own indexes; ``all`` queries the
    federated index and verifies each pointer against the owning brain's files.
    """
    if policy not in SCOPE_POLICIES:
        raise ValueError(f"scope must be one of {SCOPE_POLICIES}, got {policy!r}")
    home = home or talamus_home()
    warnings: list[str] = []
    central = central_brain(home)
    central_root = central.root().resolve() if central is not None else None
    current = current_root.resolve()

    if policy == "all":
        registry = load_registry(home)
        boost: list[str] = []
        current_entry = registry.by_path(current)
        if current_entry is not None:
            boost.append(current_entry.id)
        if central is not None:
            boost.append(central.id)
        rows, fed_warnings = search_federated(
            query,
            limit=limit,
            home=home,
            include_sensitive=include_sensitive,
            boost_brain_ids=boost,
        )
        warnings.extend(fed_warnings)
        results = []
        for row in rows:
            note_path = Path(row["note_path"])
            if not note_path.is_file():
                warnings.append(f"stale pointer: {row['title']} in {row['brain_name']}")
                continue
            results.append(
                {
                    "title": row["title"],
                    "summary": row["summary"],
                    "scope": _marker(row["brain_name"], row["brain_type"]),
                    "brain_id": row["brain_id"],
                    "path": str(note_path),
                }
            )
        return results[:limit], warnings

    results = []
    if policy in ("project-only", "project+central"):
        for item in search_notes_safe(current_root, query, limit, warnings):
            results.append({**item, "scope": "[project]"})
    if policy in ("central-only", "project+central") and central is not None:
        if central_root != current:
            for item in search_notes_safe(central.root(), query, limit, warnings):
                results.append({**item, "scope": "[central]"})
        elif policy == "central-only":
            for item in search_notes_safe(current_root, query, limit, warnings):
                results.append({**item, "scope": "[central]"})
    elif policy == "central-only" and central is None:
        warnings.append("no central brain registered; nothing to search")
    # current-brain results first (proximity boost), stable order within each group
    return results[:limit], warnings


def search_notes_safe(root: Path, query: str, limit: int, warnings: list[str]) -> list[dict]:
    """Search one brain, degrading with a warning instead of failing the whole query."""
    from talamus.paths import TalamusPaths

    try:
        return search_notes(TalamusPaths(root), query, limit=limit)
    except Exception as exc:
        warnings.append(f"brain at {root} unavailable: {exc}")
        return []


def scoped_context_items(
    current_root: Path,
    question: str,
    policy: str,
    limit: int = 5,
    home: Path | None = None,
    exclude_roots: list[Path] | None = None,
) -> tuple[list[dict], list[str]]:
    """Cross-brain context for ask/recall: real note contents read from owning brains.

    ``exclude_roots`` drops hits owned by those brains (used when the caller has
    already retrieved local context and only wants the *extra* cross-brain notes).
    """
    from talamus.paths import TalamusPaths

    excluded = [str(r.resolve()) for r in (exclude_roots or [])]
    hits, warnings = scoped_search(current_root, question, policy, limit=limit, home=home)
    items: list[dict] = []
    for hit in hits:
        if "path" in hit and any(str(Path(hit["path"]).resolve()).startswith(p) for p in excluded):
            continue
        if "path" in hit:
            note_path = Path(hit["path"])
            try:
                content = note_path.read_text(encoding="utf-8")
            except OSError as exc:
                warnings.append(f"could not read {note_path}: {exc}")
                continue
            label = f"{hit['scope']} {note_path.as_posix()}"
        else:
            root = current_root if hit["scope"] == "[project]" else _central_root(home)
            if root is None:
                continue
            text = read_note_text(TalamusPaths(root), hit["title"])
            if text is None:
                continue
            content = text
            label = f"{hit['scope']} {hit['title']}"
        items.append({"route": "scoped", "path": label, "content": content})
    return items, warnings


def _central_root(home: Path | None) -> Path | None:
    central = central_brain(home)
    return central.root() if central is not None else None


def promote_note(source_root: Path, target_root: Path, title: str, source_name: str = "") -> bool:
    """Promote a note from one brain to another (F1.5): copy/merge preserving
    id, provenance and history; the origin is recorded as a ``promoted-from`` tag."""
    import dataclasses

    from talamus.linking import NoteRegistry
    from talamus.naming import note_slug
    from talamus.paths import TalamusPaths
    from talamus.store import (
        load_notes,
        rebuild_indexes,
        render_note_markdown,
        write_note_json,
    )

    source_paths = TalamusPaths(source_root)
    target_paths = TalamusPaths(target_root)
    note = next((n for n in load_notes(source_paths) if n.title.lower() == title.lower()), None)
    if note is None:
        return False
    origin = f"promoted-from:{source_name or source_root.name}"
    if origin not in note.tags:
        note = dataclasses.replace(note, tags=[*note.tags, origin])
    target_paths.ensure_directories()
    write_note_json(target_paths, note)  # merges with an existing target note, keeps id
    source_history = source_paths.history / f"{note_slug(note.note_id)}.jsonl"
    if source_history.is_file():
        target_history = target_paths.history / f"{note_slug(note.note_id)}.jsonl"
        target_history.parent.mkdir(parents=True, exist_ok=True)
        with target_history.open("a", encoding="utf-8") as handle:
            handle.write(source_history.read_text(encoding="utf-8"))
    merged = next(n for n in load_notes(target_paths) if n.note_id == note.note_id)
    registry = NoteRegistry.from_notes(load_notes(target_paths))
    render_note_markdown(target_paths, merged, registry)
    rebuild_indexes(target_paths)
    return True
