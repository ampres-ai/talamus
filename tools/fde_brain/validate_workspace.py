from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.fde_brain.paths import WorkspacePaths


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.path} - {self.message}"


def validate_workspace(root: Path) -> list[ValidationIssue]:
    paths = WorkspacePaths(root)
    issues: list[ValidationIssue] = []

    for directory in paths.required_directories():
        if not directory.is_dir():
            issues.append(
                ValidationIssue(
                    "missing-directory",
                    str(directory),
                    "Create this required workspace directory.",
                )
            )

    required_files = [
        paths.agent_protocol,
        paths.runbook,
        paths.claude_entrypoint,
        paths.codex_entrypoint,
    ]
    for file_path in required_files:
        if not file_path.is_file():
            issues.append(
                ValidationIssue(
                    "missing-file",
                    str(file_path),
                    "Create this required protocol or entrypoint file.",
                )
            )

    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the FDE Brain workspace foundation.")
    parser.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    args = parser.parse_args(argv)

    issues = validate_workspace(Path(args.root).resolve())
    if not issues:
        print("workspace validation ok")
        return 0

    for issue in issues:
        print(issue, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
