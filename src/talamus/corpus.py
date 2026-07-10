"""Deterministic benchmark corpora — no LLM calls, fully reproducible.

Two builders feed the measurement baseline and the scale benchmarks:

- ``build_docs_corpus`` derives real concept-notes mechanically from this
  repository's own documentation (one note per ``##`` section, plus a doc-level
  note). Real content, real provenance, zero LLM cost — the corpus the real
  eval-set (``examples/eval-cases-real.json``) is authored against.
- ``build_synthetic_corpus`` generates N seeded synthetic notes for latency
  benchmarks at 100/1.000/10.000+ notes.

Both write through the normal store (JSON truth + Markdown view + indexes), so
measurements exercise the real read path.
"""

from __future__ import annotations

import hashlib
import random
import re
from pathlib import Path

from talamus.linking import NoteRegistry
from talamus.models import CanonicalNote, Relation, SourceRef
from talamus.paths import TalamusPaths
from talamus.store import load_notes, rebuild_indexes, render_note_markdown, write_note_json

# Corpus FROZEN as a fixture (2026-06-12): the 120-case eval-set references the
# section titles of THESE versions of the documents. Never edit the files under
# tests/fixtures/docs-corpus/ — that immutability is what keeps the numbers
# comparable over time. The live docs evolve freely elsewhere.
DOC_FILES = [
    "tests/fixtures/docs-corpus/readme.md",
    "tests/fixtures/docs-corpus/index.md",
    "tests/fixtures/docs-corpus/quickstart.md",
    "tests/fixtures/docs-corpus/commands.md",
    "tests/fixtures/docs-corpus/configuration.md",
    "tests/fixtures/docs-corpus/evaluation.md",
    "tests/fixtures/docs-corpus/architecture.md",
    "tests/fixtures/docs-corpus/agent-tool-calling.md",
    "tests/fixtures/docs-corpus/roadmap.md",
    "tests/fixtures/docs-corpus/ui-design.md",
]

_MIN_SECTION_CHARS = 120
_TITLE_MAX = 80
# markdown syntax + status emoji that would pollute titles
_TITLE_JUNK = re.compile(r"[*`#✅🟡⏳⭐🎯]|\[|\]|\(http[^)]*\)")


def _clean_title(heading: str) -> str:
    title = _TITLE_JUNK.sub("", heading).strip(" -—·.")
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) > _TITLE_MAX:
        title = title[:_TITLE_MAX].rsplit(" ", 1)[0].strip(" -—·.")
    return title


def _first_line(text: str, limit: int = 200) -> str:
    for line in text.splitlines():
        cleaned = line.strip().lstrip(">-*| ").strip()
        if cleaned and not cleaned.startswith(("```", "|", "![")):
            return cleaned[:limit]
    return text.strip()[:limit]


def _split_sections(markdown: str) -> tuple[str, str, list[tuple[str, str]]]:
    """Return (doc_title, intro_text, [(heading, body), ...]) split on ## headings."""
    doc_title = ""
    intro: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    in_code = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        if not in_code and line.startswith("# ") and not doc_title:
            doc_title = _clean_title(line[2:])
            continue
        if not in_code and line.startswith("## "):
            sections.append((_clean_title(line[3:]), []))
            continue
        if sections:
            sections[-1][1].append(line)
        else:
            intro.append(line)
    return (
        doc_title,
        "\n".join(intro).strip(),
        [(heading, "\n".join(body).strip()) for heading, body in sections],
    )


def _note(
    title: str,
    body: str,
    rel_path: str,
    locator: str,
    relations: list[Relation],
    tags: list[str],
) -> CanonicalNote:
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=[],
        folder="",
        tags=tags,
        summary=_first_line(body),
        retrieval_text=body,
        body_sections={"content": body},
        proposed_links=[],
        relations=relations,
        sources=[
            SourceRef(
                raw_path=rel_path,
                normalized_path=f"{rel_path}#{locator}",
                locator=locator,
                source_hash=f"sha256:{digest[:16]}",
                supported_claims=[_first_line(body)],
            )
        ],
        confidence=0.9,
    )


def _compile_markdown_corpus(
    paths: TalamusPaths, repo_root: Path, rel_paths: list[str]
) -> list[str]:
    """Compile a list of Markdown files into a real, deterministic brain.

    One note per ``##`` section plus a doc-level note. Notes carry real provenance
    (file path + section locator) and part-of relations section -> document. Returns
    the created note titles (sorted). No LLM calls — fully reproducible.
    """
    paths.ensure_directories()
    titles: list[str] = []
    seen: set[str] = set()
    notes: list[CanonicalNote] = []
    for rel_path in rel_paths:
        file_path = repo_root / rel_path
        if not file_path.is_file():
            continue
        doc_title, intro, sections = _split_sections(
            file_path.read_text(encoding="utf-8", errors="replace")
        )
        if not doc_title:
            doc_title = _clean_title(file_path.stem.replace("-", " "))
        if doc_title.lower() in seen:
            doc_title = f"{doc_title} ({file_path.stem})"
        seen.add(doc_title.lower())
        if len(intro) >= _MIN_SECTION_CHARS:
            notes.append(_note(doc_title, intro, rel_path, "intro", [], ["doc"]))
            titles.append(doc_title)
        for heading, body in sections:
            if not heading or len(body) < _MIN_SECTION_CHARS:
                continue
            title = heading
            if title.lower() in seen:
                title = f"{heading} — {doc_title}"
            if title.lower() in seen:
                continue
            seen.add(title.lower())
            relations = [
                Relation(source=title, relation="part-of", target=doc_title, confidence=0.9)
            ]
            notes.append(_note(title, body, rel_path, f"section {heading}", relations, ["doc"]))
            titles.append(title)
    for note in notes:
        write_note_json(paths, note)
    registry = NoteRegistry.from_notes(load_notes(paths))
    for note in notes:
        render_note_markdown(paths, note, registry)
    rebuild_indexes(paths)
    return sorted(titles)


def build_docs_corpus(paths: TalamusPaths, repo_root: Path) -> list[str]:
    """Compile the repo's documentation into a real, deterministic brain."""
    return _compile_markdown_corpus(paths, repo_root, DOC_FILES)


def build_garden_corpus(paths: TalamusPaths, repo_root: Path) -> list[str]:
    """Compile the frozen, domain-diverse garden corpus into a real, deterministic
    brain (the P1.5 anti-overfit corpus). Globs ``tests/fixtures/garden-corpus/*.md``."""
    garden = sorted(
        str(path.relative_to(repo_root)).replace("\\", "/")
        for path in (repo_root / "tests" / "fixtures" / "garden-corpus").glob("*.md")
    )
    return _compile_markdown_corpus(paths, repo_root, garden)


# Shared topic vocabulary for the synthetic notes; bench `_synthetic_queries`
# draws from these same words so the latency queries actually hit.
_TOPICS = [
    "memory",
    "graph",
    "index",
    "retrieval",
    "ontology",
    "note",
    "source",
    "time",
    "agent",
    "domain",
    "context",
    "search",
]


def build_synthetic_corpus(paths: TalamusPaths, n: int, seed: int = 42, render: bool = True) -> int:
    """Write ``n`` seeded synthetic notes (shared topics + unique terms) and index them.

    ``render=False`` skips the Markdown view: the search path reads the JSON cache,
    so latency benchmarks at large N don't need to pay double file writes.
    """
    paths.ensure_directories()
    rng = random.Random(seed)
    notes: list[CanonicalNote] = []
    for i in range(n):
        title = f"Synthetic note {i:05d}"
        words = [f"concept{i:05d}", *rng.choices(_TOPICS, k=8)]
        words += [f"term{rng.randrange(max(n * 3, 10)):05d}" for _ in range(12)]
        body = " ".join(words)
        relations = []
        if i > 0:
            target = f"Synthetic note {rng.randrange(i):05d}"
            relations = [Relation(source=title, relation="related", target=target, confidence=0.8)]
        notes.append(_note(title, body, "synthetic", f"item {i}", relations, ["synthetic"]))
    for note in notes:
        write_note_json(paths, note)
    if render:
        registry = NoteRegistry.from_notes(load_notes(paths))
        for note in notes:
            render_note_markdown(paths, note, registry)
    rebuild_indexes(paths)
    return len(notes)
