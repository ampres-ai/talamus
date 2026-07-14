"""FastAPI bridge: one endpoint per services/ call. The response body is the service
ServiceResult (success/message/code/data) as JSON. No business logic here — the same
seam rule the CLI and MCP follow."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from talamus.config import load_or_default
from talamus.errors import EngineFailed, EngineNotFound
from talamus.ingest import pending_captures, retry_pending_captures
from talamus.paths import TalamusPaths
from talamus.registry import load_registry, register_brain, select_brain
from talamus.routing import EngineRouter, TaskClass
from talamus.services.ask import ask_brain
from talamus.services.brains import init_brain, list_brains, set_registered_brain_flags
from talamus.services.diagnostics import inspect_diagnostics, reindex_brain
from talamus.services.engines import probe_engine, update_engine_settings
from talamus.services.importer import import_markdown_vault
from talamus.services.ingestion import ingest_raw_text, preview_ingest, run_ingest
from talamus.services.integrations import (
    inspect_integrations,
    install_capture_hook,
    install_mcp_for_agent,
)
from talamus.services.library import list_library_notes
from talamus.services.ontology import (
    apply_ontology_candidate,
    get_ontology_status,
    list_ontology_candidates,
    reject_ontology_candidate,
)
from talamus.services.query import read_note, search_brain
from talamus.services.readiness import inspect_readiness
from talamus.services.review import (
    apply_review_item,
    list_review_items,
    reject_review_item,
)
from talamus.services.scan import preview_scan, run_scan
from talamus.services.verification import verify_single_note
from talamus.smartsearch import expand_query
from talamus.webapi.graph_layout import compute_note_graph

_STATIC = Path(__file__).parent / "static"
_PLACEHOLDER = "<!doctype html><title>Talamus</title><h1>Talamus web workbench</h1>"
_NO_ENGINE = {
    "success": False,
    "code": "import_no_engine",
    "message": "No engine connected — run `talamus setup` to connect one before importing.",
}


def _router(root: Path) -> EngineRouter:
    """Engine router for the brain. Probes the configured provider eagerly (one
    for_task call) so the import/scan endpoints can keep returning the friendly
    no-engine payload BEFORE starting a long job, as they did with build_provider."""
    router = EngineRouter(load_or_default(TalamusPaths(root).config_path))
    router.for_task(TaskClass.EXTRACTION)  # raises EngineNotFound if misconfigured
    return router


def _brain_summary(root_path: Path) -> dict:
    """A light description of the active brain (the one the workbench is pointed at)."""
    name = root_path.name
    try:
        info = load_registry().by_path(root_path)
        if info is not None:
            name = info.name
    except (OSError, TypeError, ValueError, AttributeError):
        pass
    notes_dir = root_path / "notes"
    notes = sum(1 for p in notes_dir.glob("*.md") if p.is_file()) if notes_dir.is_dir() else 0
    return {
        "path": str(root_path),
        "name": name,
        "initialized": (root_path / "talamus.json").is_file(),
        "notes": notes,
    }


_LOCAL_ORIGINS = ("http://127.0.0.1", "http://localhost")


def create_app(root: Path) -> FastAPI:
    app = FastAPI(title="Talamus", docs_url=None, redoc_url=None)
    root = Path(root)

    # --- Local-only workbench guard (see SECURITY.md) ----------------------------
    # The API is served on 127.0.0.1 with no user auth, so a malicious website must
    # not be able to drive it. Three layers: (1) the Host header must be local
    # (a DNS-rebinding page sends `Host: evil.test` and is rejected here); (2) any
    # request carrying a non-local Origin/Referer is refused; (3) every /api/* call
    # must carry a per-launch token that only the served SPA can read — a
    # cross-origin page cannot read the token out of index.html (CORS blocks the
    # body read), and the custom header forces a preflight that also fails
    # cross-origin. The token is minted per process; a launcher may pin it via
    # TALAMUS_UI_TOKEN (used by tests for determinism).
    ui_token = os.environ.get("TALAMUS_UI_TOKEN") or secrets.token_urlsafe(32)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def _require_local_ui(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin") or request.headers.get("referer") or ""
            if origin and not origin.startswith(_LOCAL_ORIGINS):
                return JSONResponse(
                    {
                        "success": False,
                        "code": "forbidden_origin",
                        "message": "cross-origin request rejected",
                    },
                    status_code=403,
                )
            if not secrets.compare_digest(request.headers.get("x-talamus-ui", ""), ui_token):
                return JSONResponse(
                    {
                        "success": False,
                        "code": "forbidden",
                        "message": "missing or invalid workbench token",
                    },
                    status_code=403,
                )
        return await call_next(request)

    @app.get("/api/readiness")
    def readiness() -> dict:
        report = inspect_readiness(root=str(root))
        return {"success": True, "code": "readiness_loaded", "data": report.to_dict()}

    @app.get("/api/library")
    def library() -> dict:
        return list_library_notes(root).to_dict()

    @app.get("/api/search")
    def search_endpoint(q: str = "", limit: int = 8) -> dict:
        """Instant plain search (zero LLM) for the workbench search bar."""
        if not q.strip():
            return {"success": True, "code": "search_completed", "data": {"hits": []}}
        return search_brain(root, q, limit=limit).to_dict()

    @app.post("/api/search/smart")
    def search_smart(payload: dict | None = None) -> dict:
        """Expand-with-AI search: ONE LLM call (cached per query), then the
        same instant index — the CLI's `search --smart` for the workbench."""
        data = payload or {}
        q = str(data.get("q", "")).strip()
        if not q:
            return {"success": False, "code": "search_query_missing", "message": "Provide a query."}
        try:
            router = _router(root)
            expanded = expand_query(TalamusPaths(root), q, router)
        except EngineNotFound:
            return _NO_ENGINE
        except EngineFailed as exc:
            return {"success": False, "code": "engine_failed", "message": str(exc)}
        result = search_brain(root, f"{q} {expanded}".strip(), limit=int(data.get("limit", 8)))
        out = result.to_dict()
        out["expanded"] = expanded
        return out

    @app.get("/api/captures")
    def captures() -> dict:
        """Sessions parked after an engine failure, waiting for a retry."""
        names = [path.name for path in pending_captures(TalamusPaths(root))]
        return {"success": True, "code": "captures_listed", "data": {"pending": names}}

    @app.post("/api/captures/retry")
    def captures_retry() -> dict:
        """Replay parked captures (talamus hook --retry for the workbench)."""
        try:
            router = _router(root)
        except EngineNotFound:
            return _NO_ENGINE
        outcome = retry_pending_captures(TalamusPaths(root), router)
        return {
            "success": True,
            "code": "captures_retried",
            "message": f"retried {outcome['retried']}, remaining {outcome['remaining']}",
            "data": outcome,
        }

    @app.post("/api/brains/flags")
    def brains_flags(payload: dict | None = None) -> dict:
        """Plain-language brain switches: shared in global searches / private."""
        data = payload or {}
        name = str(data.get("name", "")).strip()
        federated = data.get("federated")
        sensitive = data.get("sensitive")
        return set_registered_brain_flags(
            name,
            federated=federated if isinstance(federated, bool) else None,
            sensitive=sensitive if isinstance(sensitive, bool) else None,
        ).to_dict()

    @app.get("/api/graph")
    def graph() -> dict:
        return {"success": True, "code": "graph_laid_out", "data": compute_note_graph(root)}

    @app.get("/api/note")
    def note(title: str, as_of: str = "") -> dict:
        """Read a note; with as_of (e.g. 2026-01) read it AS IT WAS at that date."""
        return read_note(root, title, as_of=as_of or None).to_dict()

    @app.post("/api/verify")
    def verify_note_endpoint(payload: dict | None = None) -> dict:
        """The verifiability moat in the UI: check one note against its preserved
        source (one LLM call on the quality tier when the source exists)."""
        title = str((payload or {}).get("title", "")).strip()
        if not title:
            return {
                "success": False,
                "code": "verify_title_missing",
                "message": "Provide the note title.",
            }
        try:
            router = _router(root)
        except EngineNotFound:
            return _NO_ENGINE
        return verify_single_note(root, title, router).to_dict()

    @app.post("/api/ask")
    def ask(payload: dict | None = None) -> dict:
        data = payload or {}
        question = str(data.get("question", ""))
        as_of = str(data.get("as_of", "")).strip() or None
        return ask_brain(root, question, as_of=as_of).to_dict()

    @app.get("/api/review")
    def review(status: str = "pending") -> dict:
        return list_review_items(root, status=status).to_dict()

    @app.post("/api/review/{item_id}/apply")
    def review_apply(item_id: str) -> dict:
        return apply_review_item(root, item_id).to_dict()

    @app.post("/api/review/{item_id}/reject")
    def review_reject(item_id: str, payload: dict | None = None) -> dict:
        reason = str((payload or {}).get("reason", ""))
        return reject_review_item(root, item_id, reason).to_dict()

    @app.get("/api/diagnostics")
    def diagnostics() -> dict:
        return inspect_diagnostics(root).to_dict()

    @app.post("/api/reindex")
    def reindex_endpoint() -> dict:
        """Rebuild the derived cache from the Markdown truth (UI parity for
        `talamus reindex`) — the fix for a stale cache, offered from Home."""
        return reindex_brain(root).to_dict()

    @app.get("/api/integrations")
    def integrations() -> dict:
        """MCP + capture-hook status of the active brain (claude/cursor/codex)."""
        return inspect_integrations(root).to_dict()

    @app.post("/api/integrations/mcp")
    def integrations_mcp(payload: dict | None = None) -> dict:
        """Connect agents via MCP: {"agent": "auto|claude|cursor|codex|all"} —
        per-agent results in data.results (S1 middleware guards this POST)."""
        agent = str((payload or {}).get("agent", "auto"))
        return install_mcp_for_agent(root, agent).to_dict()

    @app.post("/api/integrations/hook")
    def integrations_hook() -> dict:
        """Install the SessionEnd capture hook. Consent is the UI's job (D6): the
        workbench shows the privacy-contract copy and calls this only after the
        user said yes — the endpoint just installs (merge + idempotent)."""
        return install_capture_hook(root).to_dict()

    @app.post("/api/engines/probe")
    def engines_probe(payload: dict | None = None) -> dict:
        """One tiny live completion for {"engine": "<provider>"}: verified/error,
        the shared per-engine hint, and limit_reached — the honest on-demand
        quota check (an exhausted limit surfaces the moment it bites)."""
        engine = str((payload or {}).get("engine", ""))
        return probe_engine(root, engine).to_dict()

    @app.post("/api/engines/select")
    def engines_select(payload: dict | None = None) -> dict:
        """Switch the active engine for this brain: {"engine": "<provider>",
        "model"?: "<model>"}. Writes talamus.json — the CLI and every future
        LLM call for this brain then use it. UI parity for `talamus setup
        --engine`."""
        data = payload or {}
        provider = str(data.get("engine", "")).strip() or None
        model = data.get("model")
        return update_engine_settings(
            root,
            provider=provider,
            model=str(model) if model is not None else None,
        ).to_dict()

    @app.get("/api/brains")
    def brains() -> dict:
        return list_brains().to_dict()

    @app.get("/api/active")
    def active() -> dict:
        return {"success": True, "code": "brain_active", "data": _brain_summary(root)}

    @app.post("/api/active")
    def set_active(payload: dict | None = None) -> dict:
        """Switch the brain the workbench is pointed at (Obsidian-style vault switch).
        Accepts a registered brain {name} or an arbitrary {path}; persists the choice
        in the registry. Every view re-reads the new brain on the next request."""
        nonlocal root
        data = payload or {}
        name = str(data.get("name", "")).strip()
        path = str(data.get("path", "")).strip()
        try:
            if name:
                info = load_registry().by_name(name)
                if info is None:
                    return {
                        "success": False,
                        "code": "brain_not_found",
                        "message": f"No brain named {name!r}",
                    }
                target = Path(info.root())
                select_brain(name)
            elif path:
                target = Path(path).expanduser()
                if not target.is_dir():
                    return {
                        "success": False,
                        "code": "brain_path_missing",
                        "message": f"Folder not found: {path}",
                    }
                if not (target / "talamus.json").is_file():
                    return {
                        "success": False,
                        "code": "brain_not_initialized",
                        "message": "No talamus.json here — create a new brain instead.",
                    }
                target = target.resolve()
                registry = load_registry()
                existing = registry.by_path(target)
                chosen = existing if existing is not None else register_brain(target)
                select_brain(chosen.name)
            else:
                return {
                    "success": False,
                    "code": "brain_target_missing",
                    "message": "Provide a brain name or a folder path.",
                }
        except (OSError, TypeError, ValueError, AttributeError) as exc:
            return {"success": False, "code": "brain_switch_error", "message": str(exc)}
        root = target
        return {"success": True, "code": "brain_activated", "data": _brain_summary(root)}

    @app.post("/api/brains/init")
    def brains_init(payload: dict | None = None) -> dict:
        """Create + initialize a brand-new brain at a folder, then switch to it."""
        nonlocal root
        data = payload or {}
        path = str(data.get("path", "")).strip()
        name = str(data.get("name", "")).strip() or None
        if not path:
            return {
                "success": False,
                "code": "brain_target_missing",
                "message": "Provide a folder path for the new brain.",
            }
        result = init_brain(Path(path).expanduser(), name=name)
        if result.success:
            root = Path(path).expanduser().resolve()
        return result.to_dict()

    @app.post("/api/import/preview")
    def import_preview(payload: dict | None = None) -> dict:
        target = str((payload or {}).get("target", ""))
        return preview_ingest(root, target).to_dict()

    @app.post("/api/import/run")
    def import_run(payload: dict | None = None) -> dict:
        data = payload or {}
        target = str(data.get("target", ""))
        confirmed = bool(data.get("confirmed", False))
        try:
            router = _router(root)
        except EngineNotFound:
            return _NO_ENGINE
        return run_ingest(root, target, router, confirmed=confirmed).to_dict()

    @app.post("/api/import/text")
    def import_text(payload: dict | None = None) -> dict:
        text = str((payload or {}).get("text", ""))
        if not text.strip():
            return {"success": False, "code": "import_empty", "message": "Paste some text first."}
        try:
            router = _router(root)
        except EngineNotFound:
            return _NO_ENGINE
        return ingest_raw_text(root, text, router).to_dict()

    @app.post("/api/import/vault")
    def import_vault_endpoint(payload: dict | None = None) -> dict:
        """Import a Markdown/Obsidian vault 1:1 (no LLM, no engine needed)."""
        directory = str((payload or {}).get("directory", "")).strip()
        if not directory:
            return {
                "success": False,
                "code": "vault_target_missing",
                "message": "Provide the vault folder path.",
            }
        return import_markdown_vault(root, directory).to_dict()

    @app.post("/api/scan/preview")
    def scan_preview_endpoint(payload: dict | None = None) -> dict:
        target = str((payload or {}).get("target", ""))
        return preview_scan(root, target).to_dict()

    @app.post("/api/scan/run")
    def scan_run_endpoint(payload: dict | None = None) -> dict:
        data = payload or {}
        target = str(data.get("target", ""))
        confirmed = bool(data.get("confirmed", False))
        allow_secrets = bool(data.get("allow_secrets", False))
        try:
            router = _router(root)
        except EngineNotFound:
            return _NO_ENGINE
        return run_scan(
            root,
            target,
            router,
            confirmed=confirmed,
            allow_secrets=allow_secrets,
        ).to_dict()

    @app.get("/api/ontology/status")
    def ontology_status() -> dict:
        return get_ontology_status(root).to_dict()

    @app.get("/api/ontology/types")
    def ontology_types(status: str = "candidate") -> dict:
        return list_ontology_candidates(root, status=status).to_dict()

    @app.post("/api/ontology/{type_id}/promote")
    def ontology_promote(type_id: str) -> dict:
        return apply_ontology_candidate(root, type_id, force=True).to_dict()

    @app.post("/api/ontology/{type_id}/reject")
    def ontology_reject(type_id: str, payload: dict | None = None) -> dict:
        reason = str((payload or {}).get("reason", ""))
        return reject_ontology_candidate(root, type_id, reason=reason).to_dict()

    def _with_token(html: str) -> str:
        # Inject the per-launch token so the SPA can send it on /api calls. A
        # cross-origin page cannot read this HTML body (CORS), so it cannot steal it.
        tag = f'<meta name="talamus-ui-token" content="{ui_token}">'
        return html.replace("</head>", f"{tag}</head>", 1) if "</head>" in html else tag + html

    index = _STATIC / "index.html"
    if index.is_file():
        app.mount("/assets", StaticFiles(directory=_STATIC / "assets"), name="assets")

        @app.get("/", response_class=HTMLResponse)
        def root_page() -> str:
            return _with_token(index.read_text(encoding="utf-8"))
    else:

        @app.get("/", response_class=HTMLResponse)
        def root_page() -> str:
            return _with_token(_PLACEHOLDER)

    return app
