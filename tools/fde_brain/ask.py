from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ollama

from tools.fde_brain.distill_local import distill_normalized_sections
from tools.fde_brain.graphify import mark_graph_stale
from tools.fde_brain.graphify import graph_json_path
from tools.fde_brain.paths import WorkspacePaths


GraphRunner = Callable[[list[str]], str]


@dataclass(frozen=True)
class ContextItem:
    layer: str
    path: str
    content: str
    score: int


@dataclass(frozen=True)
class ContextBundle:
    question: str
    graph_output: str | None
    items: list[ContextItem] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    used_source_fallback: bool = False

    def render(self) -> str:
        lines = [f"Question: {self.question}", ""]
        if self.graph_output:
            lines.extend(["Graphify routing output:", self.graph_output.strip(), ""])
        for idx, item in enumerate(self.items, start=1):
            lines.extend([
                f"[{idx}] {item.path}",
                item.content.strip(),
                "",
            ])
        if self.citations:
            lines.append("Citations:")
            lines.extend(self.citations)
        return "\n".join(lines).strip() + "\n"


@dataclass(frozen=True)
class AnswerResult:
    model: str
    text: str
    citations: list[str]
    context: ContextBundle
    promoted_to: list[str] = field(default_factory=list)


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _query_terms(question: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{2,}", question)
        if token.lower() not in {"the", "and", "for", "with", "when", "what", "should", "use"}
    }


def _score(content: str, terms: set[str]) -> int:
    lowered = content.lower()
    return sum(lowered.count(term) for term in terms)


def _read_markdown_candidates(root: Path, layer: str, terms: set[str], limit: int) -> list[ContextItem]:
    items: list[ContextItem] = []
    for path in sorted(root.rglob("*.md")):
        if path.name == ".gitkeep":
            continue
        content = path.read_text(encoding="utf-8")
        score = _score(content, terms)
        if score <= 0:
            continue
        snippet = content[:5000]
        items.append(ContextItem(layer=layer, path=path.as_posix(), content=snippet, score=score))
    return sorted(items, key=lambda item: item.score, reverse=True)[:limit]


def _paths_from_graph_output(paths: WorkspacePaths, graph_output: str | None, layer: str) -> list[ContextItem]:
    if not graph_output:
        return []
    matches = re.findall(r"(?:FDE Brain|AI Space/normalized)[^\r\n\t]*?\.md", graph_output)
    items: list[ContextItem] = []
    seen: set[Path] = set()
    for raw_match in matches:
        cleaned = raw_match.strip().strip("`'\".,;:)")
        candidate = paths.root / cleaned
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        content = candidate.read_text(encoding="utf-8")
        items.append(
            ContextItem(
                layer=layer,
                path=candidate.as_posix(),
                content=content[:5000],
                score=1_000_000,
            )
        )
    return items


def _default_graph_runner(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=120)
    return (result.stdout or result.stderr).strip()


def _graph_query(paths: WorkspacePaths, question: str, layer: str, runner: GraphRunner | None) -> str | None:
    if runner is None:
        return None
    graph_dir = paths.brain_graph if layer == "brain" else paths.source_graph
    graph_json = graph_json_path(graph_dir)
    if not graph_json.exists():
        return None
    return runner(["graphify", "query", question, "--graph", graph_json.as_posix(), "--budget", "1600"])


def build_context_bundle(
    paths: WorkspacePaths,
    question: str,
    graph_runner: GraphRunner | None = _default_graph_runner,
    limit: int = 5,
) -> ContextBundle:
    terms = _query_terms(question)
    graph_output = _graph_query(paths, question, "brain", graph_runner)
    graph_items = _paths_from_graph_output(paths, graph_output, "brain")
    keyword_items = _read_markdown_candidates(paths.fde_brain, "brain", terms, limit)
    seen_paths = {item.path for item in graph_items}
    brain_items = graph_items + [item for item in keyword_items if item.path not in seen_paths]
    brain_items = brain_items[:limit]
    used_source_fallback = False
    items = brain_items

    if not items:
        graph_output = graph_output or _graph_query(paths, question, "source", graph_runner)
        source_graph_items = _paths_from_graph_output(paths, graph_output, "source")
        source_keyword_items = _read_markdown_candidates(paths.normalized, "source", terms, limit)
        seen_paths = {item.path for item in source_graph_items}
        items = (source_graph_items + [item for item in source_keyword_items if item.path not in seen_paths])[:limit]
        used_source_fallback = bool(items)

    citations = [f"[{idx}] {_rel(Path(item.path), paths.root)}" for idx, item in enumerate(items, start=1)]
    normalized_items = [
        ContextItem(
            layer=item.layer,
            path=_rel(Path(item.path), paths.root),
            content=item.content,
            score=item.score,
        )
        for item in items
    ]
    return ContextBundle(
        question=question,
        graph_output=graph_output,
        items=normalized_items,
        citations=citations,
        used_source_fallback=used_source_fallback,
    )


def _answer_prompt(question: str, bundle: ContextBundle) -> str:
    return (
        "Answer the question using only the Markdown context below. "
        "Cite sources using bracket numbers like [1]. If the context is insufficient, say so.\n\n"
        f"{bundle.render()}"
    )


def _answer_with_gemma(prompt: str, model_name: str = "gemma4:e4b") -> str:
    response = ollama.chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0, "num_ctx": 16384},
    )
    return str(response["message"]["content"]).strip()


def _answer_with_subprocess(command: list[str], prompt: str, timeout_sec: int = 180) -> str:
    completed = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=timeout_sec, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"{command[0]} exited {completed.returncode}")
    return completed.stdout.strip()


def _title_to_filename(title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", title.strip()).strip("-")
    return cleaned or "note"


def _promote_source_fallback(paths: WorkspacePaths, bundle: ContextBundle) -> list[str]:
    section_paths: list[Path] = []
    for item in bundle.items:
        if item.layer != "source":
            continue
        path = paths.root / item.path
        try:
            path.relative_to(paths.normalized)
        except ValueError:
            continue
        if path.is_file() and path.suffix == ".md":
            section_paths.append(path)
    if not section_paths:
        return []

    run_id = "query-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    result = distill_normalized_sections(section_paths=section_paths, paths=paths, run_id=run_id)
    promoted: list[str] = []
    paths.fde_brain.mkdir(parents=True, exist_ok=True)
    for note in result.notes:
        note_path = paths.fde_brain / f"{_title_to_filename(note.title)}.md"
        note_path.write_text(note.content, encoding="utf-8")
        promoted.append(_rel(note_path, paths.root))
    if promoted:
        mark_graph_stale(paths.brain_graph, "query-driven source fallback promotion")
    return promoted


def answer_question(
    paths: WorkspacePaths,
    question: str,
    model: str = "auto",
    read_only: bool = False,
    graph_runner: GraphRunner | None = _default_graph_runner,
) -> AnswerResult:
    selected = "gemma" if model == "auto" else model
    bundle = build_context_bundle(paths, question, graph_runner=graph_runner)
    prompt = _answer_prompt(question, bundle)

    if selected == "gemma":
        text = _answer_with_gemma(prompt)
    elif selected == "claude":
        text = _answer_with_subprocess(["claude", "-p"], prompt)
    elif selected == "codex":
        text = _answer_with_subprocess(["codex", "exec", prompt], "")
    else:
        raise ValueError("model must be one of: auto, gemma, claude, codex")

    promoted_to: list[str] = []
    if bundle.used_source_fallback and not read_only:
        promoted_to = _promote_source_fallback(paths, bundle)
        if promoted_to:
            text += "\n\nPromotion note: source fallback knowledge was promoted into FDE Brain."
        else:
            text += "\n\nPromotion note: source fallback was used, but no stable reusable note was promoted."

    return AnswerResult(model=selected, text=text, citations=bundle.citations, context=bundle, promoted_to=promoted_to)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Ask the Dual Graph LLM Wiki.")
    sub = parser.add_subparsers(dest="command", required=True)
    context_parser = sub.add_parser("context", help="Print citation-ready context.")
    context_parser.add_argument("question")
    context_parser.add_argument("--root", default=".")

    answer_parser = sub.add_parser("answer", help="Retrieve context and draft a cited answer.")
    answer_parser.add_argument("question")
    answer_parser.add_argument("--root", default=".")
    answer_parser.add_argument("--model", choices=["auto", "gemma", "claude", "codex"], default="auto")
    answer_parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args(argv)

    paths = WorkspacePaths(Path(args.root).resolve())
    if args.command == "context":
        print(build_context_bundle(paths, args.question).render())
        return 0

    result = answer_question(paths, args.question, model=args.model, read_only=args.read_only)
    print(f"Model: {result.model}\n")
    print(result.text)
    if result.citations:
        print("\nCitations:")
        for citation in result.citations:
            print(citation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
