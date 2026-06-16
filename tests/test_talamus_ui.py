import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_HAS_FLET = importlib.util.find_spec("flet") is not None


@unittest.skipUnless(_HAS_FLET, "flet not installed (ui extra)")
class WikilinkConversionTests(unittest.TestCase):
    """Pure conversion logic of the Flet UI — no window needed."""

    def _convert(self, text: str) -> str:
        from talamus.ui.views import wikilinks_to_md

        return wikilinks_to_md(text)

    def test_plain_wikilink_becomes_angle_bracketed_link(self) -> None:
        self.assertEqual(self._convert("see [[Embedding]]"), "see [Embedding](<Embedding>)")

    def test_aliased_wikilink_uses_label_and_target(self) -> None:
        self.assertEqual(
            self._convert("[[Embedding|gli embedding]]"), "[gli embedding](<Embedding>)"
        )

    def test_target_with_spaces_stays_one_url(self) -> None:
        self.assertEqual(self._convert("[[Vector Store]]"), "[Vector Store](<Vector Store>)")

    def test_text_without_wikilinks_is_unchanged(self) -> None:
        self.assertEqual(self._convert("nessun link qui"), "nessun link qui")


@unittest.skipUnless(_HAS_FLET, "flet not installed (ui extra)")
class WorkbenchBuildersSmokeTests(unittest.TestCase):
    """F9.14: every view builds headless on a demo brain AND on an empty brain —
    Flet controls are constructible without a window; rendering stays a runtime check."""

    def _builders(self, paths):
        from talamus.ui import views

        noop = lambda *_args: None  # noqa: E731
        return {
            "home": lambda: views.build_home(paths),
            "note": lambda: views.build_notes(paths, noop),
            "domini": lambda: views.build_domains(paths, noop),
            "grafo_unfocused": lambda: views.build_graph(paths, "", noop),
            "grafo_focused": lambda: views.build_graph(paths, "Reranking", noop),
            "timeline": lambda: views.build_timeline(paths, "Reranking"),
            "review": lambda: views.build_review(paths, noop),
            "ontologia": lambda: views.build_ontology_lab(paths, noop),
            "impostazioni": lambda: views.build_settings(paths),
        }

    def _walk_controls(self, control):
        def walk(item):
            yield item
            content = getattr(item, "content", None)
            if content is not None:
                yield from walk(content)
            for child in getattr(item, "controls", []) or []:
                yield from walk(child)

        yield from walk(control)

    def _rendered_text(self, control) -> str:
        values = []
        for item in self._walk_controls(control):
            value = getattr(item, "value", None)
            if value is not None:
                values.append(str(value))
        return "\n".join(values)

    def test_all_views_build_on_demo_brain(self) -> None:
        import flet as ft

        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            create_demo_brain(paths)
            for name, builder in self._builders(paths).items():
                control = builder()
                self.assertIsInstance(control, ft.Control, name)

    def test_home_builds_without_creating_brain_files(self) -> None:
        import flet as ft

        from talamus.paths import TalamusPaths
        from talamus.ui import views

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            control = views.build_home(paths)
            self.assertIsInstance(control, ft.Control)
            self.assertFalse(paths.config_path.exists())
            self.assertFalse(paths.talamus_dir.exists())

    def test_home_renders_readiness_report(self) -> None:
        from talamus.paths import TalamusPaths
        from talamus.ui import views

        report = SimpleNamespace(
            root="C:/example/project",
            config_exists=True,
            notes=3,
            sources=2,
            reviews_pending=1,
            jobs_active=4,
            index_backend="sqlite",
            engines=[
                SimpleNamespace(
                    label="Codex CLI",
                    status="ready",
                    configured=True,
                    detail="codex executable",
                ),
                SimpleNamespace(
                    label="Gemini CLI",
                    status="not_installed",
                    configured=False,
                    detail="Command not found: gemini",
                ),
            ],
            next_actions=[
                SimpleNamespace(label="Review queue", detail="Apply or reject pending items.")
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            with patch.object(views, "inspect_readiness", return_value=report) as inspect:
                control = views.build_home(paths)

        inspect.assert_called_once_with(root=str(paths.project_root))
        rendered = self._rendered_text(control)
        self.assertIn("C:/example/project", rendered)
        self.assertIn("sqlite", rendered)
        self.assertIn("Codex CLI", rendered)
        self.assertIn("selected", rendered)
        self.assertIn("Gemini CLI", rendered)
        self.assertIn("not_installed", rendered)
        self.assertIn("Command not found: gemini", rendered)
        self.assertIn("Review queue", rendered)
        self.assertIn("Apply or reject pending items.", rendered)

    def test_home_renders_ready_state_without_next_actions(self) -> None:
        from talamus.paths import TalamusPaths
        from talamus.ui import views

        report = SimpleNamespace(
            root="C:/example/project",
            config_exists=True,
            notes=3,
            sources=2,
            reviews_pending=0,
            jobs_active=0,
            index_backend="sqlite",
            engines=[],
            next_actions=[],
        )

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            with patch.object(views, "inspect_readiness", return_value=report):
                control = views.build_home(paths)

        rendered = self._rendered_text(control)
        self.assertIn("Ready", rendered)
        self.assertIn("This brain is ready for questions.", rendered)

    def test_home_next_action_button_calls_callback_with_target(self) -> None:
        import flet as ft

        from talamus.paths import TalamusPaths
        from talamus.ui import views

        report = SimpleNamespace(
            root="C:/example/project",
            config_exists=True,
            notes=0,
            sources=0,
            reviews_pending=0,
            jobs_active=0,
            index_backend="json",
            engines=[],
            next_actions=[
                SimpleNamespace(
                    label="Ask a question",
                    detail="Open chat.",
                    target="ask",
                )
            ],
        )
        clicked: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            with patch.object(views, "inspect_readiness", return_value=report):
                control = views.build_home(paths, clicked.append)

        buttons = [
            item
            for item in self._walk_controls(control)
            if isinstance(item, ft.TextButton) and getattr(item, "content", None) == "Apri"
        ]
        self.assertEqual(len(buttons), 1)

        buttons[0].on_click(None)

        self.assertEqual(clicked, ["ask"])

    def test_home_action_route_aliases_match_existing_views(self) -> None:
        from talamus.ui.app import _view_name_for_home_action

        builder_keys = {
            "home",
            "chat",
            "cerca",
            "note",
            "domini",
            "grafo",
            "timeline",
            "ingest",
            "review",
            "ontologia",
            "impostazioni",
        }
        readiness_targets = {"brains", "demo", "system", "import", "review", "ontology", "ask"}
        for target in readiness_targets:
            with self.subTest(target=target):
                self.assertIn(_view_name_for_home_action(target), builder_keys)

        cases = {
            "ask": "chat",
            "import": "ingest",
            "system": "impostazioni",
            "demo": "home",
            "brains": "impostazioni",
            "ontology": "ontologia",
            "future": "future",
        }
        for target, expected in cases.items():
            with self.subTest(target=target):
                self.assertEqual(_view_name_for_home_action(target), expected)

    def test_all_views_build_on_empty_brain(self) -> None:
        import flet as ft

        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            for name, builder in self._builders(paths).items():
                control = builder()
                self.assertIsInstance(control, ft.Control, name)

    def test_graph_canvas_builds_headless_global_and_focused(self) -> None:
        import flet as ft

        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths
        from talamus.ui.graph import build_graph_canvas

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            create_demo_brain(paths)
            for focus in ("", "Reranking"):
                control = build_graph_canvas(paths, focus, lambda t: None, animate=False)
                self.assertIsInstance(control, ft.Control, focus or "global")

    def test_graph_canvas_on_empty_brain_shows_empty_state(self) -> None:
        import flet as ft

        from talamus.paths import TalamusPaths
        from talamus.ui.graph import build_graph_canvas

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            control = build_graph_canvas(paths, "", lambda t: None, animate=False)
            self.assertIsInstance(control, ft.Control)

    def test_run_app_signature_supports_web_mode(self) -> None:
        import inspect

        from talamus.ui.app import run_app

        parameters = inspect.signature(run_app).parameters
        self.assertIn("web", parameters)
        self.assertIn("port", parameters)


if __name__ == "__main__":
    unittest.main()
