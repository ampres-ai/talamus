# Traguardo 1 — Loop su Testo (primo cut) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provare end-to-end il loop "ingest di un file di testo → estrazione LLM in schede → recupero con risposta citata", per validare la Scommessa A (la qualità delle schede estratte) con il minimo codice.

**Architecture:** Si aggiunge al pacchetto `talamus` esistente un layer di adattatori (LLM), normalizzazione testo, estrazione ("il bibliotecario"), uno store e l'orchestrazione di ingest. Il layout su disco evolve: le **note** stanno in `notes/` (Markdown leggibile), mentre grezzo, normalizzato, cache e log stanno in `.talamus/`. Le funzioni esistenti (`models`, `graph`, `search`, `linking`, `storage/obsidian`) vengono riusate.

> **Semplificazione voluta del primo cut (da chiudere subito dopo):** le note vengono renderizzate in Markdown in `notes/` (per la lettura umana — è il cuore della Scommessa A) e l'oggetto canonico viene salvato come JSON in `.talamus/cache/notes/<id>.json`, da cui si costruiscono grafo e indice. Il "Markdown come unica verità, con parser Markdown→oggetto per le modifiche a mano" è il **primo incremento successivo** del Traguardo 1, non questo cut. La spina dorsale resta il bersaglio.

**Tech Stack:** Python 3.13 (solo libreria standard), `unittest`, `claude-cli` come provider LLM di default (modalità `-p`), JSON, Markdown.

---

## Operating Rules

- Si lavora sul branch `feat/traguardo-1-text-loop`.
- Si committa a ogni task completato (autorizzato dall'utente). Il commit/merge finale resta all'utente.
- TDD: prima il test che fallisce, poi il minimo per farlo passare.
- I test NON devono mai chiamare la rete: l'LLM è sempre un `FakeLLMProvider` nei test. Il provider reale (`claude-cli`) si prova solo nello smoke manuale (Task 9).
- Comando test standard: `$env:PYTHONPATH="src"; python -m unittest <modulo> -v`.

## File Structure

- Modify: `src/talamus/paths.py` — nuovo layout (`notes/` + `.talamus/`).
- Modify: `src/talamus/cli.py` — `init` nuovo layout, nuovi comandi `ingest`/`ask`.
- Create: `src/talamus/adapters/__init__.py` — package adattatori.
- Create: `src/talamus/adapters/llm.py` — interfaccia `LLMProvider` + `ClaudeCliProvider`.
- Create: `src/talamus/normalize.py` — normalizzazione testo/Markdown.
- Create: `src/talamus/extract.py` — estrazione schede via LLM ("il bibliotecario").
- Create: `src/talamus/store.py` — scrittura note + cache JSON + ricostruzione indici.
- Create: `src/talamus/ingest.py` — orchestrazione dell'ingest.
- Modify: `src/talamus/ask.py` — risposta citata via LLM.
- Reuse (no change): `src/talamus/models.py`, `graph.py`, `search.py`, `linking.py`, `storage/obsidian.py`.
- Test: `tests/test_talamus_paths_config.py` (modify), `tests/test_talamus_llm_adapter.py`, `tests/test_talamus_normalize.py`, `tests/test_talamus_extract.py`, `tests/test_talamus_store.py`, `tests/test_talamus_ingest.py`, `tests/test_talamus_ask.py` (modify), `tests/test_talamus_cli.py` (modify).
- Test helper: `tests/support.py` — `FakeLLMProvider`.

---

### Task 1: Branch e checkpoint documenti

**Files:** none (solo git)

- [ ] **Step 1: Creare il branch di lavoro**

Run:

```powershell
git checkout -b feat/traguardo-1-text-loop
```

Expected: si è sul nuovo branch.

- [ ] **Step 2: Committare i documenti approvati ancora non tracciati**

Run:

```powershell
git add docs/superpowers/specs/2026-05-29-talamus-architecture-foundations.md docs/superpowers/plans/2026-05-29-traguardo-1-text-loop.md
git commit -m "docs: add architecture foundations and traguardo 1 plan"
```

Expected: commit riuscito.

---

### Task 2: Nuovo layout di progetto (`notes/` + `.talamus/`)

**Files:**
- Modify: `src/talamus/paths.py`
- Test: `tests/test_talamus_paths_config.py`

- [ ] **Step 1: Scrivere i test che falliscono per il nuovo layout**

Aggiungere a `tests/test_talamus_paths_config.py` (oltre ai test esistenti) i metodi:

```python
    def test_layout_separates_human_notes_from_managed_area(self) -> None:
        paths = TalamusPaths(Path("C:/brain"))

        self.assertEqual(paths.notes, Path("C:/brain") / "notes")
        self.assertEqual(paths.talamus_dir, Path("C:/brain") / ".talamus")
        self.assertEqual(paths.raw, Path("C:/brain") / ".talamus" / "raw")
        self.assertEqual(paths.normalized, Path("C:/brain") / ".talamus" / "normalized")
        self.assertEqual(paths.cache, Path("C:/brain") / ".talamus" / "cache")
        self.assertEqual(paths.notes_cache, Path("C:/brain") / ".talamus" / "cache" / "notes")
        self.assertEqual(paths.graph_file, Path("C:/brain") / ".talamus" / "cache" / "graph.json")
        self.assertEqual(paths.index_file, Path("C:/brain") / ".talamus" / "cache" / "bm25.json")

    def test_ensure_directories_creates_new_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            for directory in (paths.notes, paths.raw, paths.normalized, paths.notes_cache, paths.logs):
                self.assertTrue(directory.is_dir(), directory)
```

- [ ] **Step 2: Eseguire i test e verificarne il fallimento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_paths_config -v
```

Expected: FAIL (attributi `talamus_dir`, `notes_cache`, ecc. non esistono).

- [ ] **Step 3: Riscrivere `TalamusPaths` con il nuovo layout**

Sostituire il corpo di `src/talamus/paths.py` con:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TalamusPaths:
    project_root: Path

    @property
    def config_path(self) -> Path:
        return self.project_root / "talamus.json"

    @property
    def notes(self) -> Path:
        return self.project_root / "notes"

    @property
    def talamus_dir(self) -> Path:
        return self.project_root / ".talamus"

    @property
    def raw(self) -> Path:
        return self.talamus_dir / "raw"

    @property
    def normalized(self) -> Path:
        return self.talamus_dir / "normalized"

    @property
    def cache(self) -> Path:
        return self.talamus_dir / "cache"

    @property
    def notes_cache(self) -> Path:
        return self.cache / "notes"

    @property
    def graph_file(self) -> Path:
        return self.cache / "graph.json"

    @property
    def index_file(self) -> Path:
        return self.cache / "bm25.json"

    @property
    def logs(self) -> Path:
        return self.talamus_dir / "logs"

    def required_directories(self) -> list[Path]:
        return [self.notes, self.raw, self.normalized, self.cache, self.notes_cache, self.logs]

    def ensure_directories(self) -> list[Path]:
        created: list[Path] = []
        for directory in self.required_directories():
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created.append(directory)
        return created
```

- [ ] **Step 4: Eseguire i test e verificarne il superamento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_paths_config -v
```

Expected: PASS. (Nota: se test esistenti facevano riferimento a vecchie cartelle come `paths.index`, aggiornarli al nuovo layout.)

- [ ] **Step 5: Commit**

```powershell
git add src/talamus/paths.py tests/test_talamus_paths_config.py
git commit -m "feat: evolve project layout to notes/ plus managed .talamus/"
```

---

### Task 3: Adattatore LLM (interfaccia + claude-cli)

**Files:**
- Create: `src/talamus/adapters/__init__.py`
- Create: `src/talamus/adapters/llm.py`
- Create: `tests/support.py`
- Test: `tests/test_talamus_llm_adapter.py`

- [ ] **Step 1: Creare l'helper di test con il fake provider**

Create `tests/support.py`:

```python
from __future__ import annotations


class FakeLLMProvider:
    """LLM provider deterministico per i test: restituisce risposte preimpostate."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self._responses:
            return self._responses.pop(0)
        return ""
```

- [ ] **Step 2: Scrivere i test che falliscono per l'adattatore**

Create `tests/test_talamus_llm_adapter.py`:

```python
import unittest

from talamus.adapters.llm import ClaudeCliProvider


class LLMAdapterTests(unittest.TestCase):
    def test_claude_cli_builds_print_mode_command(self) -> None:
        captured = {}

        def fake_runner(args: list[str], prompt: str) -> str:
            captured["args"] = args
            captured["prompt"] = prompt
            return "risposta"

        provider = ClaudeCliProvider(runner=fake_runner)

        result = provider.complete("ciao")

        self.assertEqual("risposta", result)
        self.assertEqual(["claude", "-p"], captured["args"])
        self.assertEqual("ciao", captured["prompt"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Eseguire i test e verificarne il fallimento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_llm_adapter -v
```

Expected: FAIL (modulo inesistente).

- [ ] **Step 4: Implementare l'adattatore**

Create `src/talamus/adapters/__init__.py`:

```python
"""Adattatori intercambiabili di Talamus (LLM, convertitori, ricerca, ...)."""
```

Create `src/talamus/adapters/llm.py`:

```python
from __future__ import annotations

import subprocess
from typing import Callable, Protocol


class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str:
        ...


def _default_runner(args: list[str], prompt: str) -> str:
    completed = subprocess.run(
        args,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"LLM command failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


class ClaudeCliProvider:
    """Usa l'abbonamento via `claude -p` (modalità non interattiva)."""

    def __init__(self, runner: Callable[[list[str], str], str] = _default_runner) -> None:
        self._runner = runner

    def complete(self, prompt: str) -> str:
        return self._runner(["claude", "-p"], prompt)
```

- [ ] **Step 5: Eseguire i test e verificarne il superamento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_llm_adapter -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/talamus/adapters tests/test_talamus_llm_adapter.py tests/support.py
git commit -m "feat: add swappable LLM provider with claude-cli adapter"
```

---

### Task 4: Normalizzazione testo/Markdown

**Files:**
- Create: `src/talamus/normalize.py`
- Test: `tests/test_talamus_normalize.py`

- [ ] **Step 1: Scrivere i test che falliscono**

Create `tests/test_talamus_normalize.py`:

```python
import unittest

from talamus.normalize import normalize_text


class NormalizeTests(unittest.TestCase):
    def test_splits_by_top_level_headings_and_records_provenance(self) -> None:
        text = "# Intro\nRAG collega il modello a fonti esterne.\n\n# Uso\nQuando i dati cambiano spesso."

        package = normalize_text("knowledge/raw/note.md", text)

        self.assertEqual("knowledge/raw/note.md", package.raw_path)
        self.assertTrue(package.source_hash.startswith("sha256:"))
        self.assertEqual(2, len(package.sections))
        self.assertEqual("Intro", package.sections[0].title)
        self.assertIn("RAG", package.sections[0].text)

    def test_text_without_headings_becomes_single_section(self) -> None:
        package = normalize_text("a.txt", "Solo un paragrafo.")

        self.assertEqual(1, len(package.sections))
        self.assertEqual("a.txt", package.sections[0].title)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Eseguire i test e verificarne il fallimento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_normalize -v
```

Expected: FAIL (modulo inesistente).

- [ ] **Step 3: Implementare la normalizzazione**

Create `src/talamus/normalize.py`:

```python
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class NormalizedSection:
    section_id: str
    title: str
    text: str


@dataclass(frozen=True)
class NormalizedPackage:
    raw_path: str
    source_hash: str
    sections: list[NormalizedSection]


def normalize_text(raw_path: str, text: str) -> NormalizedPackage:
    source_hash = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    fallback_title = PurePosixPath(raw_path).name
    sections: list[NormalizedSection] = []
    matches = list(re.finditer(r"^#\s+(.+)$", text, flags=re.MULTILINE))
    if not matches:
        sections.append(NormalizedSection("001", fallback_title, text.strip()))
        return NormalizedPackage(raw_path, source_hash, sections)
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append(NormalizedSection(f"{index + 1:03d}", match.group(1).strip(), body))
    return NormalizedPackage(raw_path, source_hash, sections)
```

- [ ] **Step 4: Eseguire i test e verificarne il superamento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_normalize -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/talamus/normalize.py tests/test_talamus_normalize.py
git commit -m "feat: add text/markdown normalization with provenance"
```

---

### Task 5: Estrazione delle schede ("il bibliotecario")

**Files:**
- Create: `src/talamus/extract.py`
- Test: `tests/test_talamus_extract.py`

- [ ] **Step 1: Scrivere i test che falliscono**

Create `tests/test_talamus_extract.py`:

```python
import json
import unittest

from talamus.extract import extract_notes
from talamus.normalize import normalize_text
from tests.support import FakeLLMProvider


class ExtractTests(unittest.TestCase):
    def _package(self):
        return normalize_text("knowledge/raw/rag.md", "# RAG\nRAG collega il modello a fonti esterne.")

    def test_extracts_canonical_note_with_provenance(self) -> None:
        llm_json = json.dumps([
            {
                "title": "Retrieval-Augmented Generation",
                "aliases": ["RAG"],
                "tags": ["retrieval"],
                "summary": "RAG collega il modello a fonti esterne.",
                "retrieval_text": "rag retrieval fonti esterne",
                "body_sections": {"core_idea": "Recupera contesto prima di generare."},
                "relations": [],
                "supported_claims": ["RAG collega il modello a fonti esterne."],
                "confidence": 0.9,
            }
        ])
        llm = FakeLLMProvider([llm_json])

        notes = extract_notes(self._package(), llm)

        self.assertEqual(1, len(notes))
        note = notes[0]
        self.assertEqual("Retrieval-Augmented Generation", note.title)
        self.assertEqual(1, len(note.sources))
        self.assertEqual("knowledge/raw/rag.md", note.sources[0].raw_path)
        self.assertEqual([], note.validation_errors())

    def test_ignores_text_around_json_array(self) -> None:
        llm = FakeLLMProvider(['Ecco le note:\n[{"title":"X","supported_claims":["y"]}]\nfine'])

        notes = extract_notes(self._package(), llm)

        self.assertEqual("X", notes[0].title)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Eseguire i test e verificarne il fallimento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_extract -v
```

Expected: FAIL (modulo inesistente).

- [ ] **Step 3: Implementare l'estrazione**

Create `src/talamus/extract.py`:

```python
from __future__ import annotations

import json

from talamus.adapters.llm import LLMProvider
from talamus.models import CanonicalNote, Relation, SourceRef
from talamus.normalize import NormalizedPackage, NormalizedSection

_PROMPT = """Sei un estrattore di conoscenza. Leggi il testo e produci un ARRAY JSON di note.
Ogni nota e un concetto riutilizzabile con i campi:
title, aliases (lista), tags (lista), summary, retrieval_text,
body_sections (oggetto sezione->testo), relations (lista di {{source,relation,target,confidence}}),
supported_claims (lista di frasi sostenute dal testo), confidence (0..1).
Rispondi SOLO con l'array JSON, senza commenti.

TESTO:
{text}
"""


def _extract_json_array(raw: str) -> list[dict]:
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("nessun array JSON nella risposta del modello")
    return json.loads(raw[start : end + 1])


def _section_source(section: NormalizedSection, package: NormalizedPackage, claims: list[str]) -> SourceRef:
    return SourceRef(
        raw_path=package.raw_path,
        normalized_path=f"{package.raw_path}#section-{section.section_id}",
        locator=f"section {section.section_id}: {section.title}",
        source_hash=package.source_hash,
        supported_claims=claims,
    )


def extract_notes(package: NormalizedPackage, llm: LLMProvider) -> list[CanonicalNote]:
    text = "\n\n".join(f"# {s.title}\n{s.text}" for s in package.sections)
    raw = llm.complete(_PROMPT.format(text=text))
    candidates = _extract_json_array(raw)
    primary_section = package.sections[0]
    notes: list[CanonicalNote] = []
    for candidate in candidates:
        title = str(candidate.get("title", "")).strip()
        if not title:
            continue
        relations = [
            Relation(
                source=str(r.get("source", title)),
                relation=str(r.get("relation", "related")),
                target=str(r.get("target", "")),
                confidence=float(r.get("confidence", 0.5)),
            )
            for r in candidate.get("relations", [])
            if str(r.get("target", "")).strip()
        ]
        claims = [str(c) for c in candidate.get("supported_claims", [])]
        note = CanonicalNote(
            note_id=title.lower().replace(" ", "-"),
            title=title,
            aliases=[str(a) for a in candidate.get("aliases", [])],
            folder=str(candidate.get("folder", "")),
            tags=[str(t) for t in candidate.get("tags", [])],
            summary=str(candidate.get("summary", f"{title}.")),
            retrieval_text=str(candidate.get("retrieval_text", title)),
            body_sections={str(k): str(v) for k, v in candidate.get("body_sections", {}).items()}
            or {"summary": str(candidate.get("summary", f"{title}."))},
            proposed_links=[],
            relations=relations,
            sources=[_section_source(primary_section, package, claims)],
            confidence=float(candidate.get("confidence", 0.8)),
        )
        notes.append(note)
    return notes
```

- [ ] **Step 4: Eseguire i test e verificarne il superamento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_extract -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/talamus/extract.py tests/test_talamus_extract.py
git commit -m "feat: add LLM note extraction with provenance"
```

---

### Task 6: Store — scrittura note, cache JSON, ricostruzione indici

**Files:**
- Create: `src/talamus/store.py`
- Test: `tests/test_talamus_store.py`

- [ ] **Step 1: Scrivere i test che falliscono**

Create `tests/test_talamus_store.py`:

```python
import tempfile
import unittest
from pathlib import Path

from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.store import load_notes, rebuild_indexes, write_note


def _note(title: str) -> CanonicalNote:
    source = SourceRef("raw/a.md", "norm/a#1", "section 1", "sha256:x", [f"{title} claim"])
    return CanonicalNote.minimal(title, sources=[source])


class StoreTests(unittest.TestCase):
    def test_write_note_creates_markdown_and_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()

            write_note(paths, _note("Retrieval-Augmented Generation"))

            self.assertTrue((paths.notes / "Retrieval-Augmented-Generation.md").is_file())
            self.assertTrue((paths.notes_cache / "retrieval-augmented-generation.json").is_file())

    def test_load_notes_round_trips_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Vector Store"))

            loaded = load_notes(paths)

            self.assertEqual(1, len(loaded))
            self.assertEqual("Vector Store", loaded[0].title)

    def test_rebuild_indexes_makes_graph_and_bm25_queryable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            write_note(paths, _note("Retrieval-Augmented Generation"))

            rebuild_indexes(paths)

            self.assertTrue(paths.graph_file.is_file())
            self.assertTrue(paths.index_file.is_file())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Eseguire i test e verificarne il fallimento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_store -v
```

Expected: FAIL (modulo inesistente).

- [ ] **Step 3: Implementare lo store**

Create `src/talamus/store.py`:

```python
from __future__ import annotations

import json

from talamus.graph import build_graph, save_graph
from talamus.linking import NoteRegistry
from talamus.models import CanonicalNote, ProposedLink, Relation, SourceRef
from talamus.paths import TalamusPaths
from talamus.search import BM25Index
from talamus.storage.obsidian import render_obsidian_note


def _note_from_dict(data: dict) -> CanonicalNote:
    return CanonicalNote(
        note_id=data["note_id"],
        title=data["title"],
        aliases=list(data.get("aliases", [])),
        folder=data.get("folder", ""),
        tags=list(data.get("tags", [])),
        summary=data.get("summary", ""),
        retrieval_text=data.get("retrieval_text", ""),
        body_sections=dict(data.get("body_sections", {})),
        proposed_links=[ProposedLink(**p) for p in data.get("proposed_links", [])],
        relations=[Relation(**r) for r in data.get("relations", [])],
        sources=[SourceRef(**s) for s in data.get("sources", [])],
        confidence=float(data.get("confidence", 0.8)),
    )


def load_notes(paths: TalamusPaths) -> list[CanonicalNote]:
    notes: list[CanonicalNote] = []
    for path in sorted(paths.notes_cache.glob("*.json")):
        notes.append(_note_from_dict(json.loads(path.read_text(encoding="utf-8"))))
    return notes


def write_note(paths: TalamusPaths, note: CanonicalNote) -> None:
    paths.notes_cache.mkdir(parents=True, exist_ok=True)
    (paths.notes_cache / f"{note.note_id}.json").write_text(
        json.dumps(note.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    registry = NoteRegistry.from_notes(load_notes(paths) + [note])
    markdown = render_obsidian_note(note, registry)
    paths.notes.mkdir(parents=True, exist_ok=True)
    filename = note.title.replace(" ", "-") + ".md"
    (paths.notes / filename).write_text(markdown, encoding="utf-8")


def rebuild_indexes(paths: TalamusPaths) -> None:
    notes = load_notes(paths)
    paths.cache.mkdir(parents=True, exist_ok=True)
    save_graph(paths.graph_file, build_graph(notes))
    index = BM25Index()
    for note in notes:
        haystack = " ".join([note.title, " ".join(note.aliases), " ".join(note.tags), note.retrieval_text, note.summary])
        index.add(note.title.replace(" ", "-"), haystack)
    index.save(paths.index_file)
```

- [ ] **Step 4: Eseguire i test e verificarne il superamento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_store -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/talamus/store.py tests/test_talamus_store.py
git commit -m "feat: add note store with markdown render and rebuildable cache"
```

---

### Task 7: Orchestrazione dell'ingest

**Files:**
- Create: `src/talamus/ingest.py`
- Test: `tests/test_talamus_ingest.py`

- [ ] **Step 1: Scrivere il test end-to-end che fallisce**

Create `tests/test_talamus_ingest.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from talamus.ingest import ingest_file
from talamus.paths import TalamusPaths
from talamus.store import load_notes
from tests.support import FakeLLMProvider


class IngestTests(unittest.TestCase):
    def test_ingest_file_creates_note_raw_and_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            paths.ensure_directories()
            source = root / "rag.md"
            source.write_text("# RAG\nRAG collega il modello a fonti esterne.", encoding="utf-8")
            llm = FakeLLMProvider([json.dumps([
                {"title": "Retrieval-Augmented Generation", "aliases": ["RAG"],
                 "retrieval_text": "rag fonti esterne", "summary": "RAG collega a fonti esterne.",
                 "supported_claims": ["RAG collega a fonti esterne."], "confidence": 0.9}
            ])])

            result = ingest_file(paths, source, llm)

            self.assertEqual(1, result["notes_written"])
            self.assertEqual(1, len(load_notes(paths)))
            self.assertTrue(any(paths.raw.glob("*.md")))
            self.assertTrue(paths.graph_file.is_file())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Eseguire il test e verificarne il fallimento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_ingest -v
```

Expected: FAIL (modulo inesistente).

- [ ] **Step 3: Implementare l'orchestrazione**

Create `src/talamus/ingest.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

from talamus.adapters.llm import LLMProvider
from talamus.extract import extract_notes
from talamus.normalize import normalize_text
from talamus.paths import TalamusPaths
from talamus.store import rebuild_indexes, write_note


def ingest_file(paths: TalamusPaths, file_path: Path, llm: LLMProvider) -> dict:
    paths.ensure_directories()
    text = file_path.read_text(encoding="utf-8")

    raw_copy = paths.raw / file_path.name
    shutil.copyfile(file_path, raw_copy)

    package = normalize_text(raw_copy.as_posix(), text)
    notes = extract_notes(package, llm)
    for note in notes:
        write_note(paths, note)
    rebuild_indexes(paths)
    return {"notes_written": len(notes), "source": file_path.name}
```

- [ ] **Step 4: Eseguire il test e verificarne il superamento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_ingest -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/talamus/ingest.py tests/test_talamus_ingest.py
git commit -m "feat: add ingest orchestration for text sources"
```

---

### Task 8: Recupero con risposta citata

**Files:**
- Modify: `src/talamus/ask.py`
- Test: `tests/test_talamus_ask.py`

- [ ] **Step 1: Scrivere i test che falliscono per la risposta citata**

Aggiungere a `tests/test_talamus_ask.py`:

```python
    def test_answer_question_uses_context_and_llm(self) -> None:
        import tempfile
        from pathlib import Path

        from talamus.ask import answer_question
        from talamus.ingest import ingest_file
        from talamus.paths import TalamusPaths
        from tests.support import FakeLLMProvider
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            paths.ensure_directories()
            source = root / "rag.md"
            source.write_text("# RAG\nRAG collega il modello a fonti esterne.", encoding="utf-8")
            ingest_file(paths, source, FakeLLMProvider([json.dumps([
                {"title": "Retrieval-Augmented Generation", "aliases": ["RAG"],
                 "retrieval_text": "rag fonti esterne documenti", "summary": "RAG collega a fonti esterne.",
                 "supported_claims": ["x"], "confidence": 0.9}
            ])]))
            answering = FakeLLMProvider(["RAG collega il modello a fonti esterne [1]."])

            answer = answer_question(paths, "Come collego il modello a fonti esterne?", answering)

            self.assertIn("RAG", answer)
            self.assertIn("Retrieval-Augmented Generation", answering.prompts[0])

    def test_answer_question_without_context_is_explicit(self) -> None:
        import tempfile
        from pathlib import Path

        from talamus.ask import answer_question
        from talamus.paths import TalamusPaths
        from tests.support import FakeLLMProvider

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            from talamus.store import rebuild_indexes
            rebuild_indexes(paths)

            answer = answer_question(paths, "qualcosa", FakeLLMProvider(["non dovrebbe servire"]))

            self.assertIn("nessun contesto", answer.lower())
```

- [ ] **Step 2: Eseguire i test e verificarne il fallimento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_ask -v
```

Expected: FAIL (`answer_question` non esiste).

- [ ] **Step 3: Aggiungere `answer_question` ad `ask.py`**

Aggiungere in fondo a `src/talamus/ask.py` (mantenendo `build_context_bundle` esistente, che legge da `paths.notes`):

```python
from talamus.adapters.llm import LLMProvider
from talamus.graph import load_graph
from talamus.search import BM25Index

_ANSWER_PROMPT = """Rispondi alla domanda usando SOLO il contesto qui sotto.
Cita le schede tra parentesi quadre con il loro numero, es. [1].
Se il contesto non basta, dillo esplicitamente.

DOMANDA: {question}

CONTESTO:
{context}
"""


def answer_question(paths, question: str, llm: LLMProvider) -> str:
    graph = load_graph(paths.graph_file) if paths.graph_file.is_file() else {"nodes": {}, "edges": []}
    search = BM25Index.load(paths.index_file) if paths.index_file.is_file() else BM25Index()
    bundle = build_context_bundle(paths, graph, search, question)
    if not bundle.items:
        return "Nessun contesto trovato nel brain per questa domanda."
    context = "\n\n".join(
        f"[{i}] {item['path']}\n{item['content']}" for i, item in enumerate(bundle.items, start=1)
    )
    return llm.complete(_ANSWER_PROMPT.format(question=question, context=context))
```

> Nota: `build_context_bundle` legge i file in `paths.notes`. Verificare che usi `paths.notes`
> (nuovo layout) e i percorsi `.md` con titolo separato da trattini; se necessario adeguarlo.

- [ ] **Step 4: Eseguire i test e verificarne il superamento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_ask -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/talamus/ask.py tests/test_talamus_ask.py
git commit -m "feat: add cited-answer retrieval over the brain"
```

---

### Task 9: Cablaggio CLI (`init`, `ingest`, `ask`)

**Files:**
- Modify: `src/talamus/cli.py`
- Test: `tests/test_talamus_cli.py`

- [ ] **Step 1: Scrivere i test che falliscono**

Sostituire/aggiornare `tests/test_talamus_cli.py` con test sul nuovo layout e i nuovi comandi (con provider iniettato):

```python
import json
import tempfile
import unittest
from pathlib import Path

from talamus.cli import main
from tests.support import FakeLLMProvider


class TalamusCliTests(unittest.TestCase):
    def test_init_creates_new_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(0, main(["init", "--root", tmp]))
            self.assertTrue((Path(tmp) / "talamus.json").is_file())
            self.assertTrue((Path(tmp) / "notes").is_dir())
            self.assertTrue((Path(tmp) / ".talamus" / "cache").is_dir())

    def test_ingest_then_ask_with_injected_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(0, main(["init", "--root", tmp]))
            source = Path(tmp) / "rag.md"
            source.write_text("# RAG\nRAG collega il modello a fonti esterne.", encoding="utf-8")
            extract_llm = FakeLLMProvider([json.dumps([
                {"title": "Retrieval-Augmented Generation", "aliases": ["RAG"],
                 "retrieval_text": "rag fonti esterne", "summary": "RAG collega a fonti.",
                 "supported_claims": ["x"], "confidence": 0.9}
            ])])
            self.assertEqual(0, main(["ingest", str(source), "--root", tmp], llm=extract_llm))

            answer_llm = FakeLLMProvider(["RAG [1]."])
            self.assertEqual(0, main(["ask", "Come collego fonti esterne?", "--root", tmp], llm=answer_llm))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Eseguire i test e verificarne il fallimento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_cli -v
```

Expected: FAIL (`main` non accetta `llm`; comandi mancanti).

- [ ] **Step 3: Aggiornare la CLI**

Aggiornare `src/talamus/cli.py`:
- `main(argv=None, llm=None)`: se `llm` è `None`, usa `ClaudeCliProvider()`.
- `init`: crea il nuovo layout (`TalamusPaths.ensure_directories()`) e scrive `talamus.json` (config di default) se assente.
- aggiungere `ingest <file> --root`: chiama `ingest_file(paths, Path(file), llm)` e stampa il riepilogo.
- aggiungere/aggiornare `ask <question> --root`: chiama `answer_question(paths, question, llm)` e stampa la risposta.
- mantenere `status`/`doctor`.

Snippet chiave (import e dispatch):

```python
from pathlib import Path

from talamus.adapters.llm import ClaudeCliProvider
from talamus.ask import answer_question
from talamus.ingest import ingest_file
from talamus.paths import TalamusPaths


def _cmd_ingest(root: Path, file: str, llm) -> int:
    paths = TalamusPaths(root)
    result = ingest_file(paths, Path(file), llm)
    print(f"ingerite {result['notes_written']} schede da {result['source']}")
    return 0


def _cmd_ask(root: Path, question: str, llm) -> int:
    print(answer_question(TalamusPaths(root), question, llm))
    return 0


def main(argv: list[str] | None = None, llm=None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    provider = llm if llm is not None else ClaudeCliProvider()
    if args.command == "init":
        return _cmd_init(root)
    if args.command == "ingest":
        return _cmd_ingest(root, args.file, provider)
    if args.command == "ask":
        return _cmd_ask(root, args.question, provider)
    if args.command == "status":
        return _cmd_status(root)
    if args.command == "doctor":
        return _cmd_doctor(root)
    raise ValueError(f"comando sconosciuto {args.command}")
```

Aggiornare `build_parser()` per i sottocomandi `ingest` (arg `file`, `--root`) e `ask` (arg `question`, `--root`), e `_cmd_init` per usare il nuovo `TalamusPaths`/`talamus.json`.

- [ ] **Step 4: Eseguire i test e verificarne il superamento**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest tests.test_talamus_cli -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/talamus/cli.py tests/test_talamus_cli.py
git commit -m "feat: wire init/ingest/ask CLI for the text loop"
```

---

### Task 10: Verifica completa + smoke reale (Scommessa A)

**Files:** none (salvo difetti emersi)

- [ ] **Step 1: Eseguire l'intera suite**

Run:

```powershell
$env:PYTHONPATH="src"; python -m unittest discover -s tests -v
```

Expected: PASS (tutti i test, nuovi e preesistenti adeguati al nuovo layout).

- [ ] **Step 2: Smoke reale con claude-cli (la Scommessa A)**

Run:

```powershell
$tmp = Join-Path $env:TEMP "talamus-t1-smoke"
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
$env:PYTHONPATH="src"
python -m talamus.cli init --root $tmp
# usare un appunto/markdown reale e abbastanza ricco al posto di sample.md
python -m talamus.cli ingest "C:\percorso\a\un\appunto.md" --root $tmp
python -m talamus.cli ask "una domanda reale sul contenuto" --root $tmp
```

Then: **aprire i file in `$tmp/notes/` e giudicare a mano la qualità delle schede.**

Criterio Scommessa A: *"tra un mese troverei utili queste schede?"* Annotare l'esito.

- [ ] **Step 3: Registrare l'esito dello smoke**

Annotare in un breve commento (nel commit o in una nota) se la qualità dell'estrazione convince. Se NON convince, fermarsi: il problema è il prompt/estrazione, da iterare prima di proseguire con sessioni/hook/MCP/ontologia.

- [ ] **Step 4: Commit di eventuali correzioni**

Se la verifica ha richiesto modifiche:

```powershell
git add <file modificati>
git commit -m "fix: corrections from traguardo 1 verification"
```

---

## Self-Review Checklist

Copertura dello scope (primo cut):
- Nuovo layout `notes/` + `.talamus/`: Task 2.
- Adattatore LLM (claude-cli, sostituibile): Task 3.
- Normalizzazione testo: Task 4.
- Estrazione schede con provenienza ("bibliotecario"): Task 5.
- Store + cache ricostruibile (grafo/BM25): Task 6.
- Orchestrazione ingest: Task 7.
- Recupero con risposta citata: Task 8.
- CLI `init`/`ingest`/`ask`: Task 9.
- Verifica + Scommessa A: Task 10.

Fuori scope (espliciti, prossimi incrementi del T1):
- Parser Markdown→oggetto (Markdown come unica verità per le modifiche a mano).
- Sessioni-agente + hook di cattura + strumento MCP `deposita`.
- Fusione/dedup nelle schede esistenti (qui si creano/aggiornano per `note_id`).
- Ontologia oltre i concetti base derivati dalle relazioni/tag.
- PDF/OCR, git automatico ai checkpoint, coda di revisione.

Coerenza dei tipi:
- `LLMProvider.complete(prompt) -> str` usato da `extract` e `ask`.
- `normalize_text(raw_path, text) -> NormalizedPackage` consumato da `extract` e `ingest`.
- `write_note`/`load_notes`/`rebuild_indexes(paths)` usati da `ingest` e `ask`.
- `CanonicalNote`/`SourceRef`/`Relation` riusati dal modello esistente senza modifiche.
