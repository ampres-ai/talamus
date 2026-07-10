from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from talamus.budget import context_budget, estimate_tokens, fit_to_budget
from talamus.domains import load_overview, load_overview_tree
from talamus.graph import load_graph, query_graph
from talamus.naming import note_filename
from talamus.ontology import load_ontology, neighbors
from talamus.paths import TalamusPaths
from talamus.routing import Router, TaskClass
from talamus.search import BM25Index


@dataclass(frozen=True)
class ContextBundle:
    question: str
    items: list[dict]

    def render(self) -> str:
        lines = [f"Question: {self.question}", ""]
        for idx, item in enumerate(self.items, start=1):
            lines.extend([f"[{idx}] {item['path']} ({item['route']})", item["content"], ""])
        return "\n".join(lines).strip() + "\n"


def _note_path(paths: TalamusPaths, label: str):
    return paths.notes / note_filename(label)


def _expand_with_ontology(seed_titles: list[str], ontology: dict, limit: int) -> list[str]:
    """Fill the candidates by following the ontology relations (1 hop), beyond words.

    TYPED edges come before ``related`` ones: a type promoted by the Ontology Lab
    actually changes what enters the context when the limit cuts."""
    ranked = list(seed_titles)
    for title in seed_titles:
        connected = sorted(
            neighbors(ontology, title),
            key=lambda n: 0 if n.get("relation") != "related" else 1,
        )
        for neighbor in connected:
            if neighbor["title"] not in ranked:
                ranked.append(neighbor["title"])
    return ranked[:limit]


def build_context_bundle(
    paths: TalamusPaths,
    graph: dict,
    search_index: BM25Index,
    question: str,
    limit: int = 5,
    budget_tokens: int | None = None,
) -> ContextBundle:
    from talamus.indexes import postings_path, sqlite_path
    from talamus.indexes import search_index as query_persistent_index

    budget = context_budget(budget_tokens)
    ontology = load_ontology(paths)
    items: list[dict] = []
    if sqlite_path(paths).is_file() or postings_path(paths).is_file():
        # M4 path: seeds from the persistent index, then 1-hop ontology expansion
        seed_titles = [h["title"] for h in query_persistent_index(paths, question, limit=limit)]
        for title in _expand_with_ontology(seed_titles, ontology, limit):
            path = _note_path(paths, title)
            if not path.is_file():
                continue
            route = "index" if title in seed_titles else "graph"
            items.append(
                {"route": route, "path": path.as_posix(), "content": path.read_text("utf-8")}
            )
        return ContextBundle(question=question, items=fit_to_budget(items, budget))

    # legacy path for brains indexed before M4: caller-provided graph + BM25
    seed_titles = [str(node["label"]) for node in query_graph(graph, question, limit=limit)]
    for title in _expand_with_ontology(seed_titles, ontology, limit):
        path = _note_path(paths, title)
        if not path.is_file():
            continue
        items.append(
            {"route": "graph", "path": path.as_posix(), "content": path.read_text(encoding="utf-8")}
        )
    if items:
        return ContextBundle(question=question, items=fit_to_budget(items, budget))

    for result in search_index.search(question, limit=limit):
        path = paths.notes / f"{result['id']}.md"
        if not path.is_file():
            continue
        items.append(
            {"route": "bm25", "path": path.as_posix(), "content": path.read_text(encoding="utf-8")}
        )
    return ContextBundle(question=question, items=fit_to_budget(items, budget))


_ROUTE_PROMPT = """Given the MAP of domains (id | name: description) and a QUESTION, return
ONLY the ids of the relevant domains, comma-separated (e.g. dom-retrieval, dom-time).
No other words.

MAP:
{map}

QUESTION: {question}
"""


def _route_member_titles(
    paths: TalamusPaths,
    question: str,
    router: Router,
    trace: dict | None = None,
) -> list[str]:
    """Route via the domain overview and return the chosen domains' member titles
    (un-ranked, un-sliced). Domains are picked by **stable id** (F3.7/F3.8): the
    LLM answers with ids, parsed and validated against the map — substring
    matching on names survives only as a fallback for pre-id overviews."""
    overview = load_overview(paths)
    if not overview:
        return []
    llm = router.for_task(TaskClass.ASK_ROUTING)
    tree = load_overview_tree(paths)
    if tree:
        # Two-level routing: pick macro-areas first, then only their
        # domains enter the second prompt. Keeps the routing prompt ~log(N)
        # instead of listing every domain (one extra LLM call, big brains only).
        area_map = "\n".join(
            f"- {a.get('id', '?')} | {a.get('name', '')}: {a.get('description', '')}" for a in tree
        )
        area_raw = llm.complete(_ROUTE_PROMPT.format(map=area_map, question=question))
        valid_areas = {str(a["id"]) for a in tree if a.get("id")}
        chosen_areas = [
            token for token in re.findall(r"[a-z0-9-]+", area_raw.lower()) if token in valid_areas
        ]
        if chosen_areas:
            allowed: set[str] = set()
            for area in tree:
                if str(area.get("id", "")) in chosen_areas:
                    allowed.update(str(c) for c in area.get("children", []))
            narrowed = [d for d in overview if str(d.get("id", "")) in allowed]
            if narrowed:
                overview = narrowed
        if trace is not None:
            trace["routing_levels"] = 2
            trace["areas_chosen"] = chosen_areas
    domain_map = "\n".join(
        f"- {d.get('id', '?')} | {d.get('name', '')}: {d.get('description', '')}" for d in overview
    )
    raw = llm.complete(_ROUTE_PROMPT.format(map=domain_map, question=question))
    valid_ids = {str(d["id"]) for d in overview if d.get("id")}
    chosen_ids = [token for token in re.findall(r"[a-z0-9-]+", raw.lower()) if token in valid_ids]
    titles: list[str] = []
    fallback = False
    if chosen_ids:
        for domain in overview:
            if str(domain.get("id", "")) in chosen_ids:
                titles.extend(domain.get("members", []))
    else:  # pre-id overviews or unparseable response: legacy name matching
        fallback = True
        lower = raw.lower()
        for domain in overview:
            name = str(domain.get("name", "")).lower()
            if name and name in lower:
                titles.extend(domain.get("members", []))
    if trace is not None:
        trace["domains_available"] = [str(d.get("id") or d.get("name", "?")) for d in overview]
        trace["domains_chosen"] = chosen_ids
        trace["routing_fallback"] = fallback
    return titles


GLOBAL_ESCAPE_SEEDS = 2  # global hits outside the chosen domains: an anti-misrouting lifeboat


def _select_bundle_titles(
    paths: TalamusPaths, question: str, member_titles: list[str], limit: int
) -> list[tuple[str, str]]:
    """The chosen domains' members are RANKED against the question — before,
    the first ``limit`` were taken in the domain's listing order, and the right note
    could never be read even though it was the top hit of the global search (the
    RLHF/DPO case on the book). Ranking via the persistent index + a couple of
    global out-of-domain seeds. Deterministic, zero LLM calls."""
    from talamus.indexes import search_index

    members = list(dict.fromkeys(member_titles))
    hits = search_index(paths, question, limit=max(24, limit * 3))
    order = {h["title"]: i for i, h in enumerate(hits)}
    ranked = sorted((t for t in members if t in order), key=lambda t: order[t])
    ranked += [t for t in members if t not in order]  # tail: domain order
    member_set = set(members)
    extras = [h["title"] for h in hits if h["title"] not in member_set][:GLOBAL_ESCAPE_SEEDS]
    keep = max(limit - len(extras), 1)
    return [(t, "overview") for t in ranked[:keep]] + [(t, "index") for t in extras]


def _overview_bundle(
    paths: TalamusPaths,
    question: str,
    router: Router,
    limit: int = 8,
    trace: dict | None = None,
) -> ContextBundle:
    titles = _route_member_titles(paths, question, router, trace=trace)
    if not titles:
        return ContextBundle(question=question, items=[])
    # The LLM acts as the embedding model — it translates the question into the
    # corpus vocabulary BEFORE selection. Measured on the book: ask hit 0.861 -> 0.972,
    # vague 0.50 -> 0.81, cross 0.50 -> 0.88. Costs one extra call per ask.
    expanded = _expand_query(question, router)
    ranking_query = f"{question} {expanded}".strip() if expanded != question else question
    if trace is not None:
        trace["expanded_query"] = expanded
    items: list[dict] = []
    for title, route in _select_bundle_titles(paths, ranking_query, titles, limit):
        path = _note_path(paths, title)
        if path.is_file():
            items.append(
                {"route": route, "path": path.as_posix(), "content": path.read_text("utf-8")}
            )
    return ContextBundle(question=question, items=items)


_EXPAND_PROMPT = """Rewrite the question as 3-6 search keywords or technical terms, separated
by spaces. Give the terms BOTH in the question's language AND in English (the index
is bilingual). Return ONLY the terms.

QUESTION: {question}
"""


def _expand_query(question: str, router: Router) -> str:
    llm = router.for_task(TaskClass.QUERY_EXPANSION)
    return llm.complete(_EXPAND_PROMPT.format(question=question)).strip() or question


_ANSWER_PROMPT = """Answer the question using ONLY the context below.
Cite the notes with their bracketed number, e.g. [1].
If the context is not enough, say so explicitly.
ANSWER IN THE SAME LANGUAGE AS THE QUESTION.

QUESTION: {question}

CONTEXT:
{context}
"""


def answer_question(
    paths: TalamusPaths,
    question: str,
    router: Router,
    extra_items: list[dict] | None = None,
    trace: dict | None = None,
) -> str:
    """Answer from the brain. ``extra_items`` lets callers append cross-brain
    context (real note contents with scope markers) before the budget cut.
    Pass a dict as ``trace`` to get the route explained (F3.10): domains, route,
    notes read, context tokens, whether fallbacks fired."""
    bundle = _overview_bundle(paths, question, router, trace=trace)
    route = "overview" if bundle.items else "none"
    if not bundle.items:
        graph = (
            load_graph(paths.graph_file)
            if paths.graph_file.is_file()
            else {"nodes": {}, "edges": []}
        )
        search = BM25Index.load(paths.index_file) if paths.index_file.is_file() else BM25Index()
        bundle = build_context_bundle(paths, graph, search, question)
        if bundle.items:
            route = "index"
        elif not extra_items:
            bundle = build_context_bundle(paths, graph, search, _expand_query(question, router))
            if bundle.items:
                route = "expansion"
    all_items = [*bundle.items, *(extra_items or [])]
    if trace is not None:
        trace["route"] = route
        trace["extra_items"] = len(extra_items or [])
    if not all_items:
        return "No context found in the brain for this question."
    return answer_from_items(question, all_items, router, trace=trace)


def answer_from_items(
    question: str, all_items: list[dict], router: Router, trace: dict | None = None
) -> str:
    """Budget the items, answer with citations, append the Sources legend."""
    items = fit_to_budget(all_items, context_budget())
    if trace is not None:
        trace["items_read"] = [item["path"] for item in items]
        trace["context_tokens"] = sum(estimate_tokens(item["content"]) for item in items)
    context = "\n\n".join(
        f"[{idx}] {item['path']}\n{item['content']}" for idx, item in enumerate(items, start=1)
    )
    llm = router.for_task(TaskClass.ASK_ANSWER)
    answer = llm.complete(_ANSWER_PROMPT.format(question=question, context=context)).strip()
    if not answer:
        return "The engine produced no answer. Try again or check the engine."
    sources = "\n".join(
        f"[{idx}] {Path(item['path']).name}" for idx, item in enumerate(items, start=1)
    )
    return f"{answer}\n\n**Sources:**\n{sources}"
