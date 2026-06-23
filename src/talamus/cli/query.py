from __future__ import annotations

import json
import sys
from pathlib import Path

from talamus.adapters.llm import LLMProvider
from talamus.ask import answer_from_items, answer_question
from talamus.cli._common import (
    _print_json,
    _provider_for,
)
from talamus.eval import evaluate, load_cases, search_retriever
from talamus.ingest import remember_session
from talamus.paths import TalamusPaths
from talamus.recall import search_notes
from talamus.registry import (
    central_brain,
)
from talamus.relations import list_relations, prune_relations
from talamus.scope import (
    default_scope,
    scoped_context_items,
)
from talamus.services.graph import list_graph_neighbors
from talamus.services.query import read_note, recall_brain, search_brain
from talamus.temporal import note_timeline, parse_when
from talamus.timeline import note_as_of, note_history


def _cmd_ask(
    root: Path,
    question: str,
    llm: LLMProvider,
    json_out: bool,
    policy: str | None = None,
    with_trace: bool = False,
    as_of: str | None = None,
) -> int:
    policy = policy or default_scope(root)
    trace: dict | None = {"scope": policy} if with_trace else None
    if as_of:
        when = parse_when(as_of)
        if trace is not None and when.warning:
            trace["as_of_warning"] = when.warning
        paths = TalamusPaths(root)
        items: list[dict] = []
        for hit in search_notes(paths, question, limit=5):
            version = note_as_of(paths, hit["title"], as_of)
            if version is None:
                continue  # the note did not exist yet at that time
            joiner = chr(10)
            body = joiner.join(str(v) for v in version.get("body_sections", {}).values())
            items.append(
                {
                    "route": "as-of",
                    "path": f"[as-of {as_of}] {hit['title']}",
                    "content": f"{version.get('summary', '')}{joiner}{body}",
                }
            )
        if not items:
            print(f"no knowledge in the brain as of {as_of}")
            return 0
        answer = answer_from_items(question, items, llm, trace=trace)
        if json_out:
            temporal_payload: dict = {
                "answer": answer,
                "scope": policy,
                "as_of": when.instant_utc,
            }
            if trace is not None:
                temporal_payload["trace"] = trace
            _print_json(temporal_payload)
            return 0
        print(answer)
        return 0
    if policy == "central-only":
        central = central_brain()
        if central is None:
            print("no central brain registered (run `talamus init --global`)", file=sys.stderr)
            return 1
        answer = answer_question(TalamusPaths(central.root()), question, llm, trace=trace)
    else:
        extra: list[dict] = []
        if policy == "project+central":
            extra, _ = scoped_context_items(
                root, question, "central-only", limit=5, exclude_roots=[root]
            )
        elif policy == "all":
            extra, _ = scoped_context_items(root, question, "all", limit=5, exclude_roots=[root])
        answer = answer_question(TalamusPaths(root), question, llm, extra_items=extra, trace=trace)
    if json_out:
        payload: dict = {"answer": answer, "scope": policy}
        if trace is not None:
            payload["trace"] = trace
        _print_json(payload)
        return 0
    print(answer)
    if trace is not None:
        print("--- trace ---", file=sys.stderr)
        print(json.dumps(trace, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0


def _cmd_eval_scale(sizes_arg: str | None, json_out: bool) -> int:
    from talamus.bench import run_scale

    sizes = [int(s) for s in (sizes_arg or "100,1000,10000").split(",") if s.strip()]
    rows = run_scale(sizes)
    if json_out:
        _print_json(rows)
        return 0
    print("| notes | search p50 (ms) | search p95 (ms) | backend | bytes |")
    for row in rows:
        print(
            f"| {row['n_notes']} | {row['search']['p50_ms']} | {row['search']['p95_ms']}"
            f" | {row['index']['backend']} | {row['index']['bytes']:,} |"
        )
    return 0


def _cmd_eval(
    root: Path, cases_file: str, k: int, json_out: bool, category: str | None = None
) -> int:
    path = Path(cases_file)
    if not path.is_file():
        print(f"cases file not found: {cases_file}", file=sys.stderr)
        return 1
    cases = load_cases(path, category=category)
    if not cases:
        print("no valid cases (need entries with question + relevant[])", file=sys.stderr)
        return 1
    report = evaluate(cases, search_retriever(TalamusPaths(root)), k=k)
    if json_out:
        _print_json(report.to_dict())
    else:
        print(report.format_table())
    return 0


def _cmd_remember(
    root: Path, transcript_file: str, diff_file: str | None, llm: LLMProvider, json_out: bool
) -> int:
    transcript = Path(transcript_file).read_text(encoding="utf-8")
    diff = Path(diff_file).read_text(encoding="utf-8") if diff_file else ""
    result = remember_session(TalamusPaths(root), transcript, diff, llm)
    if json_out:
        _print_json(result)
        return 0
    if result["skipped"]:
        print("session skipped (below the gate threshold)")
    else:
        print(f"remembered {result['notes_written']} notes from the session")
    return 0


def _cmd_search(
    root: Path,
    query: str,
    json_out: bool,
    limit: int = 5,
    policy: str | None = None,
    smart: bool = False,
    llm: LLMProvider | None = None,
) -> int:
    policy = policy or default_scope(root)
    if smart:  # Query2doc: expand the query with the user's LLM (cached), then search
        from talamus.smartsearch import expand_query

        provider = llm if llm is not None else _provider_for(root)
        query = expand_query(TalamusPaths(root), query, provider)
    search_result = search_brain(root, query, policy=policy, limit=limit)
    if not search_result.success or search_result.data is None:
        print(search_result.message, file=sys.stderr)
        return 1
    report = search_result.data
    results = [hit.to_dict() for hit in report.hits]
    if json_out:
        _print_json(results)
        return 0
    if not results:
        print("no relevant notes")
    for item in results:
        marker = "" if item.get("scope") == "[project]" else f"{item.get('scope', '')} "
        print(f"- {marker}{item['title']}: {item['summary']}")
    for warning in report.warnings:
        print(f"  ! {warning}", file=sys.stderr)
    return 0


def _cmd_read(root: Path, title: str, json_out: bool, as_of: str | None = None) -> int:
    read_result = read_note(root, title, as_of=as_of)
    data = read_result.data
    if data is None:
        print(read_result.message, file=sys.stderr)
        return 1
    if as_of:
        version = data.version
        if version is None:
            print(read_result.message, file=sys.stderr)
            return 1
        if json_out:
            _print_json(version)
            return 0
        print(f"# {version.get('title', title)}  [as-of {as_of}]")
        print()
        print(version.get("summary", ""))
        print()
        for section, body in version.get("body_sections", {}).items():
            print(f"## {section.capitalize()}")
            print(body)
            print()
        return 0
    if json_out:
        _print_json({"title": title, "found": data.found, "markdown": data.markdown})
        return 0 if read_result.success else 1
    if not read_result.success:
        print(f"note not found: {title}", file=sys.stderr)
        return 1
    print(data.markdown)
    return 0


def _cmd_timeline(root: Path, title: str, json_out: bool) -> int:
    data = note_timeline(TalamusPaths(root), title)
    if json_out:
        _print_json(data)
        return 0
    print(f"Timeline of '{title}'")
    print("- transaction history (when Talamus changed the record):")
    if not data["transaction"]:
        print("  (no versions)")
    for event in data["transaction"]:
        print(f"  [{event['at']}] {event['summary']}")
    print("- fact validity (when they were true in the represented world):")
    if not data["valid"]:
        print("  (no claims recorded)")
    for claim in data["valid"]:
        closed = f" -> {claim['to']}" if claim["to"] else ""
        marker = f"  (invalidated by: {claim['invalidated_by']})" if claim["invalidated_by"] else ""
        print(f"  [{claim['from']}{closed}] {claim['text']}{marker}")
    return 0


def _cmd_history(root: Path, title: str, as_of: str | None, json_out: bool) -> int:
    paths = TalamusPaths(root)
    if as_of:
        version = note_as_of(paths, title, as_of)
        if json_out:
            _print_json(version or {})
        elif version:
            print(f"[{version.get('updated_at', '?')}] {version.get('summary', '')}")
        else:
            print(f"no version of '{title}' as of {as_of}", file=sys.stderr)
        return 0 if version else 1
    versions = note_history(paths, title)
    if json_out:
        _print_json(versions)
        return 0
    if not versions:
        print(f"note not found: {title}", file=sys.stderr)
        return 1
    for version in versions:
        print(f"[{version.get('updated_at', '?')}] {version.get('summary', '')}")
    return 0


def _render_scoped_items(items: list[dict]) -> str:
    return "\n".join(
        f"[{idx}] {item['path']}\n{item['content']}" for idx, item in enumerate(items, start=1)
    )


def _cmd_recall(
    root: Path, question: str, json_out: bool, limit: int = 5, policy: str | None = None
) -> int:
    recall_result = recall_brain(root, question, policy=policy, limit=limit)
    if not recall_result.success or recall_result.data is None:
        print(recall_result.message, file=sys.stderr)
        return 1
    result = recall_result.data
    if json_out:
        _print_json(result.to_dict())
    else:
        print(result.context)
        for warning in result.warnings:
            print(f"  ! {warning}", file=sys.stderr)
    return 0


def _cmd_neighbors(root: Path, concept: str, json_out: bool) -> int:
    result = list_graph_neighbors(root, concept)
    if not result.success or result.data is None:
        print(result.message, file=sys.stderr)
        return 1
    items = [item.to_dict() for item in result.data]
    if json_out:
        _print_json(items)
        return 0
    if not items:
        print("no connected concept")
        return 0
    for item in items:
        arrow = "->" if item["direction"] == "out" else "<-"
        print(f"{arrow} [{item['relation']}] {item['title']}")
    return 0


def _cmd_relations(root: Path, prune: float | None, json_out: bool) -> int:
    paths = TalamusPaths(root)
    if prune is not None:
        removed = prune_relations(paths, prune)
        if json_out:
            _print_json({"pruned": removed})
        else:
            print(f"pruned {removed} relation(s) below confidence {prune}")
        return 0
    rels = list_relations(paths)
    if json_out:
        _print_json(rels)
        return 0
    if not rels:
        print("no relations")
        return 0
    for rel in rels:
        print(f"{rel['source']} --[{rel['relation']} {rel['confidence']:.2f}]--> {rel['target']}")
    return 0
