import tempfile
import unittest
from pathlib import Path

from talamus.registry import (
    central_brain,
    load_registry,
    register_brain,
    rename_brain,
    select_brain,
    selected_brain,
    set_brain_flag,
    unregister_brain,
)


class RegistryTests(unittest.TestCase):
    def test_register_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as brain_dir:
            info = register_brain(Path(brain_dir), name="alpha", home=Path(home))
            self.assertEqual(info.name, "alpha")
            self.assertTrue(info.id.startswith("brain-"))
            registry = load_registry(Path(home))
            self.assertEqual(len(registry.brains), 1)
            self.assertEqual(registry.by_name("alpha").path, str(Path(brain_dir).resolve()))

    def test_register_is_idempotent_by_path(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as brain_dir:
            first = register_brain(Path(brain_dir), name="alpha", home=Path(home))
            second = register_brain(Path(brain_dir), name="ignored", home=Path(home))
            self.assertEqual(first.id, second.id)
            self.assertEqual(len(load_registry(Path(home)).brains), 1)

    def test_duplicate_names_get_suffix(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as a,
            tempfile.TemporaryDirectory() as b,
        ):
            register_brain(Path(a), name="alpha", home=Path(home))
            second = register_brain(Path(b), name="alpha", home=Path(home))
            self.assertEqual(second.name, "alpha-2")

    def test_rename_select_flags_unregister(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as brain_dir:
            register_brain(Path(brain_dir), name="alpha", home=Path(home))
            self.assertTrue(select_brain("alpha", home=Path(home)))
            self.assertEqual(selected_brain(home=Path(home)).name, "alpha")
            self.assertTrue(rename_brain("alpha", "beta", home=Path(home)))
            self.assertEqual(load_registry(Path(home)).selected, "beta")
            self.assertTrue(set_brain_flag("beta", "sensitive", True, home=Path(home)))
            self.assertTrue(load_registry(Path(home)).by_name("beta").sensitive)
            self.assertTrue(unregister_brain("beta", home=Path(home)))
            self.assertEqual(load_registry(Path(home)).brains, [])
            self.assertEqual(load_registry(Path(home)).selected, "")
            # files on disk are never touched
            self.assertTrue(Path(brain_dir).exists())

    def test_rename_to_existing_name_raises(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home,
            tempfile.TemporaryDirectory() as a,
            tempfile.TemporaryDirectory() as b,
        ):
            register_brain(Path(a), name="alpha", home=Path(home))
            register_brain(Path(b), name="beta", home=Path(home))
            with self.assertRaises(ValueError):
                rename_brain("alpha", "beta", home=Path(home))

    def test_invalid_type_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as brain_dir:
            with self.assertRaises(ValueError):
                register_brain(Path(brain_dir), brain_type="nonsense", home=Path(home))

    def test_central_brain_prefers_registered_central(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as brain_dir:
            self.assertIsNone(central_brain(home=Path(home)))
            register_brain(Path(brain_dir), name="hub", brain_type="central", home=Path(home))
            central = central_brain(home=Path(home))
            self.assertIsNotNone(central)
            self.assertEqual(central.name, "hub")

    def test_central_brain_falls_back_to_home_default(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            default = Path(home) / "default"
            default.mkdir()
            (default / "talamus.json").write_text("{}", encoding="utf-8")
            central = central_brain(home=Path(home))
            self.assertIsNotNone(central)
            self.assertEqual(central.name, "default")

    def test_corrupt_registry_degrades_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / "registry.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(load_registry(Path(home)).brains, [])


if __name__ == "__main__":
    unittest.main()
