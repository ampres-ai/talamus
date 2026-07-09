"""Ask the brain a question and get a written, cited answer (the magic moment).

The synthesis lives in core ``talamus.ask.answer_question``; this service wraps it
with engine resolution and a graceful fallback so the bridge/CLI/MCP share one seam.
Retrieval (``search_brain``) is deterministic and always runs, so even with no engine
the caller still gets the most relevant notes — the answer is the only thing that
needs an LLM. Engine failures (unconfigured, missing binary, runtime error) degrade
to the retrieval view instead of raising."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from talamus.ask import answer_from_items, answer_question
from talamus.config import load_or_default
from talamus.errors import EngineFailed, EngineNotFound
from talamus.paths import TalamusPaths
from talamus.recall import search_notes
from talamus.routing import EngineRouter, Router
from talamus.services.query import search_brain
from talamus.services.result import ServiceResult
from talamus.timeline import note_as_of


@dataclass(frozen=True)
class AskSource:
    title: str
    summary: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AskResult:
    question: str
    answer: str  # the synthesized, cited answer ("" when no engine answered)
    answered: bool  # True only when an engine produced the answer
    engine: str  # human label, e.g. "Claude CLI"
    route: str  # how the context was found ("overview"/"index"/"as-of"/…) when answered
    context_tokens: int  # context size fed to the engine when answered
    notice: str  # human note shown when the answer was skipped/degraded
    as_of: str = ""  # the time-travel instant when the answer came from the past
    sources: list[AskSource] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sources"] = [source.to_dict() for source in self.sources]
        return payload


def ask_brain(
    root: str | Path,
    question: str,
    *,
    router: Router | None = None,
    as_of: str | None = None,
) -> ServiceResult[AskResult]:
    paths = TalamusPaths(Path(root))
    text = (question or "").strip()
    if not text:
        return ServiceResult(success=False, message="Ask a question first.", code="ask_empty")

    sources = _retrieve_sources(root, text)

    # EngineRouter(config) never raises: it only stores config. The "no engine"
    # condition is now lazy — build_provider_for_task raises EngineNotFound the first
    # time answer_question actually calls the engine — so both failure modes are caught
    # around the answer_question call below.
    if router is None:
        router = EngineRouter(load_or_default(paths.config_path))
    engine_label = router.label

    if as_of and as_of.strip():
        return _ask_as_of(paths, text, router, as_of.strip(), engine_label, sources)

    trace: dict[str, Any] = {}
    try:
        answer = answer_question(paths, text, router, trace=trace)
    except EngineNotFound:
        return _degraded(
            text,
            sources,
            engine="",
            notice=(
                "No engine connected — showing the most relevant notes. Run "
                "`talamus setup` to connect one and get a written, cited answer."
            ),
            code="ask_no_engine",
        )
    except EngineFailed as exc:
        return _degraded(
            text,
            sources,
            engine=engine_label,
            notice=f"Engine {engine_label} is unavailable ({exc}). Showing relevant notes.",
            code="ask_engine_unavailable",
        )

    return ServiceResult(
        success=True,
        message="Answer ready",
        code="ask_answered",
        data=AskResult(
            question=text,
            answer=answer,
            answered=True,
            engine=engine_label,
            route=str(trace.get("route", "")),
            context_tokens=int(trace.get("context_tokens", 0)),
            notice="",
            sources=sources,
        ),
    )


def _retrieve_sources(root: str | Path, question: str) -> list[AskSource]:
    result = search_brain(root, question, limit=5)
    if not result.success or result.data is None:
        return []
    return [AskSource(title=hit.title, summary=hit.summary) for hit in result.data.hits]


def _ask_as_of(
    paths: TalamusPaths,
    question: str,
    router: Router,
    as_of: str,
    engine_label: str,
    sources: list[AskSource],
) -> ServiceResult[AskResult]:
    """Answer from the brain AS IT WAS at ``as_of`` (the TIME moat, D-priority):
    read each hit's version current at that instant and synthesize only from
    those. Notes that did not exist yet are skipped; if none existed, say so."""
    items: list[dict[str, Any]] = []
    for hit in search_notes(paths, question, limit=5):
        version = note_as_of(paths, hit["title"], as_of)
        if version is None:
            continue  # the note did not exist yet at that time
        body = "\n".join(str(v) for v in version.get("body_sections", {}).values())
        items.append(
            {
                "route": "as-of",
                "path": f"[as-of {as_of}] {hit['title']}",
                "content": f"{version.get('summary', '')}\n{body}",
            }
        )
    if not items:
        notice = f"The brain held nothing relevant as of {as_of}."
        return ServiceResult(
            success=True,
            message=notice,
            code="ask_as_of_empty",
            data=AskResult(
                question=question,
                answer="",
                answered=False,
                engine=engine_label,
                route="as-of",
                context_tokens=0,
                notice=notice,
                as_of=as_of,
                sources=sources,
            ),
        )
    trace: dict[str, Any] = {}
    try:
        answer = answer_from_items(question, items, router, trace=trace)
    except EngineNotFound:
        return _degraded(
            question,
            sources,
            engine="",
            notice=(
                "No engine connected — showing the most relevant notes. Run "
                "`talamus setup` to connect one and get a written, cited answer."
            ),
            code="ask_no_engine",
        )
    except EngineFailed as exc:
        return _degraded(
            question,
            sources,
            engine=engine_label,
            notice=f"Engine {engine_label} is unavailable ({exc}). Showing relevant notes.",
            code="ask_engine_unavailable",
        )
    return ServiceResult(
        success=True,
        message="Answer ready",
        code="ask_answered",
        data=AskResult(
            question=question,
            answer=answer,
            answered=True,
            engine=engine_label,
            route="as-of",
            context_tokens=int(trace.get("context_tokens", 0)),
            notice="",
            as_of=as_of,
            sources=sources,
        ),
    )


def _degraded(
    question: str,
    sources: list[AskSource],
    *,
    engine: str,
    notice: str,
    code: str,
) -> ServiceResult[AskResult]:
    return ServiceResult(
        success=True,
        message=notice,
        code=code,
        data=AskResult(
            question=question,
            answer="",
            answered=False,
            engine=engine,
            route="retrieval",
            context_tokens=0,
            notice=notice,
            sources=sources,
        ),
    )
