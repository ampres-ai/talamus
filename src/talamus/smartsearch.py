"""Smart search: Query2doc-style LLM query expansion in front of lexical search.

The 2026-06 ablation rounds measured a
hard ceiling for lexical+trigram+symptom search (~0.86-0.89 on a curated
brain): the remaining misses are pure vocabulary-mismatch vague queries that no
lexical trick bridges. The literature's proven no-embedding cure is Query2doc
(Wang et al. 2023): expand the query with the user's own LLM before searching.

Measured on both corpora: book hit 0.861 → 0.972, docs hit 0.618 → 0.782 — it
breaks the ceiling on the very category (vague) that caused it. Cost: one LLM
call per UNIQUE query, cached on disk so repeated queries are free. This is the
"the LLM is the embedding model" thesis applied to search, and it stays
embedding-free and infra-free — the engine is the one the user already pays for.
"""

from __future__ import annotations

import json

from talamus.ask import _EXPAND_PROMPT
from talamus.errors import EngineFailed, EngineNotFound
from talamus.paths import TalamusPaths
from talamus.routing import Router, TaskClass


def _cache_path(paths: TalamusPaths):
    return paths.cache / "expansions.json"


def _load_cache(paths: TalamusPaths) -> dict[str, str]:
    path = _cache_path(paths)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_cache(paths: TalamusPaths, cache: dict[str, str]) -> None:
    paths.cache.mkdir(parents=True, exist_ok=True)
    _cache_path(paths).write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def expand_query(paths: TalamusPaths, question: str, router: Router) -> str:
    """Return the question augmented with LLM-predicted terms, cached on disk.

    The expansion depends only on the question (not the brain), so caching by
    the normalized question is safe and makes repeated queries free. On any
    engine failure we degrade to the original question — smart search must never
    be worse than plain search."""
    key = " ".join(question.split()).lower()
    if not key:
        return question
    cache = _load_cache(paths)
    if key in cache:
        expanded = cache[key]
    else:
        try:
            llm = router.for_task(TaskClass.QUERY_EXPANSION)
            expanded = llm.complete(_EXPAND_PROMPT.format(question=question)).strip()
        except (EngineFailed, EngineNotFound):
            return question
        cache[key] = expanded
        _save_cache(paths, cache)
    return f"{question} {expanded}".strip() if expanded else question


def expand_query_multi(paths: TalamusPaths, question: str, router: Router, passes: int = 1) -> str:
    """N-pass expansion union to smooth the nondeterministic LLM expansion
    (measured run-to-run swings of ~0.06 hit). ``passes <= 1`` is the cached
    single-pass path. Extra passes are uncached (each is a fresh sample) and their
    unique terms are unioned onto the question; any engine failure is skipped so
    the result is never worse than the question itself. For a deterministic engine
    (e.g. ollama at temperature 0) one pass already reproduces — multi-pass is for
    sampling engines where a small union reduces variance."""
    if passes <= 1:
        return expand_query(paths, question, router)
    terms = question.split()
    seen = {t.lower() for t in terms}
    llm = router.for_task(TaskClass.QUERY_EXPANSION)
    for _ in range(passes):
        try:
            expansion = llm.complete(_EXPAND_PROMPT.format(question=question)).strip()
        except (EngineFailed, EngineNotFound):
            continue
        for token in expansion.split():
            if token.lower() not in seen:
                seen.add(token.lower())
                terms.append(token)
    return " ".join(terms)
