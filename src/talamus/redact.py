"""Secret detection and redaction for repo scans.

Two layers of defense before any content reaches a remote LLM:

- *file-level*: secret-like files (``.env``, key material, credential stores) are
  excluded from scans by name, always;
- *content-level*: likely secrets inside otherwise-fine files are detected and
  replaced with ``[REDACTED:<kind>]`` markers; if any are found the scan must
  stop and ask for explicit approval (or a local provider).

Deterministic regex patterns only — no network, no heuristics that phone home.
Logs must never include the matched values.
"""

from __future__ import annotations

import re
from pathlib import Path

_SECRET_FILENAMES = (
    ".env",
    ".envrc",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "service-account.json",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
)
_SECRET_SUFFIXES = (".pem", ".key", ".pfx", ".p12", ".keystore", ".jks")
_SECRET_PREFIXES = ("id_rsa", "id_ed25519", "id_dsa", ".env.")

PATTERNS: dict[str, re.Pattern[str]] = {
    "aws-access-key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private-key-block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "bearer-token": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*", re.IGNORECASE),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "generic-assignment": re.compile(
        r"""(?ix)\b(api[_-]?key|secret|token|passwd|password|client[_-]?secret)\b
            \s*[:=]\s*["']?[A-Za-z0-9_\-./+]{12,}["']?"""
    ),
}


def is_secret_file(path: Path) -> bool:
    """Excluded-by-name check: these files never enter a scan (F2.8)."""
    name = path.name.lower()
    if name in _SECRET_FILENAMES:
        return True
    if any(name.startswith(prefix) for prefix in _SECRET_PREFIXES):
        return True
    return path.suffix.lower() in _SECRET_SUFFIXES


def find_secrets(text: str) -> list[dict]:
    """Likely secrets in ``text``: kind + line number, never the value itself."""
    findings: list[dict] = []
    for kind, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append({"kind": kind, "line": line})
    return findings


def redact(text: str) -> tuple[str, int]:
    """Replace likely secrets with ``[REDACTED:<kind>]``. Returns (text, count)."""
    total = 0
    for kind, pattern in PATTERNS.items():
        text, n = pattern.subn(f"[REDACTED:{kind}]", text)
        total += n
    return text, total
