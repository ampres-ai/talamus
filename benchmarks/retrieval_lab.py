"""Retrieval research lab — hypothesis-driven ablations, no embeddings.

The M0/M4 error analysis showed three dominant failure classes on the real
eval-set: (1) Italian questions vs English-titled notes — zero token overlap;
(2) huge hub notes matching everything; (3) cross-source questions needing
graph structure. Each hypothesis below is an in-memory retriever variant,
measured on the same 120-case harness as production. Winners (and only
winners) get wired into the real index.

Variants:
- V0  baseline: current production behavior (stemmed BM25 + exact boost)
- V1  bilingual stemming (English suffixes stripped too)
- V2  character-trigram title channel (cognate bridge IT<->EN, no embeddings)
- V3  field weighting (title x3, aliases x2 in the haystack)
- V4  graph score propagation (1-hop, decayed, over typed edges)
- V5+ combinations of the above
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable

from talamus.models import CanonicalNote
from talamus.ontology import load_ontology
from talamus.paths import TalamusPaths
from talamus.store import load_notes
from talamus.textutil import tokens as tokens_it

Retriever = Callable[[str, int], list[str]]

_WORD = re.compile(r"[a-zà-ÿ0-9]+")

# light English suffix strip, mirroring the Italian stemmer's philosophy
_EN_SUFFIXES = (
    "ations", "ation", "ings", "ements", "ement", "ities", "ity",
    "ables", "able", "ing", "ed", "es", "s", "ly", "al", "ive",
)  # fmt: skip
_MIN_STEM = 4


def tokens_bilingual(text: str) -> list[str]:
    """Italian stemming first; surviving tokens also lose English suffixes."""
    result = []
    for token in tokens_it(text):
        for suffix in _EN_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= _MIN_STEM:
                token = token[: -len(suffix)]
                break
        result.append(token)
    return result


def trigrams(text: str) -> set[str]:
    """Character 3-grams of the normalized words — the cognate bridge."""
    grams: set[str] = set()
    for word in _WORD.findall(text.lower()):
        if len(word) < 3:
            continue
        for i in range(len(word) - 2):
            grams.add(word[i : i + 3])
    return grams


def _dice(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


class MemoryIndex:
    """In-memory BM25 for fast ablations (the corpus is small in experiments)."""

    def __init__(
        self,
        notes: list[CanonicalNote],
        tokenizer: Callable[[str], list[str]],
        title_weight: int = 1,
        alias_weight: int = 1,
    ) -> None:
        self.tokenizer = tokenizer
        self.notes = {note.title: note for note in notes}
        self.docs: dict[str, Counter[str]] = {}
        self.lengths: dict[str, int] = {}
        self.df: Counter[str] = Counter()
        self.title_tri: dict[str, set[str]] = {}
        for note in notes:
            haystack = " ".join(
                [
                    *([note.title] * title_weight),
                    *([" ".join(note.aliases)] * alias_weight),
                    " ".join(note.tags),
                    note.retrieval_text,
                    note.summary,
                ]
            )
            counts = Counter(tokenizer(haystack))
            self.docs[note.title] = counts
            self.lengths[note.title] = sum(counts.values())
            for term in counts:
                self.df[term] += 1
            self.title_tri[note.title] = trigrams(f"{note.title} {' '.join(note.aliases)}")

    def bm25(self, query: str) -> dict[str, float]:
        terms = self.tokenizer(query)
        if not self.docs:
            return {}
        avgdl = sum(self.lengths.values()) / len(self.lengths)
        scores: dict[str, float] = {}
        n = len(self.docs)
        for title, counts in self.docs.items():
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                df = self.df.get(term, 1)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                denom = tf + 1.5 * (1 - 0.75 + 0.75 * self.lengths[title] / avgdl)
                score += idf * tf * 2.5 / denom
            if score > 0:
                scores[title] = score
        return scores

    def trigram_scores(self, query: str) -> dict[str, float]:
        query_tri = trigrams(query)
        return {
            title: dice
            for title, grams in self.title_tri.items()
            if (dice := _dice(query_tri, grams)) > 0
        }


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    top = max(scores.values(), default=0.0)
    if top <= 0:
        return {}
    return {k: v / top for k, v in scores.items()}


def make_variant(
    paths: TalamusPaths,
    bilingual: bool = False,
    trigram_weight: float = 0.0,
    title_weight: int = 1,
    alias_weight: int = 1,
    propagation: float = 0.0,
) -> Retriever:
    """Compose a retriever variant from the hypothesis knobs."""
    notes = load_notes(paths)
    tokenizer = tokens_bilingual if bilingual else tokens_it
    index = MemoryIndex(notes, tokenizer, title_weight, alias_weight)
    neighbors_map: dict[str, list[str]] = {}
    if propagation > 0:
        for edge in load_ontology(paths).get("edges", []):
            neighbors_map.setdefault(str(edge["source"]), []).append(str(edge["target"]))
            neighbors_map.setdefault(str(edge["target"]), []).append(str(edge["source"]))

    def run(question: str, k: int) -> list[str]:
        scores = _normalize(index.bm25(question))
        if trigram_weight > 0:
            for title, dice in _normalize(index.trigram_scores(question)).items():
                scores[title] = scores.get(title, 0.0) + trigram_weight * dice
        if propagation > 0 and scores:
            spread: dict[str, float] = {}
            for title, score in scores.items():
                for neighbor in neighbors_map.get(title, []):
                    spread[neighbor] = max(spread.get(neighbor, 0.0), propagation * score)
            for title, bonus in spread.items():
                scores[title] = scores.get(title, 0.0) + bonus
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return [title for title, _ in ranked[:k]]

    return run


VARIANTS: dict[str, dict] = {
    "V0-baseline": {},
    "V1-bilingual": {"bilingual": True},
    "V2-trigram": {"trigram_weight": 0.8},
    "V3-fields": {"title_weight": 3, "alias_weight": 2},
    "V4-propagation": {"propagation": 0.4},
    "V12": {"bilingual": True, "trigram_weight": 0.8},
    "V123": {"bilingual": True, "trigram_weight": 0.8, "title_weight": 3, "alias_weight": 2},
    "V1234": {
        "bilingual": True,
        "trigram_weight": 0.8,
        "title_weight": 3,
        "alias_weight": 2,
        "propagation": 0.4,
    },
}


def run_ablations(paths: TalamusPaths, cases_file, k: int = 5) -> dict[str, dict]:
    """Evaluate every variant on the real eval-set. Returns per-variant metrics."""
    from talamus.eval import evaluate, load_cases

    cases = load_cases(cases_file)
    results: dict[str, dict] = {}
    for name, knobs in VARIANTS.items():
        retriever = make_variant(paths, **knobs)
        report = evaluate(cases, retriever, k=k)
        results[name] = {
            "recall_at_k": round(report.recall_at_k, 4),
            "mrr": round(report.mrr, 4),
            "hit_rate": round(report.hit_rate, 4),
            "categories": {cat: stats["recall_at_k"] for cat, stats in report.categories.items()},
        }
    return results


# --- Ablation: the ask bundle expands 1 hop via the ontology, but at full limit the
# expansion is a no-op (the seeds already fill the cut). Measurable question:
# "does expanding via typed edges beat simply taking more search hits?"


def make_bundle_variant(
    paths: TalamusPaths,
    seed_k: int = 5,
    expand: bool = False,
    typed_only: bool = False,
    typed_first: bool = True,
) -> Retriever:
    """Bundle-path variant: seeds from the persistent index, then 1-hop ontology
    expansion up to k. All deterministic, zero LLM."""
    from talamus.indexes import search_index
    from talamus.ontology import neighbors as onto_neighbors

    ontology = load_ontology(paths)

    def run(question: str, k: int) -> list[str]:
        seeds = [h["title"] for h in search_index(paths, question, limit=min(seed_k, k))]
        ranked = list(seeds)
        if expand:
            for title in seeds:
                connected = onto_neighbors(ontology, title)
                if typed_first:
                    connected = sorted(
                        connected, key=lambda n: 0 if n.get("relation") != "related" else 1
                    )
                for neighbor in connected:
                    if typed_only and neighbor.get("relation") == "related":
                        continue
                    if neighbor["title"] not in ranked:
                        ranked.append(neighbor["title"])
        return ranked[:k]

    return run


BUNDLE_VARIANTS: dict[str, dict] = {
    "B-seeds-only": {"seed_k": 99},  # search only: the first k hits
    "B-seeds3+exp": {"seed_k": 3, "expand": True},
    "B-seeds3+exp-typed": {"seed_k": 3, "expand": True, "typed_only": True},
    "B-seeds3+exp-flat": {"seed_k": 3, "expand": True, "typed_first": False},
    "B-seeds4+exp": {"seed_k": 4, "expand": True},
}


def run_bundle_ablations(paths: TalamusPaths, cases_file, k: int = 5) -> dict[str, dict]:
    """Compare the bundle variants on the same retriever harness."""
    from talamus.eval import evaluate, load_cases

    cases = load_cases(cases_file)
    results: dict[str, dict] = {}
    for name, knobs in BUNDLE_VARIANTS.items():
        retriever = make_bundle_variant(paths, **knobs)
        report = evaluate(cases, retriever, k=k)
        results[name] = {
            "recall_at_k": round(report.recall_at_k, 4),
            "mrr": round(report.mrr, 4),
            "hit_rate": round(report.hit_rate, 4),
            "categories": {cat: stats["recall_at_k"] for cat, stats in report.categories.items()},
        }
    return results


# --- Ablation: TRIANGULATION. The previous rejects (score propagation, 1-hop
# expansion) pushed the neighbors of the single top hit -> hub pollution. Here a
# node emerges only if SEVERAL weak, independent hits converge on it via edges:
# the vague question describes a situation BETWEEN concepts, and the agreement of
# multiple signals is the filter against hubs.


def make_triangulation_variant(
    paths: TalamusPaths,
    base_k: int = 10,
    boost: float = 0.4,
    min_converge: int = 2,
    typed_only: bool = False,
) -> Retriever:
    notes = load_notes(paths)
    index = MemoryIndex(notes, tokens_bilingual, title_weight=3, alias_weight=2)
    adjacency: dict[str, set[str]] = {}
    for edge in load_ontology(paths).get("edges", []):
        if typed_only and edge.get("type") == "related":
            continue
        adjacency.setdefault(str(edge["source"]), set()).add(str(edge["target"]))
        adjacency.setdefault(str(edge["target"]), set()).add(str(edge["source"]))

    def run(question: str, k: int) -> list[str]:
        scores = _normalize(index.bm25(question))
        for title, dice in _normalize(index.trigram_scores(question)).items():
            scores[title] = scores.get(title, 0.0) + 0.8 * dice
        ranked = sorted(scores.items(), key=lambda i: (-i[1], i[0]))[:base_k]
        hits = dict(ranked)
        votes: dict[str, list[float]] = {}
        for title, score in hits.items():
            for neighbor in adjacency.get(title, ()):  # the votes come from the hits
                votes.setdefault(neighbor, []).append(score)
        final = dict(hits)
        for node, supporters in votes.items():
            if len(supporters) < min_converge:
                continue  # a single signal = propagation, already rejected
            final[node] = final.get(node, 0.0) + boost * sum(supporters) / len(supporters) * len(
                supporters
            )
        ordered = sorted(final.items(), key=lambda i: (-i[1], i[0]))
        return [t for t, _ in ordered[:k]]

    return run


TRIANGULATION_VARIANTS: dict[str, dict] = {
    "T-base": {"boost": 0.0},  # reference: same scorer, no triangulation
    "T-all-0.3": {"boost": 0.3},
    "T-all-0.5": {"boost": 0.5},
    "T-typed-0.3": {"boost": 0.3, "typed_only": True},
    "T-typed-0.5": {"boost": 0.5, "typed_only": True},
    "T-conv3-0.5": {"boost": 0.5, "min_converge": 3},
}


def run_triangulation_ablations(paths: TalamusPaths, cases_file, k: int = 5) -> dict[str, dict]:
    from talamus.eval import evaluate, load_cases

    cases = load_cases(cases_file)
    results: dict[str, dict] = {}
    for name, knobs in TRIANGULATION_VARIANTS.items():
        report = evaluate(cases, make_triangulation_variant(paths, **knobs), k=k)
        results[name] = {
            "recall_at_k": round(report.recall_at_k, 4),
            "mrr": round(report.mrr, 4),
            "hit_rate": round(report.hit_rate, 4),
            "categories": {cat: stats["recall_at_k"] for cat, stats in report.categories.items()},
        }
    return results


# --- Ablation: rejecting negatives. The blended scores are normalized per query
# (the absolute does not separate), but WHICH channels light up does: an
# out-of-domain query does not light the stemmed lexical channel, only trigram noise.


# IT+EN function words (post-tokenizer stems): NOT semantics, pure grammar.
# Needed because in an Italian-prose corpus "what/is/of" are out of vocabulary
# and sink the coverage of legitimate English questions (failure class 2).
_FUNCTION_STEMS = frozenset(
    """come cosa cos qual quale quali quando dove perche chi che con per tra fra
    una uno della dello delle degli nella nelle sono stato fare faccio puo posso
    voglio devo meglio piu meno molto poco tutto ogni questo quello senza dopo
    prima anche ancora gia mai sempre
    what when where which who why how does did doe can could should would want
    need make get use using used keep keeps there their them they this that
    these those with without from into onto about have has had will shall
    other another same different""".split()
)


def rejection_report(paths: TalamusPaths, cases_file) -> dict:
    """Negative-rejection ablation, iteration 3. The top lexical hit does not separate (vocabulary
    overlap); coverage over ALL informative tokens does not either (English
    function words are OOV in an Italian corpus). Candidate: coverage of CONTENT
    terms only — 'carbonara' df=0 vs 'mixture' df>0."""
    from talamus.eval import load_cases

    notes = load_notes(paths)
    index = MemoryIndex(notes, tokens_bilingual, title_weight=3, alias_weight=2)
    n_docs = max(len(index.docs), 1)
    ubiquity_cap = 0.3 * n_docs  # a token in >30% of docs = effectively functional

    rows: list[dict] = []
    for case in load_cases(cases_file):
        content = [
            t
            for t in set(tokens_bilingual(case.question))
            if t not in _FUNCTION_STEMS and index.df.get(t, 0) < ubiquity_cap
        ]
        known = [t for t in content if index.df.get(t, 0) > 0]
        coverage = len(known) / len(content) if content else 1.0
        rows.append(
            {
                "question": case.question,
                "negative": case.negative,
                "coverage": round(coverage, 3),
                "unknown_terms": sorted(set(content) - set(known)),
            }
        )
    negatives = [r for r in rows if r["negative"]]
    sweep: list[dict] = []
    for tau in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        rejected = [r for r in rows if r["coverage"] < tau]
        sweep.append(
            {
                "coverage<": tau,
                "neg_rejected": f"{len([r for r in rejected if r['negative']])}/{len(negatives)}",
                "false_rejects": [r["question"] for r in rejected if not r["negative"]],
            }
        )
    return {"rows": rows, "sweep": sweep}
