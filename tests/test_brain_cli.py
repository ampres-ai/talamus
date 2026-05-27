import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from brain.cli import main


class BrainCliTests(unittest.TestCase):
    def test_init_creates_project_layout_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["init", "--root", tmp])

            self.assertEqual(0, code)
            self.assertTrue((Path(tmp) / "brain.json").is_file())
            self.assertTrue((Path(tmp) / "knowledge" / "raw").is_dir())
            self.assertTrue((Path(tmp) / "knowledge" / "notes").is_dir())

    def test_status_returns_zero_after_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(0, main(["init", "--root", tmp]))

            code = main(["status", "--root", tmp])

            self.assertEqual(0, code)

    def test_status_rejects_required_directory_replaced_by_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(0, main(["init", "--root", tmp]))
            raw_path = Path(tmp) / "knowledge" / "raw"
            shutil.rmtree(raw_path)
            raw_path.write_text("not a directory", encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                code = main(["status", "--root", tmp])

            self.assertEqual(1, code)
            self.assertIn("not a directory", stderr.getvalue())

    def test_doctor_returns_zero_with_config_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(0, main(["init", "--root", tmp]))

            code = main(["doctor", "--root", tmp])

            self.assertEqual(0, code)

    def test_doctor_reports_malformed_config_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(0, main(["init", "--root", tmp]))
            (Path(tmp) / "brain.json").write_text("{invalid json", encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                code = main(["doctor", "--root", tmp])

            self.assertEqual(1, code)
            self.assertIn("config error", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
