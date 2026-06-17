import tempfile
import unittest
from pathlib import Path

from talamus.jobs import JobStore
from talamus.paths import TalamusPaths
from talamus.services.jobs import cancel_job, get_job, list_jobs, read_job_log


class JobServiceTests(unittest.TestCase):
    def test_list_status_log_and_cancel_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(TalamusPaths(root))
            record = store.create("eval", {"case": "demo"})
            store.log(record.job_id, "started")

            listed = list_jobs(root)
            loaded = get_job(root, record.job_id)
            log = read_job_log(root, record.job_id)
            cancelled = cancel_job(root, record.job_id)

        self.assertTrue(listed.success)
        self.assertIsNotNone(listed.data)
        self.assertEqual(record.job_id, listed.data[0].job_id)
        self.assertEqual({"case": "demo"}, listed.data[0].payload)
        self.assertTrue(loaded.success)
        self.assertIsNotNone(loaded.data)
        self.assertEqual("queued", loaded.data.state)
        self.assertTrue(log.success)
        self.assertIsNotNone(log.data)
        self.assertIn("started", log.data.log)
        self.assertTrue(cancelled.success)
        self.assertIsNotNone(cancelled.data)
        self.assertEqual("cancelled", cancelled.data.state)

    def test_missing_and_terminal_jobs_return_failed_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = JobStore(TalamusPaths(root))
            record = store.create("eval")
            self.assertTrue(store.cancel(record.job_id))

            missing = get_job(root, "missing")
            terminal = cancel_job(root, record.job_id)

        self.assertFalse(missing.success)
        self.assertEqual("job_not_found", missing.code)
        self.assertFalse(terminal.success)
        self.assertEqual("job_not_cancellable", terminal.code)

    def test_wrong_shaped_job_record_returns_failed_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = TalamusPaths(root)
            jobs_dir = paths.cache / "jobs"
            jobs_dir.mkdir(parents=True)
            (jobs_dir / "bad.json").write_text("[]", encoding="utf-8")

            listed = list_jobs(root)
            loaded = get_job(root, "bad")
            log = read_job_log(root, "bad")
            cancelled = cancel_job(root, "bad")

        self.assertFalse(listed.success)
        self.assertEqual("job_store_error", listed.code)
        self.assertFalse(loaded.success)
        self.assertEqual("job_store_error", loaded.code)
        self.assertFalse(log.success)
        self.assertEqual("job_store_error", log.code)
        self.assertFalse(cancelled.success)
        self.assertEqual("job_store_error", cancelled.code)


if __name__ == "__main__":
    unittest.main()
