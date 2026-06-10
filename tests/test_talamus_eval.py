import json
import tempfile
import unittest
from pathlib import Path

from talamus.eval import (
    EvalCase,
    evaluate,
    load_cases,
    search_retriever,
)
from talamus.models import CanonicalNote, SourceRef
from talamus.paths import TalamusPaths
from talamus.store import rebuild_indexes, write_note


def _note(title: str, summary: str, retrieval: str) -> CanonicalNote:
    src = SourceRef("raw/a.md", "norm/a#1", "section 1", "sha256:x", ["claim"])
    return CanonicalNote(
        note_id=title.lower().replace(" ", "-"),
        title=title,
        aliases=[],
        folder="",
        tags=[],
        summary=summary,
        retrieval_text=retrieval,
        body_sections={"definizione": summary},
        proposed_links=[],
        relations=[],
        sources=[src],
        confidence=0.9,
    )


class EvalMetricsTests(unittest.TestCase):
    def test_metrics_are_computed_exactly(self) -> None:
        ranked = {
            "q1": ["X", "A", "C"],  # relevant {A,B}: hit, recall .5, prec 1/3, rr .5
            "q2": ["E", "F", "G"],  # relevant {D}: miss, all zero
        }
        cases = [
            EvalCase("q1", ["A", "B"]),
            EvalCase("q2", ["D"]),
        ]
        report = evaluate(cases, lambda q, k: ranked[q], k=3)
        self.assertEqual(report.n_cases, 2)
        self.assertAlmostEqual(report.recall_at_k, 0.25, places=4)
        self.assertAlmostEqual(report.precision_at_k, (1 / 3) / 2, places=4)
        self.assertAlmostEqual(report.mrr, 0.25, places=4)
        self.assertAlmostEqual(report.hit_rate, 0.5, places=4)

    def test_case_matching_is_case_insensitive(self) -> None:
        cases = [EvalCase("q", ["Retrieval-Augmented Generation"])]
        report = evaluate(cases, lambda q, k: ["retrieval-augmented generation"], k=5)
        self.assertEqual(report.hit_rate, 1.0)
        self.assertEqual(report.cases[0].reciprocal_rank, 1.0)

    def test_reciprocal_rank_uses_first_relevant_position(self) -> None:
        cases = [EvalCase("q", ["B"])]
        report = evaluate(cases, lambda q, k: ["A", "B", "C"], k=5)
        self.assertAlmostEqual(report.mrr, 0.5, places=4)


class EvalHarnessOverBrainTests(unittest.TestCase):
    def _brain(self, tmp: str) -> TalamusPaths:
        paths = TalamusPaths(Path(tmp))
        paths.ensure_directories()
        write_note(
            paths,
            _note(
                "Retrieval-Augmented Generation",
                "Collega il modello a fonti esterne.",
                "rag fonti esterne documenti recupero",
            ),
        )
        write_note(
            paths,
            _note("Vector Store", "Memorizza embeddings.", "vector store embeddings ricerca"),
        )
        rebuild_indexes(paths)
        return paths

    def test_search_retriever_scores_a_relevant_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._brain(tmp)
            cases = [
                EvalCase("recupero documenti da fonti esterne", ["Retrieval-Augmented Generation"])
            ]
            report = evaluate(cases, search_retriever(paths), k=5)
            self.assertEqual(report.hit_rate, 1.0)
            self.assertGreater(report.mrr, 0.0)

    def test_report_table_lists_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._brain(tmp)
            cases = [EvalCase("argomento del tutto assente", ["Inesistente"])]
            report = evaluate(cases, search_retriever(paths), k=5)
            self.assertEqual(report.hit_rate, 0.0)
            self.assertIn("mancati", report.format_table())


class LoadCasesTests(unittest.TestCase):
    def test_load_cases_accepts_list_and_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            as_list = Path(tmp) / "a.json"
            as_list.write_text(json.dumps([{"question": "q", "relevant": ["A"]}]), encoding="utf-8")
            as_obj = Path(tmp) / "b.json"
            as_obj.write_text(
                json.dumps({"cases": [{"question": "q", "relevant": ["A"]}]}), encoding="utf-8"
            )
            self.assertEqual(len(load_cases(as_list)), 1)
            self.assertEqual(len(load_cases(as_obj)), 1)

    def test_load_cases_skips_incomplete_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(
                json.dumps(
                    [
                        {"question": "", "relevant": ["A"]},
                        {"question": "q", "relevant": []},
                        {"question": "good", "relevant": ["A"]},
                    ]
                ),
                encoding="utf-8",
            )
            cases = load_cases(path)
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].question, "good")


class NegativeAndCategoryTests(unittest.TestCase):
    def test_negative_case_passes_when_nothing_retrieved(self) -> None:
        cases = [EvalCase("argomento assente", [], category="negative")]
        report = evaluate(cases, lambda q, k: [], k=5)
        self.assertEqual(report.n_negative, 1)
        self.assertEqual(report.negative_rejection, 1.0)

    def test_negative_case_fails_when_something_retrieved(self) -> None:
        cases = [EvalCase("argomento assente", [], category="negative")]
        report = evaluate(cases, lambda q, k: ["Rumore"], k=5)
        self.assertEqual(report.negative_rejection, 0.0)

    def test_negatives_do_not_drag_answerable_metrics(self) -> None:
        cases = [
            EvalCase("q1", ["A"], category="direct"),
            EvalCase("assente", [], category="negative"),
        ]
        report = evaluate(cases, lambda q, k: ["A"] if q == "q1" else [], k=5)
        self.assertEqual(report.hit_rate, 1.0)  # 1/1 answerable, not 1/2
        self.assertEqual(report.recall_at_k, 1.0)

    def test_per_category_breakdown(self) -> None:
        cases = [
            EvalCase("q1", ["A"], category="direct"),
            EvalCase("q2", ["B"], category="vague"),
        ]
        report = evaluate(cases, lambda q, k: ["A"], k=5)
        self.assertEqual(report.categories["direct"]["hit_rate"], 1.0)
        self.assertEqual(report.categories["vague"]["hit_rate"], 0.0)

    def test_load_cases_keeps_negative_and_filters_by_category(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text(
                json.dumps(
                    [
                        {"id": "d1", "question": "q1", "relevant": ["A"], "category": "direct"},
                        {"id": "n1", "question": "assente", "relevant": [], "category": "negative"},
                        {"question": "malformato senza relevant", "relevant": []},
                    ]
                ),
                encoding="utf-8",
            )
            all_cases = load_cases(path)
            self.assertEqual(len(all_cases), 2)  # malformed non-negative skipped
            self.assertTrue(all_cases[1].negative)
            only_direct = load_cases(path, category="direct")
            self.assertEqual(len(only_direct), 1)
            self.assertEqual(only_direct[0].case_id, "d1")


class CliEvalTests(unittest.TestCase):
    def _brain(self, tmp: str) -> TalamusPaths:
        paths = TalamusPaths(Path(tmp))
        paths.ensure_directories()
        write_note(
            paths,
            _note("Reranking", "Riordina i candidati.", "reranking riordino candidati recupero"),
        )
        rebuild_indexes(paths)
        return paths

    def test_eval_command_runs_and_reports(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            self._brain(tmp)
            cases = Path(tmp) / "cases.json"
            cases.write_text(
                json.dumps([{"question": "come riordino i candidati?", "relevant": ["Reranking"]}]),
                encoding="utf-8",
            )
            code = main(["eval", "--cases", str(cases), "--root", tmp, "--json"])
            self.assertEqual(code, 0)

    def test_eval_missing_cases_file_returns_error(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            self._brain(tmp)
            code = main(["eval", "--cases", str(Path(tmp) / "nope.json"), "--root", tmp])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
