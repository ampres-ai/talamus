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

_PROMPT = """You are a librarian. The NOTES are pre-grouped by connections (CLUSTERS).
Turn them into clear thematic DOMAINS covering ALL the notes.
- Give each domain a short name and a one-sentence description, in <LANGUAGE>.
- Assign each note to EXACTLY ONE domain (you may merge small clusters, or move a
  note to a different domain if it fits better thematically).
- Every note must end up in exactly one domain.

Return ONLY a JSON array:
[{"name": "<name>", "description": "<one sentence>", "members": ["<title>", "<title>"]}]

CLUSTERS (existing connections):
<CLUSTERS>

NOTES (title: summary):
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


def _parse_json_array(raw: str) -> list:
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _domains_from_llm(
    clusters: list[list[str]],
    summaries: dict[str, str],
    llm: LLMProvider,
    language: str,
) -> tuple[list[dict], set[str]]:
    """One full-partition call (the original path). Returns (domains, assigned)."""
    cluster_text = "\n".join(f"- {', '.join(cluster)}" for cluster in clusters)
    summary_text = "\n".join(f"- {title}: {summary}" for title, summary in summaries.items())
    raw = llm.complete(
        _PROMPT.replace("<CLUSTERS>", cluster_text)
        .replace("<SUMMARIES>", summary_text)
        .replace("<LANGUAGE>", language)
    )
    domains: list[dict] = []
    assigned: set[str] = set()
    for entry in _parse_json_array(raw):
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
    return domains, assigned


def _name_domains(
    clusters: list[list[str]],
    summaries: dict[str, str],
    llm: LLMProvider,
    language: str = "English",
) -> list[dict]:
    domains, assigned = _domains_from_llm(clusters, summaries, llm, language)
    leftover = [title for title in summaries if title not in assigned]
    if leftover:
        domains.append(
            {"name": "Varie", "description": "Schede non ancora classificate.", "members": leftover}
        )
    return domains


# --- scala libro: il prompt unico che ri-echeggia centinaia di titoli esatti si
# rompe (trovato sul run reale di "AI Engineering", 243 note -> tutto in Varie).
# Sopra BATCH_NOTES_THRESHOLD l'induzione lavora a chiamate LIMITATE:
# cluster giganti -> split dedicato; cluster medi -> naming che echeggia solo un
# indice numerico; randagi -> assegnazione a lotti contro i domini gia' nominati.

BATCH_NOTES_THRESHOLD = 60
SPLIT_CLUSTER_THRESHOLD = 25
MIN_NAMED_CLUSTER = 3
STRAY_BATCH = 40

_CLUSTER_NAME_PROMPT = """You are a librarian. For each CLUSTER of connected notes,
produce a short thematic domain name and a one-sentence description, in <LANGUAGE>.
Return ONLY a JSON array, one entry per cluster, echoing the cluster number:
[{"cluster": <number>, "name": "<short name>", "description": "<one sentence>"}]

CLUSTERS:
<CLUSTERS>
"""

_ASSIGN_PROMPT = """You are a librarian. Assign each NOTE to exactly one of the DOMAINS.
Return ONLY a JSON array: [{"title": "<note title>", "domain": "<domain name>"}]

DOMAINS:
<DOMAINS>

NOTES (title: summary):
<NOTES>
"""


def _name_domains_batched(
    clusters: list[list[str]],
    summaries: dict[str, str],
    llm: LLMProvider,
    language: str = "English",
) -> list[dict]:
    big = [c for c in clusters if len(c) >= SPLIT_CLUSTER_THRESHOLD]
    mid = [c for c in clusters if MIN_NAMED_CLUSTER <= len(c) < SPLIT_CLUSTER_THRESHOLD]
    strays = [t for c in clusters if len(c) < MIN_NAMED_CLUSTER for t in c]
    domains: list[dict] = []

    # 1) cluster giganti: partizione tematica dedicata (eco limitato al cluster)
    for cluster in big:
        sub = {t: summaries.get(t, "") for t in cluster}
        split_domains, assigned = _domains_from_llm([cluster], sub, llm, language)
        domains.extend(split_domains)
        strays.extend(t for t in cluster if t not in assigned)

    # 2) cluster medi: una chiamata che echeggia solo l'indice del cluster
    if mid:
        lines = []
        for i, cluster in enumerate(mid):
            sample = "; ".join(cluster[:8])
            extra = f" (+{len(cluster) - 8} altre)" if len(cluster) > 8 else ""
            lines.append(f"Cluster {i}: {sample}{extra}")
        raw = llm.complete(
            _CLUSTER_NAME_PROMPT.replace("<CLUSTERS>", "\n".join(lines)).replace(
                "<LANGUAGE>", language
            )
        )
        named: dict[int, dict] = {}
        for entry in _parse_json_array(raw):
            if isinstance(entry, dict) and isinstance(entry.get("cluster"), int):
                named[entry["cluster"]] = entry
        for i, cluster in enumerate(mid):
            entry = named.get(i, {})
            domains.append(
                {
                    # fallback deterministico: il primo titolo fa da nome
                    "name": str(entry.get("name", "")).strip() or cluster[0],
                    "description": str(entry.get("description", "")).strip(),
                    "members": list(cluster),
                }
            )

    # 3) randagi: assegnazione a lotti contro i domini esistenti
    leftover: list[str] = []
    if strays and domains:
        domain_lines = "\n".join(f"- {d['name']}: {d['description']}" for d in domains)
        by_name = {str(d["name"]): d for d in domains}
        for offset in range(0, len(strays), STRAY_BATCH):
            batch = strays[offset : offset + STRAY_BATCH]
            note_lines = "\n".join(f"- {t}: {summaries.get(t, '')}" for t in batch)
            raw = llm.complete(
                _ASSIGN_PROMPT.replace("<DOMAINS>", domain_lines)
                .replace("<NOTES>", note_lines)
                .replace("<LANGUAGE>", language)
            )
            placed: dict[str, str] = {}
            for entry in _parse_json_array(raw):
                if isinstance(entry, dict):
                    placed[str(entry.get("title", ""))] = str(entry.get("domain", ""))
            for title in batch:
                target = by_name.get(placed.get(title, ""))
                if target is not None:
                    target["members"].append(title)
                else:
                    leftover.append(title)
    else:
        leftover = strays

    if leftover:
        domains.append(
            {"name": "Varie", "description": "Schede non ancora classificate.", "members": leftover}
        )
    return domains


def build_overview(paths: TalamusPaths, llm: LLMProvider) -> list[dict]:
    """Induce the domains and persist the overview. Returns the domain list."""
    from talamus.config import load_or_default, resolve_language

    notes = load_notes(paths)
    if not notes:
        return []
    clusters = _structural_clusters(notes, load_ontology(paths))
    summaries = {note.title: note.summary for note in notes}
    language = resolve_language(load_or_default(paths.config_path))
    namer = _name_domains_batched if len(notes) > BATCH_NOTES_THRESHOLD else _name_domains
    domains = namer(clusters, summaries, llm, language=language)
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


# ---------------------------------------------------------- hierarchical tree

TREE_THRESHOLD = 12  # below this many domains, flat routing is already cheap

_TREE_PROMPT = """You are a librarian. Group the DOMAINS into 3-9 thematic MACRO-AREAS.
Every domain must belong to exactly one macro-area. Name and describe each area in
<LANGUAGE>. Return ONLY a JSON array:
[{"name": "<short name>", "description": "<one sentence>", "children": ["<domain id>", ...]}]

DOMAINS (id | name: description):
<DOMAINS>
"""


def tree_path(paths: TalamusPaths):
    return paths.cache / "overview-tree.json"


def build_overview_tree(paths: TalamusPaths, llm: LLMProvider) -> list[dict]:
    """Second overview level (Fase R5): macro-areas over the domains, so routing
    cost stays ~log(N) instead of growing linearly with the domain count.
    One extra LLM call, only when the flat map is big enough to need it."""
    overview = load_overview(paths)
    if len(overview) < TREE_THRESHOLD:
        tree_path(paths).unlink(missing_ok=True)
        return []
    from talamus.config import load_or_default, resolve_language

    domain_lines = "\n".join(
        f"- {d.get('id', '?')} | {d.get('name', '')}: {d.get('description', '')}" for d in overview
    )
    language = resolve_language(load_or_default(paths.config_path))
    raw = llm.complete(
        _TREE_PROMPT.replace("<DOMAINS>", domain_lines).replace("<LANGUAGE>", language)
    )
    start, end = raw.find("["), raw.rfind("]")
    parsed: list = []
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            parsed = []
    valid_ids = {str(d["id"]) for d in overview if d.get("id")}
    areas: list[dict] = []
    assigned: set[str] = set()
    taken: set[str] = set()
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        children = [c for c in entry.get("children", []) if c in valid_ids and c not in assigned]
        if not children:
            continue
        assigned.update(children)
        slug = re.sub(r"[^a-z0-9]+", "-", str(entry.get("name", "")).lower()).strip("-") or "x"
        area_id = f"area-{slug}"
        suffix = 2
        while area_id in taken:
            area_id = f"area-{slug}-{suffix}"
            suffix += 1
        taken.add(area_id)
        areas.append(
            {
                "id": area_id,
                "name": str(entry.get("name", "")).strip() or "Area",
                "description": str(entry.get("description", "")).strip(),
                "children": children,
            }
        )
    leftover = [str(d["id"]) for d in overview if d.get("id") and d["id"] not in assigned]
    if leftover:
        altro_id = "area-altro"
        suffix = 2
        while altro_id in taken:
            altro_id = f"area-altro-{suffix}"
            suffix += 1
        areas.append(
            {
                "id": altro_id,
                "name": "Altro",
                "description": "Domini non ancora raggruppati.",
                "children": leftover,
            }
        )
    paths.cache.mkdir(parents=True, exist_ok=True)
    tree_path(paths).write_text(json.dumps(areas, indent=2, ensure_ascii=False), encoding="utf-8")
    return areas


def load_overview_tree(paths: TalamusPaths) -> list[dict]:
    path = tree_path(paths)
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
