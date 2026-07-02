"""Vault-import service: the migration seam shared by CLI, UI and MCP (P9)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from talamus.errors import TalamusError
from talamus.paths import TalamusPaths
from talamus.services.result import ServiceResult
from talamus.vault_import import import_vault


@dataclass(frozen=True)
class VaultImportResult:
    root: str
    vault: str
    notes_written: int
    skipped: int
    duplicates: tuple[str, ...]
    failed: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def import_markdown_vault(
    root: str | Path, vault_dir: str | Path
) -> ServiceResult[VaultImportResult]:
    root_path = Path(root)
    try:
        report = import_vault(TalamusPaths(root_path), vault_dir)
    except TalamusError as exc:
        return ServiceResult(
            success=False, message=f"Vault import failed: {exc}", code="vault_import_failed"
        )
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        return ServiceResult(
            success=False,
            message=f"Vault import service error: {exc}",
            code="vault_import_service_error",
        )
    data = VaultImportResult(
        root=str(root_path),
        vault=str(report.get("source", vault_dir)),
        notes_written=int(report.get("notes_written", 0)),
        skipped=int(report.get("skipped", 0)),
        duplicates=tuple(str(d) for d in report.get("duplicates", [])),
        failed=tuple(dict(f) for f in report.get("failed", [])),
    )
    return ServiceResult(
        success=True,
        message="Vault imported",
        code="vault_imported",
        data=data,
    )
