from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.fde_brain.paths import WorkspacePaths


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


def brain_graph_extract(root: Path, backend: str = "claude-cli") -> GraphifyCommand:
    paths = WorkspacePaths(root)
    return GraphifyCommand(
        [
            "graphify",
            "extract",
            _as_posix_string(paths.fde_brain),
            "--backend",
            backend,
            "--out",
            _as_posix_string(paths.brain_graph),
        ]
    )


def source_graph_extract(root: Path, backend: str = "claude-cli") -> GraphifyCommand:
    paths = WorkspacePaths(root)
    return GraphifyCommand(
        [
            "graphify",
            "extract",
            _as_posix_string(paths.normalized),
            "--backend",
            backend,
            "--out",
            _as_posix_string(paths.source_graph),
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print Graphify commands for this workspace.")
    parser.add_argument("target", choices=["brain", "sources"], help="Graph to update.")
    parser.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    parser.add_argument("--backend", default="claude-cli", help="Graphify backend. Defaults to claude-cli.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    command = brain_graph_extract(root, args.backend) if args.target == "brain" else source_graph_extract(root, args.backend)
    print(command.to_powershell())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
