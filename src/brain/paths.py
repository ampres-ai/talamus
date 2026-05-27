from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrainPaths:
    project_root: Path

    @property
    def config_path(self) -> Path:
        return self.project_root / "brain.json"

    @property
    def knowledge(self) -> Path:
        return self.project_root / "knowledge"

    @property
    def pending(self) -> Path:
        return self.knowledge / "pending"

    @property
    def raw(self) -> Path:
        return self.knowledge / "raw"

    @property
    def normalized(self) -> Path:
        return self.knowledge / "normalized"

    @property
    def notes(self) -> Path:
        return self.knowledge / "notes"

    @property
    def graph(self) -> Path:
        return self.knowledge / "graph"

    @property
    def index(self) -> Path:
        return self.knowledge / "index"

    @property
    def logs(self) -> Path:
        return self.knowledge / "logs"

    @property
    def review(self) -> Path:
        return self.knowledge / "review"

    @property
    def failed(self) -> Path:
        return self.knowledge / "failed"

    @property
    def skills(self) -> Path:
        return self.knowledge / "skills"

    def required_directories(self) -> list[Path]:
        return [
            self.pending,
            self.raw,
            self.normalized,
            self.notes,
            self.graph,
            self.index,
            self.logs / "runs",
            self.logs / "decisions",
            self.logs / "errors",
            self.logs / "retrieval",
            self.review / "needs-human",
            self.review / "low-confidence-normalization",
            self.review / "missing-concepts",
            self.failed / "technical-failures",
            self.skills,
        ]

    def ensure_directories(self) -> list[Path]:
        created: list[Path] = []
        for directory in self.required_directories():
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created.append(directory)
            gitkeep = directory / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.write_text("", encoding="utf-8")
        return created
