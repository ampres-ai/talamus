import importlib.util
import os
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
            "notes": lambda: views.build_notes(paths, noop),
            "domains": lambda: views.build_domains(paths, noop),
            "graph_unfocused": lambda: views.build_graph(paths, "", noop),
            "graph_focused": lambda: views.build_graph(paths, "Reranking", noop),
            "timeline": lambda: views.build_timeline(paths, "Reranking"),
            "review": lambda: views.build_review(paths, noop),
            "ontology": lambda: views.build_ontology_lab(paths, noop),
            "settings": lambda: views.build_settings(paths),
        }

    def _walk_controls(self, control):
        def walk(item):
            yield item
            content = getattr(item, "content", None)
            if content is not None:
                yield from walk(content)
            for attr in ("title", "subtitle", "leading", "trailing"):
                child = getattr(item, attr, None)
                if child is not None:
                    yield from walk(child)
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

    def test_home_surfaces_moat_statuses(self) -> None:
        from talamus.paths import TalamusPaths
        from talamus.ui import views

        report = SimpleNamespace(
            root="C:/example/project",
            config_exists=True,
            notes=7,
            sources=5,
            reviews_pending=2,
            jobs_active=0,
            index_backend="sqlite",
            overview_domains=3,
            ontology_candidates=1,
            cache_current=True,
            engines=[],
            next_actions=[],
        )

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            with (
                patch.object(views, "inspect_readiness", return_value=report),
                patch.dict(os.environ, {"TALAMUS_CONTEXT_BUDGET": "4096"}),
            ):
                control = views.build_home(paths)

        rendered = self._rendered_text(control)
        self.assertIn("Time", rendered)
        self.assertIn("as-of ready", rendered)
        self.assertIn("Meaning", rendered)
        self.assertIn("3 domains", rendered)
        self.assertIn("Verifiability", rendered)
        self.assertIn("5 sources", rendered)
        self.assertIn("Cost", rendered)
        self.assertIn("4096 token budget", rendered)
        self.assertIn("Language", rendered)

    def test_home_matches_hybrid_brain_os_shell_copy(self) -> None:
        from talamus.paths import TalamusPaths
        from talamus.ui import views

        report = SimpleNamespace(
            root="C:/example/project",
            config_exists=True,
            notes=7,
            sources=5,
            reviews_pending=2,
            jobs_active=1,
            index_backend="sqlite",
            overview_domains=3,
            ontology_candidates=1,
            cache_current=True,
            mcp_installed=False,
            engines=[],
            next_actions=[],
        )

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            with patch.object(views, "inspect_readiness", return_value=report):
                control = views.build_home(paths)

        rendered = self._rendered_text(control)
        self.assertIn("Command Center", rendered)
        self.assertIn("No brain is created automatically.", rendered)
        self.assertIn("Next best actions", rendered)
        self.assertIn("Graph preview", rendered)
        self.assertIn("Token cost", rendered)
        self.assertIn("Language-native memory", rendered)

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
            if isinstance(item, ft.TextButton) and getattr(item, "content", None) == "Open"
        ]
        self.assertEqual(len(buttons), 1)

        buttons[0].on_click(None)

        self.assertEqual(clicked, ["ask"])

    def test_notes_builder_reads_from_library_service(self) -> None:
        from talamus.paths import TalamusPaths
        from talamus.services.result import ServiceResult
        from talamus.ui import views

        report = SimpleNamespace(
            notes=[
                SimpleNamespace(
                    title="Alpha",
                    summary="First note",
                    aliases=[],
                    tags=[],
                    confidence=1.0,
                    updated_at="",
                    source_count=0,
                    relation_count=0,
                    proposed_link_count=0,
                    markdown_path="",
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            with patch.object(
                views,
                "list_library_notes",
                return_value=ServiceResult(True, "loaded", data=report),
            ) as listed:
                control = views.build_notes(paths, lambda title: None)

        listed.assert_called_once_with(paths.project_root)
        self.assertIn("Alpha", self._rendered_text(control))

    def test_review_actions_use_review_service(self) -> None:
        import flet as ft

        from talamus.paths import TalamusPaths
        from talamus.services.result import ServiceResult
        from talamus.ui import views

        item = SimpleNamespace(
            item_id="review-1",
            kind="correction",
            title="Fix this",
            detail={"title": "Fix this"},
        )
        refreshed: list[bool] = []

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            with (
                patch.object(
                    views,
                    "list_review_items",
                    return_value=ServiceResult(True, "loaded", data=[item]),
                ) as listed,
                patch.object(
                    views,
                    "apply_review_item",
                    return_value=ServiceResult(True, "applied", data=item),
                ) as applied,
            ):
                control = views.build_review(paths, lambda: refreshed.append(True))
                buttons = [
                    child
                    for child in self._walk_controls(control)
                    if isinstance(child, ft.TextButton)
                    and getattr(child, "content", None) == "Apply"
                ]
                self.assertEqual(len(buttons), 1)
                buttons[0].on_click(None)

        listed.assert_called_once_with(paths.project_root, status="pending")
        applied.assert_called_once_with(paths.project_root, "review-1")
        self.assertEqual(refreshed, [True])

    def test_ontology_builder_uses_ontology_service(self) -> None:
        from talamus.paths import TalamusPaths
        from talamus.services.result import ServiceResult
        from talamus.ui import views

        status = SimpleNamespace(
            schema_id="schema-test",
            version=2,
            coverage={"non_related": 4, "edges": 5, "non_related_share": 0.8},
        )
        candidate = SimpleNamespace(
            id="rel:test",
            name="test",
            definition="Test relation",
            examples=["A -> B"],
            support=3,
            status="candidate",
        )

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            with (
                patch.object(
                    views,
                    "get_ontology_status",
                    return_value=ServiceResult(True, "status", data=status),
                ) as loaded_status,
                patch.object(
                    views,
                    "list_ontology_candidates",
                    side_effect=[
                        ServiceResult(True, "active", data=[]),
                        ServiceResult(True, "candidate", data=[candidate]),
                        ServiceResult(True, "deprecated", data=[]),
                    ],
                ) as listed,
            ):
                control = views.build_ontology_lab(paths, lambda: None)

        loaded_status.assert_called_once_with(paths.project_root)
        self.assertEqual(
            [call.kwargs["status"] for call in listed.call_args_list],
            ["active", "candidate", "deprecated"],
        )
        rendered = self._rendered_text(control)
        self.assertIn("schema-test", rendered)
        self.assertIn("Test relation", rendered)

    def test_settings_save_engine_uses_engine_service(self) -> None:
        import flet as ft

        from talamus.paths import TalamusPaths
        from talamus.services.result import ServiceResult
        from talamus.ui import views

        settings = {"llm_provider": "claude-cli", "llm_model": "", "language": ""}
        engine = SimpleNamespace(
            provider="claude-cli",
            label="Claude CLI",
            available=True,
            configured=True,
        )
        messages: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            with (
                patch.object(
                    views,
                    "load_engine_settings",
                    return_value=ServiceResult(True, "loaded", data=settings),
                ),
                patch.object(views, "list_engines", return_value=[engine]),
                patch.object(
                    views,
                    "list_brains",
                    return_value=ServiceResult(
                        True,
                        "brains",
                        data=SimpleNamespace(
                            brains=[], selected="", registry_path="", unregistered=[]
                        ),
                    ),
                ),
                patch.object(
                    views,
                    "inspect_integrations",
                    return_value=ServiceResult(
                        True,
                        "integrations",
                        data=SimpleNamespace(
                            hook_command="talamus hook-run --root x",
                            mcp_installed=False,
                            mcp_config_path=".mcp.json",
                        ),
                    ),
                ),
                patch.object(
                    views,
                    "inspect_diagnostics",
                    return_value=ServiceResult(
                        True,
                        "diagnostics",
                        data=SimpleNamespace(index_backend="sqlite", index_bytes=12),
                    ),
                ),
                patch.object(
                    views,
                    "update_engine_settings",
                    return_value=ServiceResult(True, "saved", data=settings),
                ) as saved,
            ):
                control = views.build_settings(paths, messages.append)
                buttons = [
                    child
                    for child in self._walk_controls(control)
                    if isinstance(child, ft.FilledButton)
                    and getattr(child, "content", None) == "Save engine"
                ]
                self.assertEqual(len(buttons), 1)
                buttons[0].on_click(None)

        saved.assert_called_once_with(
            paths.project_root,
            provider="claude-cli",
            model="",
            language="",
        )
        self.assertEqual(messages, ["saved"])

    def test_home_action_route_aliases_match_existing_views(self) -> None:
        from talamus.ui.app import _view_name_for_home_action

        builder_keys = {
            "home",
            "chat",
            "search",
            "notes",
            "domains",
            "graph",
            "timeline",
            "ingest",
            "review",
            "ontology",
            "settings",
        }
        readiness_targets = {"brains", "demo", "system", "import", "review", "ontology", "ask"}
        for target in readiness_targets:
            with self.subTest(target=target):
                self.assertIn(_view_name_for_home_action(target), builder_keys)

        cases = {
            "ask": "chat",
            "import": "ingest",
            "system": "settings",
            "demo": "home",
            "brains": "settings",
            "ontology": "ontology",
            "future": "future",
        }
        for target, expected in cases.items():
            with self.subTest(target=target):
                self.assertEqual(_view_name_for_home_action(target), expected)

    def test_primary_navigation_matches_completion_spec(self) -> None:
        from talamus.ui.app import PRIMARY_NAV_DESTINATIONS, _view_name_for_home_action

        labels = [destination.label for destination in PRIMARY_NAV_DESTINATIONS]
        self.assertEqual(
            labels,
            [
                "Home",
                "Ask",
                "Library",
                "Import",
                "Graph",
                "Review",
                "Ontology",
                "Brains",
                "System",
            ],
        )

        builder_keys = {
            "home",
            "chat",
            "notes",
            "graph",
            "ingest",
            "review",
            "ontology",
            "settings",
        }
        for destination in PRIMARY_NAV_DESTINATIONS:
            with self.subTest(destination=destination.label):
                self.assertIn(_view_name_for_home_action(destination.view), builder_keys)

    def test_theme_has_shell_primitives_for_dense_workbench(self) -> None:
        import flet as ft

        from talamus.ui import theme

        panel = theme.panel(ft.Text("Body"))
        pill = theme.status_pill("Ready", tone="ready")
        metric = theme.metric("Engine", "Codex CLI", "selected")

        self.assertIsInstance(panel, ft.Container)
        self.assertEqual(panel.border_radius, 8)
        self.assertIsInstance(pill, ft.Container)
        self.assertIn("Ready", self._rendered_text(pill))
        self.assertIn("Engine", self._rendered_text(metric))

    def test_app_content_slot_is_a_dark_container_not_a_scroll_viewport(self) -> None:
        import flet as ft

        from talamus.ui import theme
        from talamus.ui.app import _build_content_slot

        slot = _build_content_slot()

        self.assertIsInstance(slot, ft.Container)
        self.assertIsNone(slot.expand)
        self.assertEqual(slot.bgcolor, theme.BG)
        self.assertIsNone(slot.content)

    def test_app_top_bar_has_no_expanded_wrapped_children(self) -> None:
        import flet as ft

        from talamus.ui.app import _build_top_bar

        top_bar = _build_top_bar(ft.Text("Home"), ft.Text("Root"))

        self.assertIn("Token cost visible", self._rendered_text(top_bar))
        for item in self._walk_controls(top_bar):
            if isinstance(item, ft.Row) and item.wrap:
                for child in item.controls:
                    self.assertIsNone(getattr(child, "expand", None))

    def test_app_formats_ask_token_promise(self) -> None:
        from talamus.ui.app import _format_ask_token_promise

        text = _format_ask_token_promise("How does retrieval work?", "")

        self.assertIn("No LLM call until Ask", text)
        self.assertIn("context cap", text)
        self.assertIn("question text", text)

    def test_app_formats_answer_trace(self) -> None:
        from talamus.ui.app import _format_answer_trace

        trace = {
            "route": "overview",
            "domains_chosen": ["dom-retrieval"],
            "routing_fallback": False,
            "items_read": ["notes/Reranking.md", "notes/Embedding.md"],
            "context_tokens": 412,
            "extra_items": 1,
        }

        text = _format_answer_trace(trace)

        self.assertIn("Route: overview", text)
        self.assertIn("Context: 412 tokens", text)
        self.assertIn("Notes read: 2", text)
        self.assertIn("dom-retrieval", text)

    def test_app_main_pane_uses_explicit_dark_background(self) -> None:
        import flet as ft

        from talamus.ui import theme
        from talamus.ui.app import _build_main_pane

        content = ft.Column()
        top_bar = theme.panel(ft.Text("Top"))
        pane = _build_main_pane(top_bar, content)

        self.assertIsInstance(pane, ft.Container)
        self.assertEqual(pane.bgcolor, theme.BG)
        inner = pane.content
        self.assertIsInstance(inner, ft.Column)
        self.assertIs(inner.controls[0], top_bar)
        self.assertIs(inner.controls[1], content)

    def test_inspector_collapses_on_narrow_shell_widths(self) -> None:
        from talamus.ui.app import _show_inspector_for_width

        self.assertFalse(_show_inspector_for_width(720))
        self.assertTrue(_show_inspector_for_width(1200))
        self.assertTrue(_show_inspector_for_width(None))

    def test_home_wrap_rows_do_not_use_expanded_children(self) -> None:
        import flet as ft

        from talamus.paths import TalamusPaths
        from talamus.ui import views

        with tempfile.TemporaryDirectory() as tmp:
            paths = TalamusPaths(Path(tmp))
            paths.ensure_directories()
            control = views.build_home(paths)

        for item in self._walk_controls(control):
            if isinstance(item, ft.Row) and item.wrap:
                for child in item.controls:
                    self.assertIsNone(getattr(child, "expand", None))

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

    def test_app_ingest_flow_uses_services(self) -> None:
        import inspect

        import talamus.ui.app as app

        source = inspect.getsource(app)
        self.assertNotIn("from talamus.scan import", source)
        self.assertNotIn("from talamus.ingest import", source)
        self.assertIn("from talamus.services.scan import", source)
        self.assertIn("from talamus.services.ingestion import", source)

    def test_app_home_route_builds_readiness_on_ui_thread(self) -> None:
        import inspect

        import talamus.ui.app as app

        source = inspect.getsource(app)
        self.assertIn("return views.build_home(paths, show_view)", source)
        self.assertNotIn("Inspecting local readiness", source)
        self.assertNotIn("home_generation", source)


if __name__ == "__main__":
    unittest.main()
