from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.fde_brain.paths import WorkspacePaths

DEFAULT_BACKEND = "ollama"
DEFAULT_MODEL = "gemma4:e4b"
VALID_BACKENDS = {"gemini", "kimi", "claude", "openai", "deepseek", "ollama"}


@dataclass(frozen=True)
class GraphifyCommand:
    args: list[str]

    def to_powershell(self) -> str:
        rendered: list[str] = []
        for arg in self.args:
            if any(char.isspace() for char in arg) or '"' in arg:
                escaped = arg.replace('"', '`"')
                rendered.append(f'"{escaped}"')
            else:
                rendered.append(arg)
        return " ".join(rendered)


def _as_posix_string(path: Path) -> str:
    return path.as_posix()


def graph_json_path(graph_dir: Path) -> Path:
    return graph_dir / "graphify-out" / "graph.json"


def stale_marker_path(graph_dir: Path) -> Path:
    return graph_dir / ".stale"


def mark_graph_stale(graph_dir: Path, reason: str) -> Path:
    graph_dir.mkdir(parents=True, exist_ok=True)
    marker = stale_marker_path(graph_dir)
    marker.write_text(
        f"stale_at: {datetime.now(timezone.utc).isoformat()}\nreason: {reason}\n",
        encoding="utf-8",
    )
    return marker


def mark_graph_fresh(graph_dir: Path) -> None:
    stale_marker_path(graph_dir).unlink(missing_ok=True)


def _validate_backend(backend: str) -> None:
    if backend not in VALID_BACKENDS:
        valid = ", ".join(sorted(VALID_BACKENDS))
        raise ValueError(f"invalid Graphify backend `{backend}`; expected one of: {valid}")


def _extract_command(input_path: Path, output_dir: Path, backend: str, model: str | None) -> GraphifyCommand:
    _validate_backend(backend)
    args = [
        "graphify",
        "extract",
        _as_posix_string(input_path),
        "--backend",
        backend,
    ]
    if model:
        args.extend(["--model", model])
    args.extend(["--max-concurrency", "1", "--out", _as_posix_string(output_dir)])
    return GraphifyCommand(args)


def brain_graph_extract(root: Path, backend: str = DEFAULT_BACKEND, model: str | None = DEFAULT_MODEL) -> GraphifyCommand:
    paths = WorkspacePaths(root)
    return _extract_command(paths.fde_brain, paths.brain_graph, backend, model)


def source_graph_extract(root: Path, backend: str = DEFAULT_BACKEND, model: str | None = DEFAULT_MODEL) -> GraphifyCommand:
    paths = WorkspacePaths(root)
    return _extract_command(paths.normalized, paths.source_graph, backend, model)


def run_graphify_command(command: GraphifyCommand, graph_dir: Path, timeout_sec: int = 1800) -> subprocess.CompletedProcess:
    result = subprocess.run(command.args, capture_output=True, text=True, timeout=timeout_sec, check=False)
    combined_output = f"{result.stdout}\n{result.stderr}".lower()
    semantic_failed = "semantic chunk" in combined_output and "failed" in combined_output
    if result.returncode == 0 and graph_json_path(graph_dir).exists() and not semantic_failed:
        mark_graph_fresh(graph_dir)
    else:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        mark_graph_stale(graph_dir, f"refresh failed: {detail[:500]}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or run Graphify commands for this workspace.")
    parser.add_argument("target", choices=["brain", "sources"], help="Graph to update.")
    parser.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, help="Graphify backend. Defaults to ollama.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Graphify model. Defaults to gemma4:e4b.")
    parser.add_argument("--run", action="store_true", help="Run Graphify instead of only printing the command.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    paths = WorkspacePaths(root)
    command = (
        brain_graph_extract(root, args.backend, args.model)
        if args.target == "brain"
        else source_graph_extract(root, args.backend, args.model)
    )
    graph_dir = paths.brain_graph if args.target == "brain" else paths.source_graph
    print(command.to_powershell())
    if args.run:
        result = run_graphify_command(command, graph_dir)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
