"""Build a Smithery-compatible view of the canonical UV MCP bundle."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata as importlib_metadata
import json
import tomllib
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "packaging" / "mcpb"
ARCHIVE_FILES = (
    "README.md",
    "icon.png",
    "pyproject.toml",
    "src/server.py",
    "uv.lock",
)


def _validate_locked_runtime(source: Path) -> None:
    """Fail if schema generation is not using the bundle's locked runtime."""
    with (source / "uv.lock").open("rb") as handle:
        packages = tomllib.load(handle)["package"]

    for package_name in ("talamus", "mcp"):
        locked = [
            str(package["version"]) for package in packages if package["name"] == package_name
        ]
        if len(locked) != 1:
            raise RuntimeError(f"expected one locked {package_name} version, found {locked}")
        try:
            actual = importlib_metadata.version(package_name)
        except importlib_metadata.PackageNotFoundError as exc:
            raise RuntimeError(f"{package_name} is not installed in the schema runtime") from exc
        if actual != locked[0]:
            raise RuntimeError(
                f"schema runtime has {package_name} {actual}, but the bundle locks "
                f"{locked[0]}; run this builder with "
                "'uv run --frozen --project packaging/mcpb python'"
            )


def _runtime_tools() -> list[dict[str, Any]]:
    """Return the exact schemas FastMCP exposes at runtime."""
    from talamus.mcp_server import server

    tools = asyncio.run(server.list_tools())
    fields = (
        "name",
        "title",
        "description",
        "inputSchema",
        "outputSchema",
        "annotations",
    )
    metadata: list[dict[str, Any]] = []
    for tool in tools:
        data = tool.model_dump(mode="json", by_alias=True, exclude_none=True)
        metadata.append({field: data[field] for field in fields if field in data})
    return metadata


def build_bundle(source: Path, output: Path) -> str:
    """Create the compatibility archive and return its SHA-256 digest."""
    source = source.resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing bundle: {output}")

    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Smithery CLI currently maps only python/node/binary/bun to its registry
    # runtime enum. Execution remains UV-managed through mcp_config.command.
    manifest["server"]["type"] = "python"
    manifest["tools"] = _runtime_tools()

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        for relative in ARCHIVE_FILES:
            path = source / relative
            if not path.is_file():
                raise FileNotFoundError(f"missing bundle file: {path}")
            archive.write(path, arcname=relative)

    return hashlib.sha256(output.read_bytes()).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New .mcpb file to create.")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Canonical MCPB source directory.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    _validate_locked_runtime(args.source.resolve())
    digest = build_bundle(args.source, args.output)
    print(f"bundle: {args.output.resolve()}")
    print(f"sha256: {digest}")


if __name__ == "__main__":
    main()
