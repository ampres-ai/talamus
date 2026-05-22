from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pypdf import PdfReader

from tools.fde_brain.categories import Category
from tools.fde_brain.chapters import extract_chapters_from_pdf
from tools.fde_brain.ocr import extract_text_from_image
from tools.fde_brain.paths import WorkspacePaths

MIN_DIGITAL_PDF_CHARS = 50

RoutedTo = Literal["normalized", "review", "failed"]


@dataclass(frozen=True)
class NormalizedOutput:
    ok: bool
    output_path: Path | None
    routed_to: RoutedTo
    parser: str
    error: str | None = None


_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(\d+-)?")


def _slug_from_raw(raw_path: Path) -> str:
    stem = _DATE_PREFIX_RE.sub("", raw_path.stem)
    return stem.lower().replace(" ", "-")


def _frontmatter(
    raw_path: Path,
    category: Category,
    raw_hash: str,
    captured_at: datetime,
    parser: str,
    confidence: float,
    workspace_root: Path,
) -> str:
    try:
        source_rel = raw_path.relative_to(workspace_root).as_posix()
    except ValueError:
        source_rel = raw_path.as_posix()
    return (
        "---\n"
        f"source-path: {source_rel}\n"
        f"source-type: {category}\n"
        f"source-hash: {raw_hash}\n"
        f"captured-at: {captured_at.isoformat()}\n"
        f"parser: {parser}\n"
        f"parser-confidence: {confidence}\n"
        "---\n\n"
    )


def _write(dest: Path, body: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")


def _normalize_passthrough(
    raw_path: Path,
    category: Category,
    raw_hash: str,
    captured_at: datetime,
    paths: WorkspacePaths,
) -> NormalizedOutput:
    body_text = raw_path.read_text(encoding="utf-8")
    body = _frontmatter(raw_path, category, raw_hash, captured_at, "passthrough", 1.0, paths.root) + body_text
    dest = paths.normalized_for(category) / f"{_slug_from_raw(raw_path)}.md"
    _write(dest, body)
    return NormalizedOutput(ok=True, output_path=dest, routed_to="normalized", parser="passthrough")


def _normalize_pdf(
    raw_path: Path,
    raw_hash: str,
    captured_at: datetime,
    paths: WorkspacePaths,
) -> NormalizedOutput:
    try:
        reader = PdfReader(str(raw_path))
        pages_text: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            pages_text.append(extracted.strip())
    except Exception as exc:
        dest = paths.failed / "technical-failures" / f"{_slug_from_raw(raw_path)}.md"
        body = (
            _frontmatter(raw_path, "pdf", raw_hash, captured_at, "pypdf", 0.0, paths.root)
            + f"# PDF parsing failed\n\nError: {exc}\n"
        )
        _write(dest, body)
        return NormalizedOutput(ok=False, output_path=dest, routed_to="failed", parser="pypdf", error=str(exc))

    total_chars = sum(len(t) for t in pages_text)
    slug = _slug_from_raw(raw_path)

    if total_chars < MIN_DIGITAL_PDF_CHARS:
        dest = paths.review / "low-confidence-normalization" / f"{slug}.md"
        body = (
            _frontmatter(raw_path, "pdf", raw_hash, captured_at, "pypdf", 0.2, paths.root)
            + f"# Low-confidence PDF normalization\n\nExtracted {total_chars} characters across {len(pages_text)} pages. "
            "Routed for human review.\n"
        )
        _write(dest, body)
        return NormalizedOutput(ok=True, output_path=dest, routed_to="review", parser="pypdf")

    body_parts = [_frontmatter(raw_path, "pdf", raw_hash, captured_at, "pypdf", 1.0, paths.root)]
    body_parts.append(f"# {raw_path.stem}\n\n")

    chapters = extract_chapters_from_pdf(reader)
    if chapters:
        for chapter in chapters:
            section_text = "\n\n".join(
                pages_text[i - 1]
                for i in range(chapter.page_start, chapter.page_end + 1)
                if 1 <= i <= len(pages_text) and pages_text[i - 1]
            )
            heading_prefix = "#" * (chapter.level + 1)
            body_parts.append(
                f"{heading_prefix} {chapter.title}\n\n"
                f"_Pages {chapter.page_start}–{chapter.page_end}_\n\n"
                f"{section_text}\n\n"
            )
    else:
        for idx, text in enumerate(pages_text, start=1):
            body_parts.append(f"## Page {idx}\n\n{text}\n\n")

    dest = paths.normalized_for("pdf") / f"{slug}.md"
    _write(dest, "".join(body_parts))
    return NormalizedOutput(ok=True, output_path=dest, routed_to="normalized", parser="pypdf")


def _normalize_image(
    raw_path: Path,
    raw_hash: str,
    captured_at: datetime,
    paths: WorkspacePaths,
) -> NormalizedOutput:
    result = extract_text_from_image(raw_path)
    slug = _slug_from_raw(raw_path)

    if not result.ok:
        dest = paths.failed / "technical-failures" / f"{slug}.md"
        body = (
            _frontmatter(raw_path, "image", raw_hash, captured_at, "glm-ocr", 0.0, paths.root)
            + f"# OCR failed\n\nError: {result.error}\n"
        )
        _write(dest, body)
        return NormalizedOutput(
            ok=False, output_path=dest, routed_to="failed", parser="glm-ocr", error=result.error
        )

    body = (
        _frontmatter(raw_path, "image", raw_hash, captured_at, "glm-ocr", 0.9, paths.root)
        + f"# {raw_path.stem}\n\n## OCR\n\n{result.text}\n"
    )
    dest = paths.normalized_for("image") / f"{slug}.md"
    _write(dest, body)
    return NormalizedOutput(ok=True, output_path=dest, routed_to="normalized", parser="glm-ocr")


def _normalize_unknown(
    raw_path: Path,
    raw_hash: str,
    captured_at: datetime,
    paths: WorkspacePaths,
) -> NormalizedOutput:
    slug = _slug_from_raw(raw_path) or raw_path.name
    dest = paths.review / "needs-human" / f"{slug}.md"
    body = (
        _frontmatter(raw_path, "unknown", raw_hash, captured_at, "none", 0.0, paths.root)
        + f"# Needs human review\n\nUnrecognized file extension: `{raw_path.suffix}`.\n"
        f"Original at `{raw_path.as_posix()}`.\n"
    )
    _write(dest, body)
    return NormalizedOutput(ok=True, output_path=dest, routed_to="review", parser="none")


def normalize_source(
    raw_path: Path,
    category: Category,
    raw_hash: str,
    captured_at: datetime,
    paths: WorkspacePaths,
) -> NormalizedOutput:
    if category in ("markdown", "text"):
        return _normalize_passthrough(raw_path, category, raw_hash, captured_at, paths)
    if category == "pdf":
        return _normalize_pdf(raw_path, raw_hash, captured_at, paths)
    if category == "image":
        return _normalize_image(raw_path, raw_hash, captured_at, paths)
    return _normalize_unknown(raw_path, raw_hash, captured_at, paths)
