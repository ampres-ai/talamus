from __future__ import annotations

import json
import posixpath
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urldefrag
from xml.etree import ElementTree as ET

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pypdf import PdfReader

from tools.fde_brain.categories import Category
from tools.fde_brain.chapters import extract_chapters_from_pdf
from tools.fde_brain.layout import page_has_visual_content
from tools.fde_brain.ocr import extract_text_from_image
from tools.fde_brain.paths import WorkspacePaths
from tools.fde_brain.pdf_render import render_page_to_tempfile

MIN_DIGITAL_PDF_CHARS = 50

RoutedTo = Literal["normalized", "review", "failed"]


@dataclass(frozen=True)
class NormalizedOutput:
    ok: bool
    output_path: Path | None
    routed_to: RoutedTo
    parser: str
    error: str | None = None
    manifest_path: Path | None = None
    section_paths: list[Path] = field(default_factory=list)
    quality_report_path: Path | None = None
    package_dir: Path | None = None


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


_MOJIBAKE_REPLACEMENTS = {
    "â€™": "'",
    "â€˜": "'",
    "â€œ": '"',
    "â€\x9d": '"',
    "â€“": "-",
    "â€”": "-",
    "â€¦": "...",
    "Â ": " ",
    "Â": "",
}


def _clean_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    for bad, good in _MOJIBAKE_REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)
    cleaned = re.sub(r"(?<=\w)-\n(?=\w)", "", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _remove_repeated_page_noise(pages_text: list[str]) -> list[str]:
    if len(pages_text) < 2:
        return [_clean_text(text) for text in pages_text]

    counts: dict[str, int] = {}
    for text in pages_text:
        seen_on_page: set[str] = set()
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if len(stripped) <= 80:
                seen_on_page.add(stripped)
        for line in seen_on_page:
            counts[line] = counts.get(line, 0) + 1

    threshold = max(2, len(pages_text) // 2)
    repeated = {line for line, count in counts.items() if count >= threshold}
    cleaned_pages: list[str] = []
    for text in pages_text:
        kept: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped in repeated:
                continue
            if re.fullmatch(r"(?:page\s*)?\d+", stripped, flags=re.IGNORECASE):
                continue
            kept.append(line)
        cleaned_pages.append(_clean_text("\n".join(kept)))
    return cleaned_pages


def _rel_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _slug_text(value: str, fallback: str = "section") -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return slug.lower() or fallback


def _yaml_scalar(value: str) -> str:
    text = str(value)
    if text == "":
        return '""'
    needs_quotes = (
        ": " in text
        or text.startswith(("-", "?", ":", "@", "`", "!", "&", "*", "#", "{", "}", "[", "]"))
        or "\n" in text
        or text.strip() != text
    )
    if not needs_quotes:
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


@dataclass(frozen=True)
class _SectionDraft:
    section_id: str
    title: str
    body: str
    locator: str
    confidence: float = 1.0
    page_start: int | None = None
    page_end: int | None = None
    classification: str = "reusable-knowledge-candidate"


class _MarkdownHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._heading: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading = "#" * int(tag[1])
            self.parts.append("\n\n")
        elif tag in {"p", "div", "section", "article", "br"}:
            self.parts.append("\n\n" if tag != "br" else "\n")
        elif tag in {"li"}:
            self.parts.append("\n- ")

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "section", "article", "li"}:
            self.parts.append("\n")
            self._heading = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._heading:
            self.parts.append(f"{self._heading} {text}")
            self._heading = None
        else:
            self.parts.append(text)

    def markdown(self) -> str:
        return _clean_text(" ".join(self.parts).replace("# ", "\n# "))


def _section_frontmatter(
    raw_path: Path,
    category: Category,
    raw_hash: str,
    captured_at: datetime,
    parser: str,
    confidence: float,
    section: _SectionDraft,
    paths: WorkspacePaths,
    previous_section: str | None,
    next_section: str | None,
    classification: str = "reusable-knowledge-candidate",
) -> str:
    lines = [
        "---",
        f"source-path: {_rel_path(raw_path, paths.root)}",
        f"source-type: {category}",
        f"source-hash: {raw_hash}",
        f"captured-at: {captured_at.isoformat()}",
        f"parser: {parser}",
        f"parser-confidence: {confidence}",
        f"section-id: {section.section_id}",
        f"section-title: {_yaml_scalar(section.title)}",
        f"source-location: {_yaml_scalar(section.locator)}",
        f"previous-section: {_yaml_scalar(previous_section or '')}",
        f"next-section: {_yaml_scalar(next_section or '')}",
        f"classification: {classification}",
        "---",
        "",
    ]
    return "\n".join(lines)


def _write_package(
    raw_path: Path,
    category: Category,
    raw_hash: str,
    captured_at: datetime,
    paths: WorkspacePaths,
    parser: str,
    parser_confidence: float,
    sections: list[_SectionDraft],
    quality: dict,
) -> NormalizedOutput:
    slug = _slug_from_raw(raw_path)
    package_dir = paths.normalized_for(category) / slug
    sections_dir = package_dir / "sections"
    package_dir.mkdir(parents=True, exist_ok=True)
    sections_dir.mkdir(parents=True, exist_ok=True)

    section_paths: list[Path] = []
    filenames: list[str] = []
    for section in sections:
        filenames.append(f"{section.section_id}-{_slug_text(section.title)}.md")

    for index, section in enumerate(sections):
        section_path = sections_dir / filenames[index]
        previous_rel = (
            _rel_path(sections_dir / filenames[index - 1], paths.root)
            if index > 0 else None
        )
        next_rel = (
            _rel_path(sections_dir / filenames[index + 1], paths.root)
            if index + 1 < len(sections) else None
        )
        body = section.body.strip()
        if not body.startswith("#"):
            body = f"# {section.title}\n\n{body}"
        content = _section_frontmatter(
            raw_path=raw_path,
            category=category,
            raw_hash=raw_hash,
            captured_at=captured_at,
            parser=parser,
            confidence=section.confidence,
            section=section,
            paths=paths,
            previous_section=previous_rel,
            next_section=next_rel,
            classification=section.classification,
        ) + body.strip() + "\n"
        _write(section_path, content)
        section_paths.append(section_path)

    manifest_path = package_dir / "manifest.json"
    quality_report_path = package_dir / "quality-report.json"
    manifest_sections = []
    for index, section in enumerate(sections):
        section_path = section_paths[index]
        manifest_sections.append({
            "section_id": section.section_id,
            "title": section.title,
            "path": _rel_path(section_path, paths.root),
            "locator": section.locator,
            "page_start": section.page_start,
            "page_end": section.page_end,
            "confidence": section.confidence,
            "previous_section": _rel_path(section_paths[index - 1], paths.root) if index > 0 else None,
            "next_section": _rel_path(section_paths[index + 1], paths.root) if index + 1 < len(section_paths) else None,
        })
    manifest = {
        "package_version": "2.0",
        "source_slug": slug,
        "source": {
            "raw_path": _rel_path(raw_path, paths.root),
            "raw_hash": raw_hash,
            "source_type": category,
            "captured_at": captured_at.isoformat(),
        },
        "parser": parser,
        "parser_confidence": parser_confidence,
        "sections": manifest_sections,
        "quality_report": _rel_path(quality_report_path, paths.root),
    }
    _write(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False))

    quality_payload = {
        "source_slug": slug,
        "source_type": category,
        "parser": parser,
        "parser_confidence": parser_confidence,
        "section_count": len(sections),
        **quality,
    }
    _write(quality_report_path, json.dumps(quality_payload, indent=2, ensure_ascii=False))

    return NormalizedOutput(
        ok=True,
        output_path=manifest_path,
        routed_to="normalized",
        parser=parser,
        manifest_path=manifest_path,
        section_paths=section_paths,
        quality_report_path=quality_report_path,
        package_dir=package_dir,
    )


def _normalize_passthrough(
    raw_path: Path,
    category: Category,
    raw_hash: str,
    captured_at: datetime,
    paths: WorkspacePaths,
) -> NormalizedOutput:
    body_text = _clean_text(raw_path.read_text(encoding="utf-8"))
    title_match = re.search(r"^#\s+(.+)$", body_text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else raw_path.stem
    classification = (
        "personal-note"
        if category == "markdown" and re.search(r"\b(i think|todo|personal|idea)\b", body_text, re.IGNORECASE)
        else "reusable-knowledge-candidate"
    )
    section = _SectionDraft(
        section_id="001",
        title=title,
        body=body_text,
        locator=category,
        confidence=1.0,
        classification=classification,
    )
    quality = {
        "total_chars": len(body_text),
        "ocr_pages": 0,
        "warnings": [],
        "classification": classification,
    }
    return _write_package(
        raw_path=raw_path,
        category=category,
        raw_hash=raw_hash,
        captured_at=captured_at,
        paths=paths,
        parser="passthrough",
        parser_confidence=1.0,
        sections=[section],
        quality=quality,
    )


def _ocr_page_via_render(raw_path: Path, page_index: int) -> str:
    tmp_png: Path | None = None
    try:
        tmp_png = render_page_to_tempfile(raw_path, page_index)
        result = extract_text_from_image(tmp_png)
        return result.text if result.ok else ""
    except Exception:
        return ""
    finally:
        if tmp_png is not None:
            tmp_png.unlink(missing_ok=True)


def _combine_page_text(pypdf_text: str, ocr_text: str) -> str:
    if not ocr_text:
        return pypdf_text
    if not pypdf_text:
        return ocr_text
    if len(ocr_text) > len(pypdf_text):
        return ocr_text
    return f"{pypdf_text}\n\n[Visual content extracted via GLM-OCR]\n\n{ocr_text}"


def _normalize_pdf(
    raw_path: Path,
    raw_hash: str,
    captured_at: datetime,
    paths: WorkspacePaths,
) -> NormalizedOutput:
    def _progress(stage: str, message: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] [{stage}] {message}", flush=True)

    try:
        _progress("normalize", f"opening pdf …")
        reader = PdfReader(str(raw_path))
        total_pages = len(reader.pages)
        _progress("normalize", f"opened pdf ({total_pages} pages)")
        pages_text: list[str] = []
        ocr_used_pages = 0
        for idx, page in enumerate(reader.pages):
            pypdf_text = (page.extract_text() or "").strip()
            if page_has_visual_content(page):
                _progress("normalize", f"page {idx+1}/{total_pages} OCR …")
                ocr_text = _ocr_page_via_render(raw_path, idx)
                if ocr_text:
                    ocr_used_pages += 1
                pages_text.append(_combine_page_text(pypdf_text, ocr_text))
            else:
                if (idx + 1) % 50 == 0 or idx == 0:
                    _progress("normalize", f"page {idx+1}/{total_pages} text-only")
                pages_text.append(pypdf_text)
        _progress("normalize", f"all pages done ({ocr_used_pages} ocr'd of {total_pages})")
    except Exception as exc:
        dest = paths.failed / "technical-failures" / f"{_slug_from_raw(raw_path)}.md"
        body = (
            _frontmatter(raw_path, "pdf", raw_hash, captured_at, "pypdf", 0.0, paths.root)
            + f"# PDF parsing failed\n\nError: {exc}\n"
        )
        _write(dest, body)
        return NormalizedOutput(ok=False, output_path=dest, routed_to="failed", parser="pypdf", error=str(exc))

    pages_text = _remove_repeated_page_noise(pages_text)
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

    chapters = extract_chapters_from_pdf(reader)
    sections: list[_SectionDraft] = []
    if chapters:
        for index, chapter in enumerate(chapters, start=1):
            section_text = "\n\n".join(
                pages_text[i - 1]
                for i in range(chapter.page_start, chapter.page_end + 1)
                if 1 <= i <= len(pages_text) and pages_text[i - 1]
            )
            sections.append(
                _SectionDraft(
                    section_id=f"{index:03d}",
                    title=chapter.title,
                    body=f"# {chapter.title}\n\n{section_text}",
                    locator=f"pages {chapter.page_start}-{chapter.page_end}",
                    confidence=1.0,
                    page_start=chapter.page_start,
                    page_end=chapter.page_end,
                )
            )
    else:
        for idx, text in enumerate(pages_text, start=1):
            sections.append(
                _SectionDraft(
                    section_id=f"{idx:03d}",
                    title=f"Page {idx}",
                    body=f"# Page {idx}\n\n{text}",
                    locator=f"pages {idx}-{idx}",
                    confidence=1.0,
                    page_start=idx,
                    page_end=idx,
                )
            )

    quality = {
        "total_chars": total_chars,
        "total_pages": len(pages_text),
        "ocr_pages": ocr_used_pages,
        "warnings": [],
        "cleanup": {
            "repeated_headers_removed": True,
            "hyphenation_repaired": True,
            "encoding_repaired": True,
        },
    }
    return _write_package(
        raw_path=raw_path,
        category="pdf",
        raw_hash=raw_hash,
        captured_at=captured_at,
        paths=paths,
        parser="pypdf",
        parser_confidence=1.0,
        sections=sections,
        quality=quality,
    )


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
        f"# {raw_path.stem}\n\n## OCR\n\n{_clean_text(result.text)}"
    )
    if len(_clean_text(result.text)) < 5:
        dest = paths.review / "low-confidence-normalization" / f"{slug}.md"
        review_body = (
            _frontmatter(raw_path, "image", raw_hash, captured_at, "glm-ocr", 0.2, paths.root)
            + "# Low-confidence image OCR\n\nOCR returned too little text for automatic promotion.\n"
        )
        _write(dest, review_body)
        return NormalizedOutput(ok=True, output_path=dest, routed_to="review", parser="glm-ocr")
    section = _SectionDraft(
        section_id="001",
        title=raw_path.stem,
        body=body,
        locator="image ocr",
        confidence=0.9,
    )
    quality = {
        "total_chars": len(result.text),
        "ocr_pages": 1,
        "warnings": [],
    }
    return _write_package(
        raw_path=raw_path,
        category="image",
        raw_hash=raw_hash,
        captured_at=captured_at,
        paths=paths,
        parser="glm-ocr",
        parser_confidence=0.9,
        sections=[section],
        quality=quality,
    )


def _xml_find_text_attr(root: ET.Element, xpath: str, attr: str) -> str | None:
    found = root.find(xpath)
    if found is None:
        return None
    return found.attrib.get(attr)


def _epub_member_path(opf_path: str, href: str) -> str:
    clean_href, _fragment = urldefrag(href)
    clean_href = unquote(clean_href)
    opf_dir = posixpath.dirname(opf_path.replace("\\", "/"))
    return posixpath.normpath(posixpath.join(opf_dir, clean_href)).lstrip("/")


def _normalize_epub(
    raw_path: Path,
    raw_hash: str,
    captured_at: datetime,
    paths: WorkspacePaths,
) -> NormalizedOutput:
    try:
        with zipfile.ZipFile(raw_path) as zf:
            container = ET.fromstring(zf.read("META-INF/container.xml"))
            opf_path = _xml_find_text_attr(container, ".//{*}rootfile", "full-path")
            if not opf_path:
                raise ValueError("EPUB container does not declare an OPF package")
            opf_root = ET.fromstring(zf.read(opf_path))
            manifest: dict[str, str] = {}
            for item in opf_root.findall(".//{*}manifest/{*}item"):
                item_id = item.attrib.get("id")
                href = item.attrib.get("href")
                if item_id and href:
                    manifest[item_id] = href

            sections: list[_SectionDraft] = []
            for index, itemref in enumerate(opf_root.findall(".//{*}spine/{*}itemref"), start=1):
                idref = itemref.attrib.get("idref")
                href = manifest.get(idref or "")
                if not href:
                    continue
                member = _epub_member_path(opf_path, href)
                html = zf.read(member).decode("utf-8", errors="replace")
                parser = _MarkdownHTMLParser()
                parser.feed(html)
                markdown = parser.markdown()
                title_match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
                title = title_match.group(1).strip() if title_match else Path(href).stem
                sections.append(
                    _SectionDraft(
                        section_id=f"{index:03d}",
                        title=title,
                        body=markdown if markdown.startswith("#") else f"# {title}\n\n{markdown}",
                        locator=f"epub spine {index}",
                        confidence=1.0,
                    )
                )
    except Exception as exc:
        dest = paths.failed / "technical-failures" / f"{_slug_from_raw(raw_path)}.md"
        body = (
            _frontmatter(raw_path, "epub", raw_hash, captured_at, "epub", 0.0, paths.root)
            + f"# EPUB parsing failed\n\nError: {exc}\n"
        )
        _write(dest, body)
        return NormalizedOutput(ok=False, output_path=dest, routed_to="failed", parser="epub", error=str(exc))

    if not sections:
        dest = paths.review / "low-confidence-normalization" / f"{_slug_from_raw(raw_path)}.md"
        body = (
            _frontmatter(raw_path, "epub", raw_hash, captured_at, "epub", 0.2, paths.root)
            + "# Low-confidence EPUB normalization\n\nNo readable spine sections were extracted.\n"
        )
        _write(dest, body)
        return NormalizedOutput(ok=True, output_path=dest, routed_to="review", parser="epub")

    quality = {
        "total_chars": sum(len(s.body) for s in sections),
        "ocr_pages": 0,
        "warnings": [],
    }
    return _write_package(
        raw_path=raw_path,
        category="epub",
        raw_hash=raw_hash,
        captured_at=captured_at,
        paths=paths,
        parser="epub",
        parser_confidence=1.0,
        sections=sections,
        quality=quality,
    )


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
    if category == "epub":
        return _normalize_epub(raw_path, raw_hash, captured_at, paths)
    if category == "image":
        return _normalize_image(raw_path, raw_hash, captured_at, paths)
    return _normalize_unknown(raw_path, raw_hash, captured_at, paths)
