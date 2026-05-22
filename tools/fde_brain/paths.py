from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    """Central path map for the Dual Graph LLM Wiki workspace."""

    root: Path

    @property
    def ai_space(self) -> Path:
        return self.root / "AI Space"

    @property
    def fde_brain(self) -> Path:
        return self.root / "FDE Brain"

    @property
    def pending(self) -> Path:
        return self.ai_space / "pending"

    @property
    def raw(self) -> Path:
        return self.ai_space / "raw"

    @property
    def normalized(self) -> Path:
        return self.ai_space / "normalized"

    @property
    def graph_root(self) -> Path:
        return self.ai_space / "graph"

    @property
    def brain_graph(self) -> Path:
        return self.graph_root / "brain"

    @property
    def source_graph(self) -> Path:
        return self.graph_root / "sources"

    @property
    def logs(self) -> Path:
        return self.ai_space / "logs"

    @property
    def review(self) -> Path:
        return self.ai_space / "review"

    @property
    def failed(self) -> Path:
        return self.ai_space / "failed"

    @property
    def system(self) -> Path:
        return self.ai_space / "system"

    @property
    def agent_protocol(self) -> Path:
        return self.system / "AGENT_PROTOCOL.md"

    @property
    def runbook(self) -> Path:
        return self.system / "RUNBOOK.md"

    @property
    def claude_entrypoint(self) -> Path:
        return self.root / "CLAUDE.md"

    @property
    def codex_entrypoint(self) -> Path:
        return self.root / "AGENTS.md"

    @property
    def logs_runs(self) -> Path:
        return self.logs / "runs"

    @property
    def logs_decisions(self) -> Path:
        return self.logs / "decisions"

    @property
    def logs_errors(self) -> Path:
        return self.logs / "errors"

    @property
    def logs_promotions(self) -> Path:
        return self.logs / "promotions"

    @property
    def registry_path(self) -> Path:
        return self.normalized / "registry.json"

    def raw_for(self, category: str) -> Path:
        return self.raw / category

    def normalized_for(self, category: str) -> Path:
        return self.normalized / category

    def required_directories(self) -> list[Path]:
        return [
            self.pending,
            self.raw,
            self.normalized,
            self.brain_graph,
            self.source_graph,
            self.logs / "runs",
            self.logs / "decisions",
            self.logs / "errors",
            self.logs / "promotions",
            self.review / "ambiguous",
            self.review / "conflicts",
            self.review / "needs-human",
            self.review / "low-confidence-normalization",
            self.failed / "technical-failures",
            self.system,
            self.fde_brain,
        ]

    def ensure_directories(self) -> list[Path]:
        created: list[Path] = []
        for directory in self.required_directories():
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created.append(directory)
            gitkeep = directory / ".gitkeep"
            if directory != self.fde_brain and not gitkeep.exists():
                gitkeep.write_text("", encoding="utf-8")
        return created
