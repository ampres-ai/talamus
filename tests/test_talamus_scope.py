import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.registry import register_brain
from talamus.scope import (
    default_scope,
    promote_note,
    resolve_brain,
    resolve_init_root,
    scoped_search,
)
from talamus.store import load_notes, rebuild_indexes, write_note


def _note(title: str, retrieval: str) -> CanonicalNote:
    src = SourceRef("raw/a.md", "norm/a#1", "s", "sha256:x", ["c"])
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=[],
        folder="",
        tags=[],
        summary=f"{title}.",
        retrieval_text=retrieval,
        body_sections={"d": retrieval},
        proposed_links=[],
        relations=[],
        sources=[src],
        confidence=0.9,
    )


def _brain(root: Path, notes: list[tuple[str, str]]) -> TalamusPaths:
    paths = TalamusPaths(root)
    paths.ensure_directories()
    (root / "talamus.json").write_text("{}", encoding="utf-8")
    for title, retrieval in notes:
        write_note(paths, _note(title, retrieval))
    rebuild_indexes(paths)
    return paths


class ResolveBrainTests(unittest.TestCase):
    def test_explicit_root_wins(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as root:
            resolved = resolve_brain(root, "ignored", True, home=Path(home))
            self.assertEqual(resolved.root, Path(root).resolve())
            self.assertEqual(resolved.source, "--root")

    def test_named_brain_resolves_through_registry(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as elsewhere:
            register_brain(Path(elsewhere), name="work", home=Path(home))
            resolved = resolve_brain(None, "work", False, home=Path(home))
            self.assertEqual(resolved.root, Path(elsewhere).resolve())
            self.assertEqual(resolved.scope, "named")

    def test_named_brain_falls_back_to_home_dir(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            resolved = resolve_brain(None, "ricerca", False, home=Path(home))
            self.assertEqual(resolved.root, (Path(home) / "ricerca").resolve())

    def test_project_ancestor_beats_selected_global(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as project,
            tempfile.TemporaryDirectory() as other,
        ):
            (Path(project) / "talamus.json").write_text("{}", encoding="utf-8")
            register_brain(Path(other), name="sel", home=Path(home))
            from talamus.registry import select_brain

            select_brain("sel", home=Path(home))
            nested = Path(project) / "sub" / "dir"
            nested.mkdir(parents=True)
            resolved = resolve_brain(None, None, False, cwd=nested, home=Path(home))
            self.assertEqual(resolved.root, Path(project).resolve())
            self.assertEqual(resolved.source, "project-ancestor")

    def test_selected_global_beats_default(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as other,
            tempfile.TemporaryDirectory() as cwd,
        ):
            register_brain(Path(other), name="sel", home=Path(home))
            from talamus.registry import select_brain

            select_brain("sel", home=Path(home))
            resolved = resolve_brain(None, None, False, cwd=Path(cwd), home=Path(home))
            self.assertEqual(resolved.root, Path(other).resolve())
            self.assertEqual(resolved.source, "selected-global")

    def test_default_global_is_last_resort(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd:
            resolved = resolve_brain(None, None, False, cwd=Path(cwd), home=Path(home))
            self.assertEqual(resolved.root, (Path(home) / "default").resolve())
            self.assertEqual(resolved.source, "default-global")


class ResolveInitRootTests(unittest.TestCase):
    def test_init_defaults_to_current_directory(self) -> None:
        """THE bug fix: bare `talamus init` must target the cwd, never the global."""
        with tempfile.TemporaryDirectory() as cwd:
            resolved = resolve_init_root(None, None, False, cwd=Path(cwd))
            self.assertEqual(resolved.root, Path(cwd).resolve())
            self.assertEqual(resolved.source, "current-directory")

    def test_init_global_targets_home_default(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(os.environ, {"TALAMUS_HOME": home}):
                resolved = resolve_init_root(None, None, True)
                self.assertEqual(resolved.root, (Path(home) / "default").resolve())
                self.assertEqual(resolved.scope, "global")


class ScopedSearchTests(unittest.TestCase):
    def test_project_plus_central_merges_with_markers(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as project,
            tempfile.TemporaryDirectory() as hub,
        ):
            _brain(Path(project), [("Nota Progetto", "argomento condiviso progetto")])
            _brain(Path(hub), [("Nota Centrale", "argomento condiviso centrale")])
            register_brain(Path(hub), name="hub", brain_type="central", home=Path(home))
            results, warnings = scoped_search(
                Path(project), "argomento condiviso", "project+central", limit=5, home=Path(home)
            )
            scopes = {r["scope"] for r in results}
            self.assertIn("[project]", scopes)
            self.assertIn("[central]", scopes)
            self.assertEqual(warnings, [])
            # proximity: project results come first
            self.assertEqual(results[0]["scope"], "[project]")

    def test_project_only_ignores_central(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as project,
            tempfile.TemporaryDirectory() as hub,
        ):
            _brain(Path(project), [("Nota Progetto", "argomento condiviso")])
            _brain(Path(hub), [("Nota Centrale", "argomento condiviso")])
            register_brain(Path(hub), name="hub", brain_type="central", home=Path(home))
            results, _ = scoped_search(
                Path(project), "argomento condiviso", "project-only", limit=5, home=Path(home)
            )
            self.assertEqual({r["scope"] for r in results}, {"[project]"})

    def test_central_only_without_central_warns(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as project:
            _brain(Path(project), [("Nota", "argomento")])
            results, warnings = scoped_search(
                Path(project), "argomento", "central-only", limit=5, home=Path(home)
            )
            self.assertEqual(results, [])
            self.assertTrue(warnings)

    def test_default_scope_is_all_from_central(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as hub:
            register_brain(Path(hub), name="hub", brain_type="central", home=Path(home))
            self.assertEqual(default_scope(Path(hub), home=Path(home)), "all")
            with tempfile.TemporaryDirectory() as project:
                self.assertEqual(default_scope(Path(project), home=Path(home)), "project+central")


class PromoteNoteTests(unittest.TestCase):
    def test_promote_preserves_id_provenance_and_origin(self) -> None:
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            _brain(Path(src), [("Concetto Durevole", "conoscenza che vale ovunque")])
            target = TalamusPaths(Path(dst))
            target.ensure_directories()
            (Path(dst) / "talamus.json").write_text("{}", encoding="utf-8")
            ok = promote_note(Path(src), Path(dst), "Concetto Durevole", source_name="lavoro")
            self.assertTrue(ok)
            promoted = load_notes(target)
            self.assertEqual(len(promoted), 1)
            note = promoted[0]
            self.assertEqual(note.note_id, "concetto-durevole")
            self.assertTrue(note.sources)  # provenance preserved
            self.assertIn("promoted-from:lavoro", note.tags)
            self.assertTrue((target.notes / "Concetto-Durevole.md").is_file())

    def test_promote_missing_note_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            _brain(Path(src), [("Altro", "altro")])
            self.assertFalse(promote_note(Path(src), Path(dst), "Inesistente"))


class WhereJsonTests(unittest.TestCase):
    def test_where_json_reports_scope_and_source(self) -> None:
        import io
        from contextlib import redirect_stdout

        from talamus.cli import main

        with tempfile.TemporaryDirectory() as root:
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["where", "--root", root, "--json"])
            self.assertEqual(code, 0)
            data = json.loads(out.getvalue())
            self.assertEqual(data["scope"], "explicit")
            self.assertEqual(data["source"], "--root")
            self.assertFalse(data["config_exists"])


if __name__ == "__main__":
    unittest.main()
