"""FastAPI bridge: one endpoint per services/ call. The response body is the service
ServiceResult (success/message/code/data) as JSON. No business logic here — the same
seam rule the CLI and MCP follow."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from talamus.adapters.llm import LLMProvider, build_provider
from talamus.config import load_or_default
from talamus.errors import EngineNotFound
from talamus.paths import TalamusPaths
from talamus.services.ask import ask_brain
from talamus.services.brains import list_brains
from talamus.services.diagnostics import inspect_diagnostics
from talamus.services.ingestion import ingest_raw_text, preview_ingest, run_ingest
from talamus.services.library import list_library_notes
from talamus.services.ontology import (
    apply_ontology_candidate,
    get_ontology_status,
    list_ontology_candidates,
    reject_ontology_candidate,
)
from talamus.services.query import read_note
from talamus.services.readiness import inspect_readiness
from talamus.services.review import (
    apply_review_item,
    list_review_items,
    reject_review_item,
)
from talamus.services.scan import preview_scan, run_scan
from talamus.webapi.graph_layout import compute_note_graph

_STATIC = Path(__file__).parent / "static"
_PLACEHOLDER = "<!doctype html><title>Talamus</title><h1>Talamus web workbench</h1>"
_NO_ENGINE = {
    "success": False,
    "code": "import_no_engine",
    "message": "No engine connected — run `talamus setup` to connect one before importing.",
}


def _provider(root: Path) -> LLMProvider:
    config = load_or_default(TalamusPaths(root).config_path)
    return build_provider(config.llm_provider, config.llm_model)


def create_app(root: Path) -> FastAPI:
    app = FastAPI(title="Talamus", docs_url=None, redoc_url=None)
    root = Path(root)

    @app.get("/api/readiness")
    def readiness() -> dict:
        report = inspect_readiness(root=str(root))
        return {"success": True, "code": "readiness_loaded", "data": report.to_dict()}

    @app.get("/api/library")
    def library() -> dict:
        return list_library_notes(root).to_dict()

    @app.get("/api/graph")
    def graph() -> dict:
        return {"success": True, "code": "graph_laid_out", "data": compute_note_graph(root)}

    @app.get("/api/note")
    def note(title: str) -> dict:
        return read_note(root, title).to_dict()

    @app.post("/api/ask")
    def ask(payload: dict | None = None) -> dict:
        question = str((payload or {}).get("question", ""))
        return ask_brain(root, question).to_dict()

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

    @app.get("/api/brains")
    def brains() -> dict:
        return list_brains().to_dict()

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
            provider = _provider(root)
        except EngineNotFound:
            return _NO_ENGINE
        return run_ingest(root, target, provider, confirmed=confirmed).to_dict()

    @app.post("/api/import/text")
    def import_text(payload: dict | None = None) -> dict:
        text = str((payload or {}).get("text", ""))
        if not text.strip():
            return {"success": False, "code": "import_empty", "message": "Paste some text first."}
        try:
            provider = _provider(root)
        except EngineNotFound:
            return _NO_ENGINE
        return ingest_raw_text(root, text, provider).to_dict()

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
        return run_scan(
            root,
            target,
            lambda: _provider(root),
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

    index = _STATIC / "index.html"
    if index.is_file():
        app.mount("/assets", StaticFiles(directory=_STATIC / "assets"), name="assets")

        @app.get("/", response_class=HTMLResponse)
        def root_page() -> str:
            return index.read_text(encoding="utf-8")
    else:

        @app.get("/", response_class=HTMLResponse)
        def root_page() -> str:
            return _PLACEHOLDER

    return app
