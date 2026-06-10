import tempfile
import unittest
from pathlib import Path

from talamus.jobs import JobStore, run_items
from talamus.paths import TalamusPaths


class JobStoreTests(unittest.TestCase):
    def test_create_persists_before_any_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(TalamusPaths(Path(tmp)))
            record = store.create("scan", payload={"files": ["a", "b"]})
            self.assertEqual(record.state, "queued")
            reloaded = store.load(record.job_id)
            self.assertIsNotNone(reloaded)
            self.assertEqual(reloaded.payload, {"files": ["a", "b"]})

    def test_invalid_kind_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(TalamusPaths(Path(tmp)))
            with self.assertRaises(ValueError):
                store.create("nonsense")

    def test_illegal_transition_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(TalamusPaths(Path(tmp)))
            record = store.create("eval")
            with self.assertRaises(ValueError):
                store.transition(record, "completed")  # queued -> completed is illegal

    def test_cancel_only_non_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(TalamusPaths(Path(tmp)))
            record = store.create("eval")
            self.assertTrue(store.cancel(record.job_id))
            self.assertFalse(store.cancel(record.job_id))  # already cancelled
            self.assertIn("cancelled", store.read_log(record.job_id))

    def test_list_returns_all_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(TalamusPaths(Path(tmp)))
            store.create("eval")
            store.create("export")
            self.assertEqual(len(store.list()), 2)


class RunItemsTests(unittest.TestCase):
    def test_crash_then_resume_skips_done_items(self) -> None:
        """The M2 gate: a simulated crash leaves a resumable job; resume re-does nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(TalamusPaths(Path(tmp)))
            record = store.create("ingest", payload={"items": ["a", "b", "c"]})
            handled: list[str] = []

            def crashing(item: str) -> None:
                if item == "b":
                    raise RuntimeError("simulated crash")
                handled.append(item)

            with self.assertRaises(RuntimeError):
                run_items(store, record, ["a", "b", "c"], crashing)
            crashed = store.load(record.job_id)
            self.assertEqual(crashed.state, "failed")
            self.assertEqual(crashed.progress["done_items"], ["a"])
            self.assertIn("simulated crash", crashed.error)

            resumed = run_items(store, crashed, ["a", "b", "c"], handled.append)
            self.assertEqual(resumed.state, "completed")
            # "a" was NOT re-done: only b and c ran on resume
            self.assertEqual(handled, ["a", "b", "c"])

    def test_cooperative_cancel_stops_without_corruption(self) -> None:
        """The M2 gate: cancelling mid-run keeps completed writes intact, does no more."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            store = JobStore(paths)
            record = store.create("ingest")
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()

            def writing(item: str) -> None:
                (out_dir / f"{item}.txt").write_text(f"contenuto {item}", encoding="utf-8")
                if item == "a":  # someone cancels after the first item completes
                    store.cancel(record.job_id)

            final = run_items(store, record, ["a", "b", "c"], writing)
            self.assertEqual(final.state, "cancelled")
            self.assertTrue((out_dir / "a.txt").is_file())  # completed work intact
            self.assertEqual((out_dir / "a.txt").read_text(encoding="utf-8"), "contenuto a")
            self.assertFalse((out_dir / "b.txt").exists())  # nothing after the cancel
            self.assertFalse((out_dir / "c.txt").exists())

    def test_clean_run_completes_with_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(TalamusPaths(Path(tmp)))
            record = store.create("eval")
            final = run_items(store, record, ["x", "y"], lambda item: None, stage="test")
            self.assertEqual(final.state, "completed")
            self.assertEqual(final.progress["done"], 2)
            self.assertEqual(final.progress["total"], 2)
            self.assertIn("completed", store.read_log(record.job_id))


class CliJobsTests(unittest.TestCase):
    def test_jobs_list_status_cancel_logs(self) -> None:
        import io
        import json
        from contextlib import redirect_stderr, redirect_stdout

        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(TalamusPaths(Path(tmp)))
            record = store.create("eval")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["jobs", "list", "--root", tmp, "--json"]))
            self.assertEqual(json.loads(out.getvalue())[0]["job_id"], record.job_id)
            self.assertEqual(0, main(["jobs", "status", record.job_id, "--root", tmp]))
            self.assertEqual(0, main(["jobs", "cancel", record.job_id, "--root", tmp]))
            self.assertEqual(0, main(["jobs", "logs", record.job_id, "--root", tmp]))
            with redirect_stderr(io.StringIO()):
                self.assertEqual(1, main(["jobs", "status", "manca", "--root", tmp]))

    def test_resume_without_runner_is_actionable(self) -> None:
        import io
        from contextlib import redirect_stderr

        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(TalamusPaths(Path(tmp)))
            record = store.create("eval")
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(1, main(["jobs", "resume", record.job_id, "--root", tmp]))
            self.assertIn("fix:", err.getvalue())


if __name__ == "__main__":
    unittest.main()
