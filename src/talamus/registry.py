"""Brain registry — the machine-wide record of every Talamus brain.

Lives at ``<TALAMUS_HOME>/registry.json``. The registry is metadata, never source
truth: each brain owns its notes; the registry records where brains live, their
type (central/project/archive), whether they participate in the federated index
and whether they are sensitive (excluded from cross-brain search by default).

Writes are atomic (temp file + ``os.replace``) with a small retry for Windows
file-lock hiccups.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

BRAIN_TYPES = ("central", "project", "archive")
REGISTRY_VERSION = 1


def talamus_home() -> Path:
    """Container for global brains, registry and federation (env ``TALAMUS_HOME``)."""
    return Path(os.environ.get("TALAMUS_HOME") or Path.home() / "talamus")


def registry_path(home: Path | None = None) -> Path:
    return (home or talamus_home()) / "registry.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-") or "brain"


@dataclass
class BrainInfo:
    id: str
    name: str
    path: str
    type: str = "project"
    federated: bool = True
    sensitive: bool = False
    created_at: str = ""
    updated_at: str = ""
    last_accessed_at: str = ""
    project: dict | None = None

    def root(self) -> Path:
        return Path(self.path)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Registry:
    version: int = REGISTRY_VERSION
    selected: str = ""
    brains: list[BrainInfo] = field(default_factory=list)

    def by_name(self, name: str) -> BrainInfo | None:
        for brain in self.brains:
            if brain.name == name:
                return brain
        return None

    def by_path(self, path: Path) -> BrainInfo | None:
        wanted = str(path.resolve())
        for brain in self.brains:
            if str(Path(brain.path).resolve()) == wanted:
                return brain
        return None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "selected": self.selected,
            "brains": [b.to_dict() for b in self.brains],
        }


def load_registry(home: Path | None = None) -> Registry:
    path = registry_path(home)
    if not path.is_file():
        return Registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Registry()
    brains = []
    for entry in data.get("brains", []):
        known = {f for f in BrainInfo.__dataclass_fields__}
        brains.append(BrainInfo(**{k: v for k, v in entry.items() if k in known}))
    return Registry(
        version=int(data.get("version", REGISTRY_VERSION)),
        selected=str(data.get("selected", "")),
        brains=brains,
    )


def save_registry(registry: Registry, home: Path | None = None) -> None:
    path = registry_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(registry.to_dict(), ensure_ascii=False, indent=2)
    tmp = path.with_suffix(".json.tmp")
    for attempt in range(3):
        try:
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, path)
            return
        except PermissionError:  # transient Windows lock — retry briefly
            if attempt == 2:
                raise
            time.sleep(0.1)


def _detect_project(path: Path) -> dict | None:
    return {"git_root": str(path)} if (path / ".git").exists() else None


def register_brain(
    root: Path,
    name: str | None = None,
    brain_type: str = "project",
    home: Path | None = None,
    federated: bool = True,
    sensitive: bool = False,
) -> BrainInfo:
    """Add (or refresh) a brain in the registry. Idempotent by path."""
    if brain_type not in BRAIN_TYPES:
        raise ValueError(f"brain type must be one of {BRAIN_TYPES}, got {brain_type!r}")
    registry = load_registry(home)
    root = root.resolve()
    existing = registry.by_path(root)
    now = _now()
    if existing is not None:
        existing.updated_at = now
        existing.last_accessed_at = now
        save_registry(registry, home)
        return existing
    base_name = name or root.name
    final_name = base_name
    suffix = 2
    while registry.by_name(final_name) is not None:
        final_name = f"{base_name}-{suffix}"
        suffix += 1
    brain = BrainInfo(
        id=f"brain-{_slug(final_name)}",
        name=final_name,
        path=str(root),
        type=brain_type,
        federated=federated,
        sensitive=sensitive,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
        project=_detect_project(root),
    )
    registry.brains.append(brain)
    save_registry(registry, home)
    return brain


def unregister_brain(name: str, home: Path | None = None) -> bool:
    """Remove a brain from the registry. Files on disk are never touched."""
    registry = load_registry(home)
    before = len(registry.brains)
    registry.brains = [b for b in registry.brains if b.name != name]
    if registry.selected == name:
        registry.selected = ""
    save_registry(registry, home)
    return len(registry.brains) < before


def rename_brain(old: str, new: str, home: Path | None = None) -> bool:
    registry = load_registry(home)
    if registry.by_name(new) is not None:
        raise ValueError(f"a brain named {new!r} already exists")
    brain = registry.by_name(old)
    if brain is None:
        return False
    brain.name = new
    brain.updated_at = _now()
    if registry.selected == old:
        registry.selected = new
    save_registry(registry, home)
    return True


def set_brain_flag(name: str, flag: str, value: bool, home: Path | None = None) -> bool:
    if flag not in ("federated", "sensitive"):
        raise ValueError(f"unknown flag {flag!r}")
    registry = load_registry(home)
    brain = registry.by_name(name)
    if brain is None:
        return False
    setattr(brain, flag, value)
    brain.updated_at = _now()
    save_registry(registry, home)
    return True


def select_brain(name: str, home: Path | None = None) -> bool:
    registry = load_registry(home)
    if registry.by_name(name) is None:
        return False
    registry.selected = name
    save_registry(registry, home)
    return True


def selected_brain(home: Path | None = None) -> BrainInfo | None:
    registry = load_registry(home)
    return registry.by_name(registry.selected) if registry.selected else None


def central_brain(home: Path | None = None) -> BrainInfo | None:
    """The personal central brain: the registered ``central`` entry, else home/default."""
    registry = load_registry(home)
    for brain in registry.brains:
        if brain.type == "central":
            return brain
    default_root = (home or talamus_home()) / "default"
    if (default_root / "talamus.json").exists():
        return BrainInfo(
            id="brain-default",
            name="default",
            path=str(default_root),
            type="central",
        )
    return None
