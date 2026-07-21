from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypeVar

from talamus.services.result import ServiceResult

T = TypeVar("T")


@dataclass(frozen=True)
class IntegrationReport:
    root: str
    mcp_config_path: str
    mcp_installed: bool
    hook_command: str
    cursor_installed: bool
    codex_on_path: bool
    opencode_on_path: bool
    openclaw_on_path: bool
    hook_installed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class McpInstallResult:
    config_path: str
    server_name: str
    command: str
    args: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HookSnippet:
    command: str
    settings: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HookInstallResult:
    settings_path: str
    command: str
    installed: bool
    already_installed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def inspect_integrations(root: str | Path) -> ServiceResult[IntegrationReport]:
    root_path = Path(root)
    try:
        report = IntegrationReport(
            root=str(root_path),
            mcp_config_path=str(_mcp_config_path(root_path)),
            mcp_installed=mcp_installed(root_path),
            hook_command=_hook_command(root_path),
            cursor_installed=cursor_installed(root_path),
            codex_on_path=shutil.which("codex") is not None,
            opencode_on_path=shutil.which("opencode") is not None,
            openclaw_on_path=shutil.which("openclaw") is not None,
            hook_installed=hook_installed(root_path),
        )
    except (OSError, TypeError, ValueError, AttributeError, json.JSONDecodeError) as exc:
        return _integration_error(exc)
    return ServiceResult(
        success=True,
        message="Integration status loaded",
        code="integrations_status_loaded",
        data=report,
    )


def install_mcp_config(root: str | Path) -> ServiceResult[McpInstallResult]:
    """Claude Code reads the project-level `.mcp.json` (Cursor has its own path)."""
    root_path = Path(root)
    return _install_mcp_json(_mcp_config_path(root_path), root_path)


def install_mcp_config_cursor(root: str | Path) -> ServiceResult[McpInstallResult]:
    """Cursor reads `<project>/.cursor/mcp.json` — same shape as `.mcp.json`."""
    root_path = Path(root)
    return _install_mcp_json(root_path / ".cursor" / "mcp.json", root_path)


def install_mcp_config_opencode(root: str | Path) -> ServiceResult[McpInstallResult]:
    """opencode reads `<project>/opencode.json`; its `mcp` section registers
    local servers. Merge-not-clobber and idempotent, like every installer here."""
    root_path = Path(root)
    path = root_path / "opencode.json"
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ServiceResult(
                success=False,
                message=f"cannot parse existing {path.name} — fix or remove it first",
                code="opencode_config_unreadable",
            )
    if not isinstance(data, dict):
        data = {}
    data.setdefault("$schema", "https://opencode.ai/config.json")
    mcp = data.setdefault("mcp", {})
    if not isinstance(mcp, dict):
        return ServiceResult(
            success=False,
            message=f"{path.name} has a non-object `mcp` section — fix it first",
            code="opencode_config_invalid",
        )
    mcp["talamus"] = {"type": "local", "command": ["talamus-mcp"], "enabled": True}
    path.write_text(json.dumps(data, indent=2) + chr(10), encoding="utf-8")
    return ServiceResult(
        success=True,
        message=f"registered talamus in {path.name} (opencode reads it per project)",
        code="mcp_config_installed_opencode",
        data=McpInstallResult(
            config_path=str(path), server_name="talamus", command="talamus-mcp", args=[]
        ),
    )


def install_mcp_config_codex() -> ServiceResult[McpInstallResult]:
    """Codex registers MCP servers GLOBALLY via its own CLI (`codex mcp add`).

    Registered without `--root` on purpose: `talamus-mcp` then resolves the
    brain from the directory codex runs in, so ONE registration serves every
    project. remove-then-add keeps the call idempotent (add rejects duplicates)."""
    codex = shutil.which("codex")  # full path: bare "codex" is an npm .cmd shim on Windows
    if codex is None:
        return ServiceResult(
            success=False,
            message="codex CLI not found on PATH — install codex or skip --agent codex",
            code="codex_not_found",
        )
    try:
        subprocess.run(  # a stale entry is fine to drop; failure here is not an error
            [codex, "mcp", "remove", "talamus"], capture_output=True, text=True, timeout=30
        )
        added = subprocess.run(
            [codex, "mcp", "add", "talamus", "--", "talamus-mcp"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return _integration_error(exc)
    if added.returncode != 0:
        detail = (added.stderr or added.stdout or "").strip()
        return ServiceResult(
            success=False,
            message=f"codex mcp add failed: {detail}",
            code="codex_mcp_add_failed",
        )
    return ServiceResult(
        success=True,
        message="registered talamus with codex (global; the brain resolves per project)",
        code="mcp_config_installed_codex",
        data=McpInstallResult(
            config_path="codex mcp (~/.codex/config.toml)",
            server_name="talamus",
            command="talamus-mcp",
            args=[],
        ),
    )


_OPENCLAW_DEFAULT_TOOLS = (
    "search",
    "read_note",
    "recall",
    "overview",
    "neighbors",
    "history",
    "sources",
    "ontology_status",
    "review_list",
)


def install_mcp_config_openclaw(root: str | Path) -> ServiceResult[McpInstallResult]:
    """Register Talamus in OpenClaw's global MCP registry via its own CLI.

    OpenClaw owns the config format and validation, so use ``openclaw mcp set``
    instead of editing ``~/.openclaw/openclaw.json`` ourselves. The explicit
    root makes the selected project brain stable even when the Gateway starts
    the stdio child from another working directory. Default to a read-oriented
    tool surface; LLM-backed and mutating tools remain an explicit opt-in in
    OpenClaw's MCP settings.
    """
    openclaw = shutil.which("openclaw")
    if openclaw is None:
        return ServiceResult(
            success=False,
            message="openclaw CLI not found on PATH — install OpenClaw or skip --agent openclaw",
            code="openclaw_not_found",
        )
    root_path = Path(root)
    args = ["--root", str(root_path)]
    server_config = {
        "command": "talamus-mcp",
        "args": args,
        "transport": "stdio",
        "toolFilter": {"include": list(_OPENCLAW_DEFAULT_TOOLS)},
    }
    try:
        configured = subprocess.run(
            [
                openclaw,
                "mcp",
                "set",
                "talamus",
                json.dumps(server_config, separators=(",", ":")),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return _integration_error(exc)
    if configured.returncode != 0:
        detail = (configured.stderr or configured.stdout or "").strip()
        return ServiceResult(
            success=False,
            message=f"openclaw mcp set failed: {detail}",
            code="openclaw_mcp_set_failed",
        )
    return ServiceResult(
        success=True,
        message=(
            "registered talamus with openclaw "
            "(global definition, project brain pinned by --root, read-oriented tools by default)"
        ),
        code="mcp_config_installed_openclaw",
        data=McpInstallResult(
            config_path="openclaw mcp (~/.openclaw/openclaw.json)",
            server_name="talamus",
            command="talamus-mcp",
            args=args,
        ),
    )


_MCP_AGENTS = ("auto", "claude", "cursor", "codex", "opencode", "openclaw", "all")
_OPTIONAL_MISSING_CODES = {"codex_not_found", "openclaw_not_found"}


def install_mcp_for_agent(root: str | Path, agent: str = "auto") -> ServiceResult[dict[str, Any]]:
    """One call, every agent (D7.2, the UI side of `talamus mcp install`):
    Claude always, Cursor when named or the project has `.cursor/`, and agent
    CLIs when named or found on PATH. A missing optional CLI is a skip under
    auto/all (reported per-agent, not fatal) but an error when explicitly
    requested — the same contract as the CLI."""
    root_path = Path(root)
    choice = (agent or "auto").strip().lower()
    if choice not in _MCP_AGENTS:
        return ServiceResult(
            success=False,
            message=(
                f"Unknown agent {agent!r} — use auto, claude, cursor, codex, "
                "opencode, openclaw or all"
            ),
            code="mcp_agent_unknown",
        )
    installs: list[tuple[str, Callable[[], ServiceResult[McpInstallResult]]]] = []
    if choice in ("auto", "claude", "all"):
        installs.append(("claude", lambda: install_mcp_config(root_path)))
    if choice in ("cursor", "all") or (choice == "auto" and (root_path / ".cursor").is_dir()):
        installs.append(("cursor", lambda: install_mcp_config_cursor(root_path)))
    if choice in ("codex", "all") or (choice == "auto" and shutil.which("codex") is not None):
        installs.append(("codex", install_mcp_config_codex))
    if choice in ("opencode", "all") or (choice == "auto" and shutil.which("opencode") is not None):
        installs.append(("opencode", lambda: install_mcp_config_opencode(root_path)))
    if choice in ("openclaw", "all") or (choice == "auto" and shutil.which("openclaw") is not None):
        installs.append(("openclaw", lambda: install_mcp_config_openclaw(root_path)))
    results: dict[str, ServiceResult[McpInstallResult]] = {}
    for name, run in installs:
        results[name] = run()
    failed = [
        name
        for name, result in results.items()
        if not result.success
        and not (choice not in ("codex", "openclaw") and result.code in _OPTIONAL_MISSING_CODES)
    ]
    installed = [name for name, result in results.items() if result.success]
    data = {
        "agent": choice,
        "results": {name: result.to_dict() for name, result in results.items()},
    }
    if failed:
        return ServiceResult(
            success=False,
            message=f"MCP install failed for: {', '.join(failed)}",
            code="mcp_agents_failed",
            data=data,
        )
    return ServiceResult(
        success=True,
        message=f"MCP configured for: {', '.join(installed) or 'no agent detected'}",
        code="mcp_agents_installed",
        data=data,
    )


def _install_mcp_json(config_path: Path, root_path: Path) -> ServiceResult[McpInstallResult]:
    args = ["--root", str(root_path)]
    try:
        data = _read_json_object(config_path)
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
            data["mcpServers"] = servers
        servers["talamus"] = {
            "command": "talamus-mcp",
            "args": args,
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (OSError, TypeError, ValueError, AttributeError, json.JSONDecodeError) as exc:
        return _integration_error(exc)
    return ServiceResult(
        success=True,
        message=f"wrote talamus MCP server to {config_path}",
        code="mcp_config_installed",
        data=McpInstallResult(
            config_path=str(config_path),
            server_name="talamus",
            command="talamus-mcp",
            args=args,
        ),
    )


def build_hook_snippet(root: str | Path) -> ServiceResult[HookSnippet]:
    root_path = Path(root)
    command = _hook_command(root_path)
    settings = {
        "hooks": {
            "SessionEnd": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": command,
                        }
                    ]
                }
            ]
        }
    }
    return ServiceResult(
        success=True,
        message="Hook snippet built",
        code="hook_snippet_built",
        data=HookSnippet(command=command, settings=settings),
    )


def install_capture_hook(root: str | Path) -> ServiceResult[HookInstallResult]:
    """Write the SessionEnd capture hook into <root>/.claude/settings.json,
    merging with whatever is already there. Consent is the caller's job:
    interfaces call this only after the user said yes (D6)."""
    root_path = Path(root)
    settings_path = _claude_settings_path(root_path)
    command = _hook_command(root_path)
    try:
        data = _read_json_object(settings_path)
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            hooks = {}
            data["hooks"] = hooks
        session_end = hooks.get("SessionEnd")
        if not isinstance(session_end, list):
            session_end = []
            hooks["SessionEnd"] = session_end
        if _capture_hook_present(session_end):
            return ServiceResult(
                success=True,
                message=f"capture hook already installed in {settings_path}",
                code="hook_already_installed",
                data=HookInstallResult(
                    settings_path=str(settings_path),
                    command=command,
                    installed=False,
                    already_installed=True,
                ),
            )
        session_end.append({"hooks": [{"type": "command", "command": command}]})
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (OSError, TypeError, ValueError, AttributeError, json.JSONDecodeError) as exc:
        return _integration_error(exc)
    return ServiceResult(
        success=True,
        message=f"capture hook installed (SessionEnd) in {settings_path}",
        code="hook_installed",
        data=HookInstallResult(
            settings_path=str(settings_path),
            command=command,
            installed=True,
            already_installed=False,
        ),
    )


def _mcp_config_path(root: Path) -> Path:
    return root / ".mcp.json"


def _claude_settings_path(root: Path) -> Path:
    return root / ".claude" / "settings.json"


def _capture_hook_present(session_end: list[Any]) -> bool:
    for entry in session_end:
        if not isinstance(entry, dict):
            continue
        nested = entry.get("hooks")
        if not isinstance(nested, list):
            continue
        for hook in nested:
            if isinstance(hook, dict) and "talamus hook-run" in str(hook.get("command", "")):
                return True
    return False


def _hook_command(root: Path) -> str:
    # Quoted: the hook line is run by a shell, and roots with spaces are common.
    return f'talamus hook-run --root "{root}"'


def _read_json_object(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def mcp_installed(root: Path) -> bool:
    return _mcp_json_has_talamus(_mcp_config_path(root))


def cursor_installed(root: Path) -> bool:
    """Cursor's `.cursor/mcp.json` carries the talamus server (same shape as `.mcp.json`)."""
    return _mcp_json_has_talamus(root / ".cursor" / "mcp.json")


def hook_installed(root: Path) -> bool:
    """The SessionEnd capture hook is present in `<root>/.claude/settings.json`."""
    hooks = _read_json_object(_claude_settings_path(root)).get("hooks")
    session_end = hooks.get("SessionEnd") if isinstance(hooks, dict) else None
    return isinstance(session_end, list) and _capture_hook_present(session_end)


def _mcp_json_has_talamus(config_path: Path) -> bool:
    servers = _read_json_object(config_path).get("mcpServers")
    if not isinstance(servers, dict):
        return False
    talamus = servers.get("talamus")
    return isinstance(talamus, dict) and talamus.get("command") == "talamus-mcp"


def _integration_error(exc: Exception) -> ServiceResult[T]:
    return ServiceResult(
        success=False,
        message=f"Integration service error: {exc}",
        code="integration_service_error",
    )
