"""Markdown/Obsidian vault importer (P9 minimal slice, v1 launch plan D3).

Imports a folder of .md notes 1:1 — titles, tags, aliases and [[wikilinks]]
preserved — with NO LLM call: migration must be instant, free and light.
The switching wall (ROADMAP P9) falls without burning the user's subscription.
"""

import tempfile
import unittest
from pathlib import Path

from talamus.paths import TalamusPaths
from talamus.store import load_notes
from talamus.vault_import import import_vault


def _vault(tmp: str) -> Path:
    vault = Path(tmp) / "vault"
    (vault / "Concepts").mkdir(parents=True)
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "workspace.md").write_text("ignore me", encoding="utf-8")
    (vault / "RAG.md").write_text(
        "---\ntitle: Retrieval-Augmented Generation\ntags: [ai, retrieval]\n"
        "aliases:\n  - RAG\n---\n\n"
        "RAG connects the model to external sources.\n\n"
        "It relies on a [[Vector Store]] for retrieval.\n",
        encoding="utf-8",
    )
    (vault / "Concepts" / "Vector Store.md").write_text(
        "A vector store holds embeddings for retrieval.\n", encoding="utf-8"
    )
    return vault


class VaultImportTests(unittest.TestCase):
    def test_imports_notes_one_to_one_without_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp) / "brain")
            paths.ensure_directories()
            report = import_vault(paths, _vault(tmp))

            self.assertEqual(report["notes_written"], 2)
            notes = {n.title: n for n in load_notes(paths)}
            self.assertIn("Retrieval-Augmented Generation", notes)
            self.assertIn("Vector Store", notes)

    def test_frontmatter_title_tags_aliases_are_mapped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp) / "brain")
            paths.ensure_directories()
            import_vault(paths, _vault(tmp))

            note = {n.title: n for n in load_notes(paths)}["Retrieval-Augmented Generation"]
            self.assertIn("ai", note.tags)
            self.assertIn("retrieval", note.tags)
            self.assertIn("RAG", note.aliases)
            self.assertIn("external sources", note.summary)

    def test_wikilinks_survive_in_the_body_and_become_graph_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp) / "brain")
            paths.ensure_directories()
            import_vault(paths, _vault(tmp))

            notes = {n.title: n for n in load_notes(paths)}
            rag = notes["Retrieval-Augmented Generation"]
            self.assertIn("[[Vector Store]]", " ".join(rag.body_sections.values()))
            self.assertTrue(
                any(r.target == "Vector Store" for r in rag.relations),
                "wikilink should become a typed relation for the graph",
            )
            rendered = (paths.notes / "Retrieval-Augmented-Generation.md").read_text("utf-8")
            self.assertIn("[[Vector Store", rendered)

    def test_filename_becomes_the_title_without_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp) / "brain")
            paths.ensure_directories()
            import_vault(paths, _vault(tmp))

            titles = {n.title for n in load_notes(paths)}
            self.assertIn("Vector Store", titles)  # no frontmatter in that file

    def test_second_run_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp) / "brain")
            paths.ensure_directories()
            vault = _vault(tmp)
            first = import_vault(paths, vault)
            second = import_vault(paths, vault)

            self.assertEqual(first["notes_written"], 2)
            self.assertEqual(second["notes_written"], 0)
            self.assertEqual(second["skipped"], 2)
            self.assertEqual(len(load_notes(paths)), 2)

    def test_duplicate_titles_are_reported_not_silently_merged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp) / "brain")
            paths.ensure_directories()
            vault = _vault(tmp)
            (vault / "Concepts" / "RAG.md").write_text(
                "---\ntitle: Retrieval-Augmented Generation\n---\nAnother take.\n",
                encoding="utf-8",
            )
            report = import_vault(paths, vault)

            self.assertEqual(report["notes_written"], 2)
            self.assertEqual(len(report["duplicates"]), 1)

    def test_hostile_frontmatter_never_crashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp) / "brain")
            paths.ensure_directories()
            vault = Path(tmp) / "vault"
            vault.mkdir()
            (vault / "broken.md").write_text(
                "---\ntitle: [unclosed\ntags: {not: yaml\n---\nBody survives.\n",
                encoding="utf-8",
            )
            (vault / "empty.md").write_text("", encoding="utf-8")
            report = import_vault(paths, vault)

            # broken frontmatter degrades to filename title; empty files are skipped
            self.assertEqual(report["notes_written"], 1)
            self.assertEqual(load_notes(paths)[0].title, "broken")

    def test_missing_vault_raises_source_not_found(self) -> None:
        from talamus.errors import SourceNotFound

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp) / "brain")
            paths.ensure_directories()
            with self.assertRaises(SourceNotFound):
                import_vault(paths, Path(tmp) / "nope")


class VaultImportCliTests(unittest.TestCase):
    def test_cli_import_vault_end_to_end(self) -> None:
        import io
        from contextlib import redirect_stdout

        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            brain = Path(tmp) / "brain"
            brain.mkdir()
            vault = _vault(tmp)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["import-vault", str(vault), "--root", str(brain)])
            self.assertEqual(0, code)
            self.assertIn("imported 2 notes", out.getvalue())
            self.assertEqual(2, len(load_notes(TalamusPaths(brain))))

    def test_service_reports_missing_vault_cleanly(self) -> None:
        from talamus.services.importer import import_markdown_vault

        with tempfile.TemporaryDirectory() as tmp:
            result = import_markdown_vault(Path(tmp), Path(tmp) / "nope")
        self.assertFalse(result.success)
        self.assertEqual("vault_import_failed", result.code)


if __name__ == "__main__":
    unittest.main()
