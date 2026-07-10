"""Per-task model+effort tiering.

A TaskClass names one point in the pipeline that makes exactly one LLM call. Each task
carries a TaskIntent (tier, effort); an EngineRouter resolves that intent, within the
single provider configured for the brain, into a concrete LLMProvider — never across
providers. Task classes
never know provider-specific model names; providers never know about task classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from talamus.adapters.llm import (
    ENGINE_LABELS,
    LLMProvider,
    build_provider_for_task,
    canonical_provider,
)
from talamus.config import TalamusConfig


class TaskClass(StrEnum):
    EXTRACTION = "extraction"
    SESSION_REMEMBER = "session_remember"
    ASK_ROUTING = "ask_routing"
    QUERY_EXPANSION = "query_expansion"
    ASK_ANSWER = "ask_answer"
    VERIFY = "verify"
    ENRICH = "enrich"
    CONSOLIDATE = "consolidate"
    ONTOLOGY_NAMING = "ontology_naming"
    OVERVIEW_NAMING = "overview_naming"


@dataclass(frozen=True)
class TaskIntent:
    tier: str  # "economy" | "quality"
    effort: str  # "low" | "high"


class Router(Protocol):
    """The interface leaf functions depend on: resolve a TaskClass to a provider.

    Both EngineRouter (real per-task tiering) and StaticRouter (one fixed engine)
    satisfy it structurally, so a leaf annotated ``router: Router`` accepts either —
    production code passes an EngineRouter, tests and single-engine callers a
    StaticRouter, with no leaf-side change."""

    label: str

    def for_task(self, task: TaskClass) -> LLMProvider: ...


DEFAULT_INTENTS: dict[TaskClass, TaskIntent] = {
    TaskClass.EXTRACTION: TaskIntent("economy", "low"),
    TaskClass.SESSION_REMEMBER: TaskIntent("quality", "low"),
    TaskClass.ASK_ROUTING: TaskIntent("economy", "low"),
    TaskClass.QUERY_EXPANSION: TaskIntent("economy", "low"),
    TaskClass.ASK_ANSWER: TaskIntent("quality", "high"),
    TaskClass.VERIFY: TaskIntent("quality", "low"),
    TaskClass.ENRICH: TaskIntent("economy", "low"),
    TaskClass.CONSOLIDATE: TaskIntent("economy", "low"),
    TaskClass.ONTOLOGY_NAMING: TaskIntent("economy", "low"),
    TaskClass.OVERVIEW_NAMING: TaskIntent("economy", "low"),
}


def _resolve_intent(config: TalamusConfig, task: TaskClass) -> TaskIntent:
    override = config.task_tiers.get(task.value)
    if not override:
        return DEFAULT_INTENTS[task]
    default = DEFAULT_INTENTS[task]
    return TaskIntent(override.get("tier", default.tier), override.get("effort", default.effort))


class StaticRouter:
    """A router that returns one fixed provider for every task, ignoring tier/effort.

    Used by tests that inject a single fake LLMProvider (wrap it once instead of
    rewriting every fake to be task-aware) and by any caller that received an explicit
    provider override and wants it honored for every sub-call."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self.label = getattr(provider, "label", "engine")

    def for_task(self, task: TaskClass) -> LLMProvider:
        return self._provider


class EngineRouter:
    """Resolves each TaskClass to a concrete LLMProvider, within the single provider
    configured for the brain (see the design doc's scope note). Built fresh per call
    from a TalamusConfig (no long-lived global state — config changes take effect
    immediately, mirroring the existing build_provider(...) per-call construction).
    Providers are memoized per (tier, effort) so tasks sharing a resolved engine share
    one object."""

    def __init__(self, config: TalamusConfig) -> None:
        self._config = config
        self._provider_name = canonical_provider(config.llm_provider)
        self._cache: dict[tuple[str, str], LLMProvider] = {}
        self.label = ENGINE_LABELS.get(self._provider_name, self._provider_name)

    def for_task(self, task: TaskClass) -> LLMProvider:
        intent = _resolve_intent(self._config, task)
        key = (intent.tier, intent.effort)
        if key not in self._cache:
            self._cache[key] = build_provider_for_task(
                self._provider_name, self._config, intent.tier, intent.effort
            )
        return self._cache[key]
