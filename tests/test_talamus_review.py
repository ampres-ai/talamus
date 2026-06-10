import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from talamus.paths import TalamusPaths
from talamus.review import ReviewQueue


class ReviewQueueTests(unittest.TestCase):
    def test_add_list_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = ReviewQueue(TalamusPaths(Path(tmp)))
            item = queue.add("correction", "Nota X non combacia con la fonte", {"note": "X"})
            self.assertEqual(item.status, "pending")
            self.assertEqual(len(queue.list(status="pending")), 1)
            applied = queue.apply(item.item_id, "correzione applicata")
            self.assertEqual(applied.status, "applied")
            self.assertEqual(queue.list(status="pending"), [])
            # decision is kept, not deleted
            self.assertEqual(len(queue.list()), 1)

    def test_reject_is_logged_not_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = ReviewQueue(TalamusPaths(Path(tmp)))
            item = queue.add("duplicate_concept", "Forse duplicato", {})
            rejected = queue.reject(item.item_id, "non sono duplicati")
            self.assertEqual(rejected.status, "rejected")
            kept = queue.get(item.item_id)
            self.assertEqual(kept.resolution, "non sono duplicati")

    def test_apply_non_pending_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = ReviewQueue(TalamusPaths(Path(tmp)))
            item = queue.add("stale_source", "Fonte cambiata", {})
            queue.reject(item.item_id)
            self.assertIsNone(queue.apply(item.item_id))

    def test_invalid_kind_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = ReviewQueue(TalamusPaths(Path(tmp)))
            with self.assertRaises(ValueError):
                queue.add("nonsense", "x", {})


class CliReviewTests(unittest.TestCase):
    def test_review_flow_via_cli(self) -> None:
        from talamus.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            queue = ReviewQueue(TalamusPaths(Path(tmp)))
            item = queue.add("low_confidence_note", "Nota dubbia", {"why": "confidence 0.3"})
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["review", "list", "--root", tmp]))
            self.assertIn(item.item_id, out.getvalue())
            self.assertEqual(0, main(["review", "show", item.item_id, "--root", tmp]))
            self.assertEqual(0, main(["review", "apply", item.item_id, "--root", tmp]))
            out2 = io.StringIO()
            with redirect_stdout(out2):
                main(["review", "list", "--root", tmp])
            self.assertIn("empty", out2.getvalue())
            out3 = io.StringIO()
            with redirect_stdout(out3):
                main(["review", "list", "--all", "--root", tmp])
            self.assertIn(item.item_id, out3.getvalue())


if __name__ == "__main__":
    unittest.main()
