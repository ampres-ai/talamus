import tempfile
import unittest
from pathlib import Path

from talamus.federation import build_federated_index, federation_status, search_federated
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.registry import register_brain, set_brain_flag
from talamus.store import rebuild_indexes, write_note


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


def _brain(root: Path, notes: list[tuple[str, str]]) -> None:
    paths = TalamusPaths(root)
    paths.ensure_directories()
    (root / "talamus.json").write_text("{}", encoding="utf-8")
    for title, retrieval in notes:
        write_note(paths, _note(title, retrieval))
    rebuild_indexes(paths)


class FederationTests(unittest.TestCase):
    def test_build_and_search_across_two_brains(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as a,
            tempfile.TemporaryDirectory() as b,
        ):
            _brain(Path(a), [("Pattern Retry", "pattern retry con backoff esponenziale")])
            _brain(Path(b), [("Decisione Architettura", "scelta architettura esagonale")])
            register_brain(Path(a), name="alpha", home=Path(home))
            register_brain(Path(b), name="beta", home=Path(home))
            report = build_federated_index(home=Path(home))
            self.assertEqual(report["rows"], 2)
            self.assertEqual(report["warnings"], [])
            results, warnings = search_federated("retry backoff", home=Path(home))
            self.assertEqual(warnings, [])
            self.assertTrue(results)
            top = results[0]
            self.assertEqual(top["title"], "Pattern Retry")
            self.assertEqual(top["brain_name"], "alpha")
            self.assertTrue(top["brain_id"].startswith("brain-"))
            # pointer leads to the real note in the owning brain
            self.assertTrue(Path(top["note_path"]).is_file())

    def test_missing_brain_degrades_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as a:
            _brain(Path(a), [("Nota Vera", "contenuto reale")])
            register_brain(Path(a), name="ok", home=Path(home))
            ghost = Path(home) / "ghost-brain"
            ghost.mkdir()
            register_brain(ghost, name="ghost", home=Path(home))  # no talamus.json
            report = build_federated_index(home=Path(home))
            self.assertEqual(report["rows"], 1)
            self.assertTrue(any("ghost" in w for w in report["warnings"]))

    def test_sensitive_brain_excluded_by_default(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as a,
            tempfile.TemporaryDirectory() as b,
        ):
            _brain(Path(a), [("Pubblica", "argomento condiviso pubblico")])
            _brain(Path(b), [("Riservata", "argomento condiviso riservato")])
            register_brain(Path(a), name="open", home=Path(home))
            register_brain(Path(b), name="secret", home=Path(home))
            set_brain_flag("secret", "sensitive", True, home=Path(home))
            build_federated_index(home=Path(home))
            results, _ = search_federated("argomento condiviso", home=Path(home))
            self.assertEqual({r["brain_name"] for r in results}, {"open"})
            results_opt_in, _ = search_federated(
                "argomento condiviso", home=Path(home), include_sensitive=True
            )
            self.assertEqual({r["brain_name"] for r in results_opt_in}, {"open", "secret"})

    def test_not_federated_brain_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as a:
            _brain(Path(a), [("Nota", "contenuto")])
            register_brain(Path(a), name="solo", home=Path(home))
            set_brain_flag("solo", "federated", False, home=Path(home))
            report = build_federated_index(home=Path(home))
            self.assertEqual(report["rows"], 0)

    def test_status_and_unbuilt_search_warn(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            self.assertFalse(federation_status(home=Path(home))["built"])
            results, warnings = search_federated("qualunque", home=Path(home))
            self.assertEqual(results, [])
            self.assertTrue(warnings)

    def test_boost_prefers_current_brain(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as a,
            tempfile.TemporaryDirectory() as b,
        ):
            _brain(Path(a), [("Gemella A", "argomento identico condiviso")])
            _brain(Path(b), [("Gemella B", "argomento identico condiviso")])
            info_a = register_brain(Path(a), name="aaa", home=Path(home))
            register_brain(Path(b), name="bbb", home=Path(home))
            build_federated_index(home=Path(home))
            results, _ = search_federated(
                "argomento identico", home=Path(home), boost_brain_ids=[info_a.id]
            )
            self.assertEqual(results[0]["brain_name"], "aaa")


if __name__ == "__main__":
    unittest.main()
