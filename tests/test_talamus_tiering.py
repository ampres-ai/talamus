import unittest


class TaskIntentDefaultsTests(unittest.TestCase):
    def test_every_task_class_has_a_default_intent(self) -> None:
        from talamus.routing import DEFAULT_INTENTS, TaskClass

        for task in TaskClass:
            self.assertIn(task, DEFAULT_INTENTS)
            intent = DEFAULT_INTENTS[task]
            self.assertIn(intent.tier, ("economy", "quality"))
            self.assertIn(intent.effort, ("low", "high"))

    def test_cost_minimizing_defaults_match_the_design(self) -> None:
        from talamus.routing import DEFAULT_INTENTS, TaskClass

        self.assertEqual(DEFAULT_INTENTS[TaskClass.EXTRACTION].tier, "economy")
        self.assertEqual(DEFAULT_INTENTS[TaskClass.ASK_ANSWER].tier, "quality")
        self.assertEqual(DEFAULT_INTENTS[TaskClass.ASK_ANSWER].effort, "high")
        self.assertEqual(DEFAULT_INTENTS[TaskClass.SESSION_REMEMBER].tier, "quality")
        self.assertEqual(DEFAULT_INTENTS[TaskClass.VERIFY].tier, "quality")


class StaticRouterTests(unittest.TestCase):
    def test_returns_the_same_provider_for_every_task(self) -> None:
        from talamus.routing import StaticRouter, TaskClass

        class Fake:
            def complete(self, prompt: str) -> str:
                return "ok"

        fake = Fake()
        router = StaticRouter(fake)
        self.assertIs(router.for_task(TaskClass.EXTRACTION), fake)
        self.assertIs(router.for_task(TaskClass.ASK_ANSWER), fake)

    def test_exposes_the_wrapped_providers_label(self) -> None:
        from talamus.routing import StaticRouter, TaskClass

        class Labeled:
            label = "Fake Engine"

            def complete(self, prompt: str) -> str:
                return "ok"

        router = StaticRouter(Labeled())
        self.assertEqual(router.label, "Fake Engine")
        self.assertIsNotNone(router.for_task(TaskClass.VERIFY))

    def test_defaults_the_label_when_the_provider_has_none(self) -> None:
        from talamus.routing import StaticRouter

        class Bare:
            def complete(self, prompt: str) -> str:
                return "ok"

        self.assertEqual(StaticRouter(Bare()).label, "engine")


class EngineRouterTests(unittest.TestCase):
    def test_resolves_the_code_default_intent_per_task(self) -> None:
        from talamus.config import TalamusConfig
        from talamus.routing import EngineRouter, TaskClass

        router = EngineRouter(TalamusConfig.default())
        provider = router.for_task(TaskClass.EXTRACTION)
        self.assertEqual(provider._model, "haiku")  # economy tier for claude-cli

    def test_ask_answer_resolves_to_the_quality_tier(self) -> None:
        from talamus.config import TalamusConfig
        from talamus.routing import EngineRouter, TaskClass

        router = EngineRouter(TalamusConfig.default())
        provider = router.for_task(TaskClass.ASK_ANSWER)
        self.assertEqual(provider._model, "opus")

    def test_task_tiers_override_wins(self) -> None:
        from dataclasses import replace

        from talamus.config import TalamusConfig
        from talamus.routing import EngineRouter, TaskClass

        config = replace(TalamusConfig.default(), task_tiers={"extraction": {"tier": "quality"}})
        router = EngineRouter(config)
        provider = router.for_task(TaskClass.EXTRACTION)
        self.assertEqual(provider._model, "opus")

    def test_memoizes_providers_sharing_the_same_resolved_engine(self) -> None:
        from talamus.config import TalamusConfig
        from talamus.routing import EngineRouter, TaskClass

        router = EngineRouter(TalamusConfig.default())
        # ASK_ROUTING and QUERY_EXPANSION are both economy/low by default -> same engine
        self.assertIs(
            router.for_task(TaskClass.ASK_ROUTING), router.for_task(TaskClass.QUERY_EXPANSION)
        )

    def test_label_reflects_the_configured_provider(self) -> None:
        from talamus.config import TalamusConfig
        from talamus.routing import EngineRouter

        router = EngineRouter(TalamusConfig.default())
        self.assertEqual(router.label, "Claude CLI")


if __name__ == "__main__":
    unittest.main()
