"""Domain induction (hybrid): structural clusters from the typed graph, then the LLM
names and refines them into thematic domains that cover every note.

The structural pass groups notes connected by typed relations; the LLM pass turns
those clusters into named domains and assigns the strays. The result is the
**overview**: a small, ~constant-size map the LLM can route over.
"""

from __future__ import annotations

import json
import re

from talamus.adapters.llm import LLMProvider
from talamus.models import CanonicalNote
from talamus.ontology import load_ontology, neighbors
from talamus.paths import TalamusPaths
from talamus.store import load_notes

_PROMPT = """Sei un bibliotecario. Le SCHEDE sono pre-raggruppate per connessioni (CLUSTER).
Trasformale in DOMINI tematici chiari che coprano TUTTE le schede.
- Dai a ogni dominio un nome breve e una descrizione di una frase.
- Assegna ogni scheda a UN SOLO dominio (puoi unire cluster piccoli o spostare una
  scheda in un altro dominio se tematicamente sta meglio).
- Ogni scheda deve finire in esattamente un dominio.

Restituisci SOLO un array JSON:
[{"name": "<nome>", "description": "<una frase>", "members": ["<titolo>", "<titolo>"]}]

CLUSTER (connessioni esistenti):
<CLUSTERS>

SCHEDE (titolo: riassunto):
<SUMMARIES>
"""


def _structural_clusters(notes: list[CanonicalNote], ontology: dict) -> list[list[str]]:
    titles = [note.title for note in notes]
    title_set = set(titles)
    parent: dict[str, str] = {title: title for title in titles}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for title in titles:
        for neighbor in neighbors(ontology, title):
            other = str(neighbor.get("title", ""))
            if other in title_set:
                union(title, other)

    clusters: dict[str, list[str]] = {}
    for title in titles:
        clusters.setdefault(find(title), []).append(title)
    return list(clusters.values())


def _name_domains(
    clusters: list[list[str]], summaries: dict[str, str], llm: LLMProvider
) -> list[dict]:
    cluster_text = "\n".join(f"- {', '.join(cluster)}" for cluster in clusters)
    summary_text = "\n".join(f"- {title}: {summary}" for title, summary in summaries.items())
    raw = llm.complete(
        _PROMPT.replace("<CLUSTERS>", cluster_text).replace("<SUMMARIES>", summary_text)
    )
    start, end = raw.find("["), raw.rfind("]")
    parsed: list = []
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            parsed = []

    domains: list[dict] = []
    assigned: set[str] = set()
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        members = [m for m in entry.get("members", []) if m in summaries and m not in assigned]
        if not members:
            continue
        assigned.update(members)
        domains.append(
            {
                "name": str(entry.get("name", "")).strip() or "Dominio",
                "description": str(entry.get("description", "")).strip(),
                "members": members,
            }
        )

    leftover = [title for title in summaries if title not in assigned]
    if leftover:
        domains.append(
            {"name": "Varie", "description": "Schede non ancora classificate.", "members": leftover}
        )
    return domains


def build_overview(paths: TalamusPaths, llm: LLMProvider) -> list[dict]:
    """Induce the domains and persist the overview. Returns the domain list."""
    notes = load_notes(paths)
    if not notes:
        return []
    clusters = _structural_clusters(notes, load_ontology(paths))
    summaries = {note.title: note.summary for note in notes}
    domains = _name_domains(clusters, summaries, llm)
    save_overview(paths, domains)
    return domains


def _domain_id(name: str, taken: set[str]) -> str:
    base = "dom-" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "x")
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def save_overview(paths: TalamusPaths, domains: list[dict]) -> None:
    """Persist the overview, ensuring every domain carries a stable ``id`` (F3.8)
    separate from its human name — routing talks ids, never substring-matched names."""
    taken: set[str] = {str(d["id"]) for d in domains if d.get("id")}
    for domain in domains:
        if not domain.get("id"):
            domain["id"] = _domain_id(str(domain.get("name", "")), taken)
            taken.add(domain["id"])
    paths.cache.mkdir(parents=True, exist_ok=True)
    paths.overview_file.write_text(
        json.dumps(domains, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_overview(paths: TalamusPaths) -> list[dict]:
    if not paths.overview_file.is_file():
        return []
    return json.loads(paths.overview_file.read_text(encoding="utf-8"))
