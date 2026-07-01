"""Repo scan: compile an existing repository into the brain, safely (PRD 9.2/F2).

The flow is *plan first, spend later*: ``build_plan`` walks the tree respecting
``.gitignore`` (common patterns; negations unsupported) and the default excludes
(vendor dirs, caches, binaries, lockfiles, secret-like files), sniffs likely
secrets in content, and produces a dry-run plan with size/token/call estimates —
zero LLM cost. ``execute_plan`` then runs as a persistent, resumable job: docs go
through the normal extractor, code files become deterministic *digests* (path,
public signatures, docstrings) compiled with a code-aware prompt preamble into
Module/Public API/decision-type notes. Content sent to the LLM is redacted first;
the plan stops for explicit approval when likely secrets are found (F2.10).
"""

from __future__ import annotations

import ast
import fnmatch
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

from talamus.adapters.llm import LLMProvider
from talamus.ingest import ingest_text
from talamus.jobs import JobRecord, JobStore, run_items
from talamus.paths import TalamusPaths
from talamus.redact import find_secrets, is_secret_file, redact
from talamus.routing import StaticRouter

DOC_EXTS = {".md", ".markdown", ".rst", ".txt", ".docx", ".pdf", ".html", ".htm"}
CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".c", ".h",
    ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".scala", ".sh", ".ps1", ".sql",
    ".toml", ".yaml", ".yml", ".ini", ".cfg",
}  # fmt: skip
PROFILES = ("docs", "code", "all")

DEFAULT_EXCLUDE_DIRS = {
    ".git", ".talamus", ".claude", ".worktrees", "node_modules", ".venv", "venv",
    "env", "dist", "build", "target", "site", "__pycache__", ".mypy_cache",
    ".ruff_cache", ".pytest_cache", ".idea", ".vscode", ".egg-info",
}  # fmt: skip
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock",
    "cargo.lock", "gemfile.lock", "composer.lock",
}  # fmt: skip
PER_FILE_MAX_BYTES = 1_000_000

CODE_PREAMBLE = (
    "ADDITIONAL INSTRUCTIONS FOR SOURCE CODE: the text is a digest of a code module "
    "(path, public signatures, docstrings). Do NOT treat it as prose: produce few "
    "notes of the types Module (the module's responsibility), Public API (what it "
    "exposes and what for), and Architecture Decision / Integration Point / Risk "
    "only when the code truly reveals them. No notes for private functions, no "
    "copied code beyond short signatures. Include 'code' among each note's tags.\n\n"
)


@dataclass
class ScanPlan:
    root: str
    profile: str
    included: list[dict] = field(default_factory=list)  # {path, category, bytes}
    excluded: list[dict] = field(default_factory=list)  # {path, reason}
    total_bytes: int = 0
    est_tokens: int = 0
    est_llm_calls: int = 0
    secret_flags: list[dict] = field(default_factory=list)  # {path, kind, line}
    git: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _load_gitignore(root: Path) -> list[str]:
    path = root / ".gitignore"
    if not path.is_file():
        return []
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue  # negations unsupported in this matcher (documented)
        patterns.append(line)
    return patterns


def _is_ignored(rel: PurePosixPath, patterns: list[str]) -> bool:
    """Light .gitignore matching: name, any path segment, or full-path glob."""
    text = str(rel)
    for raw in patterns:
        pattern = raw.strip("/")
        if not pattern:
            continue
        if (
            fnmatch.fnmatch(rel.name, pattern)
            or fnmatch.fnmatch(text, pattern)
            or fnmatch.fnmatch(text, f"*/{pattern}")
            or any(fnmatch.fnmatch(part, pattern) for part in rel.parts)
        ):
            return True
    return False


def _git_info(root: Path) -> dict:
    try:

        def _run(*args: str) -> str:
            out = subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, timeout=10
            )
            return out.stdout.strip()

        commit = _run("rev-parse", "--short", "HEAD")
        if not commit:
            return {}
        return {
            "commit": commit,
            "branch": _run("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(_run("status", "--porcelain")),
        }
    except (subprocess.SubprocessError, OSError):
        return {}


def _looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\x00" in handle.read(1024)
    except OSError:
        return True


def _category(path: Path, profile: str) -> str | None:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if profile in ("docs", "all") and suffix in DOC_EXTS:
        return "docs"
    if profile in ("code", "all"):
        if suffix in CODE_EXTS or name in ("makefile", "dockerfile"):
            return "code"
        if profile == "code" and suffix in DOC_EXTS and name.startswith("readme"):
            return "docs"
    return None


def build_plan(
    root: Path,
    profile: str = "all",
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_files: int | None = None,
) -> ScanPlan:
    """Walk the repo and produce the dry-run plan. No LLM calls, no writes."""
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of {PROFILES}, got {profile!r}")
    root = root.resolve()
    patterns = _load_gitignore(root)
    plan = ScanPlan(root=str(root), profile=profile, git=_git_info(root))
    extra_exclude = list(exclude or [])
    only_include = list(include or [])
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = PurePosixPath(Path(dirpath).relative_to(root).as_posix())
        kept_dirs = []
        for d in dirnames:
            rel_sub = rel_dir / d if str(rel_dir) != "." else PurePosixPath(d)
            if d.lower() in DEFAULT_EXCLUDE_DIRS or d.lower().endswith(".egg-info"):
                continue  # vendor/cache dirs are pruned silently, like .git
            if _is_ignored(rel_sub, patterns):
                plan.excluded.append({"path": f"{rel_sub}/", "reason": ".gitignore"})
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs
        for filename in sorted(filenames):
            full = Path(dirpath) / filename
            rel = PurePosixPath(full.relative_to(root).as_posix())
            rel_str = str(rel)
            if only_include and not any(fnmatch.fnmatch(rel_str, p) for p in only_include):
                continue
            if any(
                fnmatch.fnmatch(rel_str, p) or fnmatch.fnmatch(rel.name, p) for p in extra_exclude
            ):
                plan.excluded.append({"path": rel_str, "reason": "--exclude"})
                continue
            if _is_ignored(rel, patterns):
                plan.excluded.append({"path": rel_str, "reason": ".gitignore"})
                continue
            if is_secret_file(full):
                plan.excluded.append({"path": rel_str, "reason": "secret-like file"})
                continue
            if filename.lower() in LOCKFILES:
                plan.excluded.append({"path": rel_str, "reason": "lockfile"})
                continue
            category = _category(full, profile)
            if category is None:
                plan.excluded.append({"path": rel_str, "reason": "unsupported type"})
                continue
            try:
                size = full.stat().st_size
            except OSError:
                plan.excluded.append({"path": rel_str, "reason": "unreadable"})
                continue
            if size > PER_FILE_MAX_BYTES:
                plan.excluded.append({"path": rel_str, "reason": "over size threshold"})
                continue
            if _looks_binary(full):
                plan.excluded.append({"path": rel_str, "reason": "binary"})
                continue
            if max_files is not None and len(plan.included) >= max_files:
                plan.excluded.append({"path": rel_str, "reason": "--max-files"})
                continue
            plan.included.append({"path": rel_str, "category": category, "bytes": size})
            plan.total_bytes += size
            if full.suffix.lower() not in (".pdf", ".docx"):
                try:
                    text = full.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
                for finding in find_secrets(text):
                    plan.secret_flags.append({"path": rel_str, **finding})
    plan.est_tokens = plan.total_bytes // 4
    plan.est_llm_calls = len(plan.included)
    return plan


def format_plan(plan: ScanPlan) -> str:
    by_category: dict[str, int] = {}
    for entry in plan.included:
        by_category[entry["category"]] = by_category.get(entry["category"], 0) + 1
    categories = ", ".join(f"{n} {cat}" for cat, n in sorted(by_category.items())) or "0"
    lines = [
        f"Scan plan for {plan.root}",
        f"Profile     {plan.profile}",
        f"Files       {len(plan.included)} included ({categories}), {len(plan.excluded)} skipped",
        f"Estimate    ~{plan.est_tokens:,} input tokens, {plan.est_llm_calls} LLM calls",
        "Cost        provider does not expose pricing; estimates are token-based",
    ]
    if plan.git:
        dirty = " (dirty)" if plan.git.get("dirty") else ""
        lines.append(f"Git         {plan.git.get('branch')} @ {plan.git.get('commit')}{dirty}")
    if plan.secret_flags:
        flagged = sorted({f["path"] for f in plan.secret_flags})
        shown = ", ".join(flagged[:5])
        lines.append(f"Safety      {len(flagged)} file(s) with likely secrets: {shown}")
        lines.append("            content will be REDACTED; pass --allow-secrets to proceed")
    lines.append("")
    lines.append("Run\n  talamus scan . --yes")
    return "\n".join(lines)


def _python_digest(text: str, rel_path: str) -> str | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    lines = [f"Modulo: {rel_path}"]
    doc = ast.get_docstring(tree)
    if doc:
        lines.append(f"Docstring: {doc.strip()}")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name.startswith("_"):
                continue
            kind = "class" if isinstance(node, ast.ClassDef) else "def"
            node_doc = ast.get_docstring(node) or ""
            first = node_doc.strip().splitlines()[0] if node_doc.strip() else ""
            lines.append(f"{kind} {node.name}: {first}")
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not sub.name.startswith("_"):
                            lines.append(f"  def {node.name}.{sub.name}")
    return "\n".join(lines)


_SIGNATURE_LINE = re.compile(
    r"^\s*(def |class |function |func |fn |public |export |interface |struct |impl )"
)


def code_digest(full: Path, rel_path: str) -> str:
    """Deterministic digest of a code file: path + public signatures + docstrings."""
    text = full.read_text(encoding="utf-8", errors="replace")
    if full.suffix.lower() == ".py":
        digest = _python_digest(text, rel_path)
        if digest is not None:
            return digest
    lines = [f"Modulo: {rel_path}"]
    lines += [line.rstrip() for line in text.splitlines()[:30]]
    signatures = [line.rstrip() for line in text.splitlines()[30:] if _SIGNATURE_LINE.match(line)]
    lines += signatures[:40]
    return "\n".join(lines)[:8000]


def execute_plan(
    paths: TalamusPaths,
    plan: ScanPlan,
    llm: LLMProvider,
    job_record: JobRecord | None = None,
) -> dict:
    """Run the plan as a persistent, resumable job. Per-file failures are recorded,
    never abort the batch; content is redacted before reaching the LLM."""
    store = JobStore(paths)
    record = job_record or store.create("scan", payload=plan.to_dict())
    categories = {entry["path"]: entry["category"] for entry in plan.included}
    root = Path(plan.root)
    commit = plan.git.get("commit", "dirty") if plan.git else "no-git"
    failures: list[dict] = []
    notes_written = 0
    router = StaticRouter(llm)  # scan pins one engine for the whole batch (no per-task tiering)

    def handle(rel_path: str) -> None:
        nonlocal notes_written
        full = root / rel_path
        try:
            if categories.get(rel_path) == "code":
                text = code_digest(full, rel_path)
                preamble = CODE_PREAMBLE
            else:
                header = f"[source: {rel_path} @ {commit}]\n\n"
                text = header + full.read_text(encoding="utf-8", errors="replace")
                preamble = ""
            redacted, n_secrets = redact(text)
            if n_secrets:
                store.log(record.job_id, f"{rel_path}: {n_secrets} redaction(s) applied")
            name = rel_path.replace("/", "-").replace("\\", "-")
            result = ingest_text(paths, redacted, router, name=name, preamble=preamble)
            notes_written += result["notes_written"]
        except Exception as exc:  # record, don't abort the batch
            failures.append({"path": rel_path, "error": str(exc)})
            store.log(record.job_id, f"{rel_path}: FAILED {exc}")

    final = run_items(store, record, [e["path"] for e in plan.included], handle, stage="scan")
    final.result = {
        "notes_written": notes_written,
        "failed": failures,
        "files": len(plan.included),
    }
    store.save(final)
    return {"job_id": final.job_id, "state": final.state, **final.result}


def plan_from_record(record: JobRecord) -> ScanPlan:
    """Rebuild a plan from a persisted job payload (for `talamus jobs resume`)."""
    data = dict(record.payload)
    known = {f for f in ScanPlan.__dataclass_fields__}
    return ScanPlan(**{k: v for k, v in data.items() if k in known})
