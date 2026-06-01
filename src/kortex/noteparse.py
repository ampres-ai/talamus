from __future__ import annotations

import re

_KEY = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
_ITEM = re.compile(r"^\s+-\s+(.*)$")
_HEADING = re.compile(r"^##\s+(.+)$")
_H1 = re.compile(r"^#\s+(.+)$")


def _split_frontmatter(text: str) -> tuple[list[str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1 :])
    return [], text


def parse_note_markdown(text: str) -> dict:
    """Estrae dai .md i campi che l'umano puo' modificare a mano.

    Ignora di proposito provenienza/confidenza (campi 'macchina' tenuti nella cache).
    """
    fm_lines, body = _split_frontmatter(text)
    scalars: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    current_list: str | None = None
    for line in fm_lines:
        if not line.startswith((" ", "\t")):
            key_match = _KEY.match(line)
            if key_match:
                key, value = key_match.group(1), key_match.group(2).strip()
                if key in ("aliases", "tags"):
                    current_list = key
                    lists[key] = []
                    if value and value != "[]":
                        lists[key].append(value)
                else:
                    current_list = None
                    if key in ("id", "title") and value:
                        scalars[key] = value
                continue
        item_match = _ITEM.match(line)
        if item_match and current_list is not None:
            value = item_match.group(1).strip()
            if value and value != "[]":
                lists[current_list].append(value)

    summary = ""
    body_sections: dict[str, str] = {}
    title_h1 = ""
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal summary
        if current_heading is None:
            return
        content = "\n".join(buffer).strip()
        name = current_heading.strip()
        if name.lower() == "summary":
            summary = content
        elif name.lower() == "related":
            return
        else:
            body_sections[name.lower().replace(" ", "_")] = content

    for line in body.splitlines():
        if _HEADING.match(line):
            flush()
            current_heading = _HEADING.match(line).group(1)
            buffer = []
            continue
        h1 = _H1.match(line)
        if h1 and not line.startswith("##"):
            title_h1 = h1.group(1).strip()
            continue
        buffer.append(line)
    flush()

    return {
        "id": scalars.get("id", ""),
        "title": scalars.get("title", title_h1),
        "aliases": lists.get("aliases", []),
        "tags": lists.get("tags", []),
        "summary": summary,
        "body_sections": body_sections,
    }
