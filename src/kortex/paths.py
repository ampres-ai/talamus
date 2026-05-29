from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KortexPaths:
    project_root: Path

    @property
    def config_path(self) -> Path:
        return self.project_root / "kortex.json"

    @property
    def notes(self) -> Path:
        return self.project_root / "notes"

    @property
    def kortex_dir(self) -> Path:
        return self.project_root / ".kortex"

    @property
    def raw(self) -> Path:
        return self.kortex_dir / "raw"

    @property
    def normalized(self) -> Path:
        return self.kortex_dir / "normalized"

    @property
    def cache(self) -> Path:
        return self.kortex_dir / "cache"

    @property
    def notes_cache(self) -> Path:
        return self.cache / "notes"

    @property
    def graph_file(self) -> Path:
        return self.cache / "graph.json"

    @property
    def index_file(self) -> Path:
        return self.cache / "bm25.json"

    @property
    def logs(self) -> Path:
        return self.kortex_dir / "logs"

    def required_directories(self) -> list[Path]:
        return [self.notes, self.raw, self.normalized, self.cache, self.notes_cache, self.logs]

    def ensure_directories(self) -> list[Path]:
        created: list[Path] = []
        for directory in self.required_directories():
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created.append(directory)
        return created
