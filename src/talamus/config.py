from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class TalamusConfig:
    storage_provider: str
    pdf_converter: str
    ocr_provider: str
    ocr_model: str
    llm_provider: str
    graph_provider: str
    search_provider: str

    @classmethod
    def default(cls) -> TalamusConfig:
        return cls(
            storage_provider="obsidian",
            pdf_converter="docling",
            ocr_provider="ollama",
            ocr_model="glm-ocr",
            llm_provider="claude-cli",
            graph_provider="deterministic-json",
            search_provider="builtin-bm25",
        )


def save_config(path: Path, config: TalamusConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")


def load_config(path: Path) -> TalamusConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    return TalamusConfig(**data)
