from __future__ import annotations

import json
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
    root_path = Path(root)
    config_path = _mcp_config_path(root_path)
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
    data = _read_json_object(_mcp_config_path(root))
    servers = data.get("mcpServers")
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
