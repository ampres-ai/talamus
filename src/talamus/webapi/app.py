"""FastAPI bridge: one endpoint per services/ call. The response body is the service
ServiceResult (success/message/code/data) as JSON. No business logic here — the same
seam rule the CLI and MCP follow."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from talamus.services.library import list_library_notes
from talamus.services.readiness import inspect_readiness
from talamus.webapi.graph_layout import compute_note_graph

_STATIC = Path(__file__).parent / "static"
_PLACEHOLDER = "<!doctype html><title>Talamus</title><h1>Talamus web workbench</h1>"


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
