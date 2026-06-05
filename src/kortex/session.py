from __future__ import annotations

import hashlib
import json

from kortex.normalize import NormalizedPackage, NormalizedSection


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                btype = block.get("type")
                if btype == "text":
                    parts.append(str(block.get("text", "")).strip())
                elif btype == "tool_use":
                    name = block.get("name", "tool")
                    inp = block.get("input", {})
                    hint = ""
                    if isinstance(inp, dict):
                        hint = str(inp.get("file_path") or inp.get("path") or inp.get("command") or "")[:60]
                    parts.append(f"[tool {name}: {hint}]".strip())
                elif btype == "tool_result":
                    parts.append("[risultato tool]")
            elif isinstance(block, str):
                parts.append(block.strip())
        return " ".join(part for part in parts if part).strip()
    return str(content).strip()


def _compress_message(obj: dict) -> str:
    role = obj.get("role") or obj.get("type") or "?"
    text = _content_to_text(obj.get("content", obj.get("text", "")))
    return f"{role}: {text}" if text else ""


def _compress_jsonl(lines: list[str]) -> str | None:
    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        return ""
    try:
        json.loads(non_empty[0])
    except json.JSONDecodeError:
        return None
    out: list[str] = []
    for line in non_empty:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = _compress_message(obj)
        if message:
            out.append(message)
    return "\n".join(out)


def compress_transcript(text: str) -> str:
    """Comprime un transcript: se JSONL, estrae i turni e compatta i blocchi tool; altrimenti passthrough."""
    compressed = _compress_jsonl(text.splitlines())
    if compressed is not None:
        return compressed
    return text.strip()


def session_worth_remembering(transcript: str, diff: str = "", min_chars: int = 400) -> bool:
    """Gate euristico (niente LLM): vale se c'è un diff non vuoto o un transcript sostanzioso."""
    if diff.strip():
        return True
    return len(transcript.strip()) >= min_chars


def normalize_session(raw_path: str, transcript: str, diff: str = "") -> NormalizedPackage:
    convo = compress_transcript(transcript)
    payload = convo + ("\n\n" + diff if diff.strip() else "")
    source_hash = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    sections = [NormalizedSection("001", "Conversazione", convo)]
    if diff.strip():
        sections.append(NormalizedSection("002", "Modifiche", diff.strip()))
    return NormalizedPackage(raw_path, source_hash, sections)
