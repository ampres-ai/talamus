# P7 Web Workbench — Walking Skeleton — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans or
> superpowers:subagent-driven-development to implement this task-by-task. Steps use
> checkbox (`- [ ]`) syntax.

**Goal:** A local React web workbench (Aurora skin) over the existing `services/`,
launched as a native window, showing two real views — Home (readiness) and the Graph
hero — to prove the whole stack end-to-end. Flet stays untouched.

**Architecture:** A thin FastAPI bridge (`src/talamus/webapi/`) maps each `services/`
call to a JSON endpoint (`ServiceResult.to_dict()` is the body). A Vite + React + TS
SPA (`webui/`) renders the workbench; the graph is laid out server-side by the
existing pure-Python `ui/physics.py` and rendered on a `<canvas>`. `python -m
talamus.webapi` serves the built SPA and opens a pywebview window (browser fallback).

**Tech Stack:** Python 3.13, FastAPI + uvicorn + pywebview (`[ui]` extra), Vite +
React 18 + TypeScript, Vitest. Gate: `python dev.py` (Python side). Node 24 / npm 11
present.

**Working rules:** run Python from `C:/dev/Kortex` with `PYTHONIOENCODING=utf-8`;
`python dev.py` must stay ALL GREEN. The bridge calls ONLY `services/` (never core
business logic) — same seam rule as CLI/MCP. Spec:
[dev/specs/2026-06-26-p7-web-workbench-design.md](../specs/2026-06-26-p7-web-workbench-design.md).
Tests run via `python -m unittest` (pytest is not installed).

---

## File structure

- Create: `src/talamus/webapi/__init__.py` — package marker + `create_app` re-export.
- Create: `src/talamus/webapi/app.py` — FastAPI app factory + endpoints + static mount.
- Create: `src/talamus/webapi/graph_layout.py` — server-side note-graph layout (reuses physics).
- Create: `src/talamus/webapi/__main__.py` — `python -m talamus.webapi` launcher (uvicorn + pywebview).
- Modify: `pyproject.toml` — extend the `[ui]` extra with fastapi/uvicorn/pywebview.
- Create: `tests/test_webapi.py` — endpoint + layout tests (in the gate).
- Create: `webui/` — Vite React TS app (package.json, vite.config.ts, src/...).
- Create: `webui/src/theme.css` — Aurora design tokens.
- Create: `webui/src/api.ts` — typed fetch client.
- Create: `webui/src/shell/*` — ActivityBar, Sidebar, Tabs, StatusBar.
- Create: `webui/src/views/Home.tsx`, `webui/src/views/Graph.tsx`.
- Build output: `webui/dist/` → copied/served from `src/talamus/webapi/static/`.

---

## Task 1: The `[ui]` extra + webapi package + `/api/readiness`

**Files:**
- Modify: `pyproject.toml` (the `[project.optional-dependencies] ui` list)
- Create: `src/talamus/webapi/__init__.py`, `src/talamus/webapi/app.py`
- Test: `tests/test_webapi.py`

- [ ] **Step 1: Extend the `ui` extra.** In `pyproject.toml`, add to the `ui` extra
list (next to `flet`): `"fastapi>=0.110"`, `"uvicorn>=0.29"`, `"pywebview>=5.0"`.
(Both Flet and web ship during the transition; flet is dropped at Flet retirement.)

- [ ] **Step 2: Write the failing test** `tests/test_webapi.py`:

```python
import importlib.util
import tempfile
import unittest
from pathlib import Path

_HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


@unittest.skipUnless(_HAS_FASTAPI, "fastapi not installed (ui extra)")
class WebApiTests(unittest.TestCase):
    def _client(self, root: Path):
        from fastapi.testclient import TestClient

        from talamus.webapi.app import create_app

        return TestClient(create_app(root))

    def test_readiness_endpoint_returns_service_result(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            create_demo_brain(TalamusPaths(Path(tmp)))
            resp = self._client(Path(tmp)).get("/api/readiness")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertIn("data", body)
        self.assertEqual(body["data"]["notes"], 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run it to verify it fails.**

```bash
cd "C:/dev/Kortex"; python -m unittest tests.test_webapi -v
```

Expected: FAIL (`No module named 'talamus.webapi'`).

- [ ] **Step 4: Implement** `src/talamus/webapi/__init__.py`:

```python
"""Local web workbench backend: a thin FastAPI bridge over talamus.services."""

from __future__ import annotations

from talamus.webapi.app import create_app

__all__ = ["create_app"]
```

And `src/talamus/webapi/app.py`:

```python
"""FastAPI bridge: one endpoint per services/ call. The response body is the
service ServiceResult (success/message/code/data) as JSON. No business logic here —
the same seam rule the CLI and MCP follow."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from talamus.services.readiness import inspect_readiness


def create_app(root: Path) -> FastAPI:
    app = FastAPI(title="Talamus", docs_url=None, redoc_url=None)
    root = Path(root)

    @app.get("/api/readiness")
    def readiness() -> dict:
        report = inspect_readiness(root=str(root))
        return {"success": True, "code": "readiness_loaded", "data": report.to_dict()}

    return app
```

- [ ] **Step 5: Run it to verify it passes.**

```bash
cd "C:/dev/Kortex"; python -m unittest tests.test_webapi -v
```

Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add pyproject.toml src/talamus/webapi/__init__.py src/talamus/webapi/app.py tests/test_webapi.py
git commit -m "feat(webapi): FastAPI bridge + /api/readiness [P7]"
```

---

## Task 2: `/api/library` (a list view's data)

**Files:**
- Modify: `src/talamus/webapi/app.py`
- Test: `tests/test_webapi.py`

- [ ] **Step 1: Add the failing test** (new method in `WebApiTests`):

```python
    def test_library_endpoint_lists_notes(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            create_demo_brain(TalamusPaths(Path(tmp)))
            resp = self._client(Path(tmp)).get("/api/library")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["note_count"], 3)
        titles = [n["title"] for n in body["data"]["notes"]]
        self.assertIn("Embedding", titles)
```

- [ ] **Step 2: Run to verify it fails** (`404`/KeyError).

```bash
cd "C:/dev/Kortex"; python -m unittest tests.test_webapi -v
```

- [ ] **Step 3: Implement** — in `app.py` add the import and endpoint:

```python
from talamus.services.library import list_library_notes
```

```python
    @app.get("/api/library")
    def library() -> dict:
        result = list_library_notes(root)
        return result.to_dict()
```

(`ServiceResult.to_dict()` already yields `{success, message, code, data}`; `data` is
the `LibraryReport` with `note_count` + `notes`.)

- [ ] **Step 4: Run to verify it passes.**

- [ ] **Step 5: Commit.**

```bash
git add src/talamus/webapi/app.py tests/test_webapi.py
git commit -m "feat(webapi): /api/library endpoint [P7]"
```

---

## Task 3: Graph layout helper + `/api/graph` (the hero's data)

**Files:**
- Create: `src/talamus/webapi/graph_layout.py`
- Modify: `src/talamus/webapi/app.py`
- Test: `tests/test_webapi.py`

- [ ] **Step 1: Write the failing test:**

```python
    def test_graph_endpoint_lays_out_notes(self) -> None:
        from talamus.demo import create_demo_brain
        from talamus.paths import TalamusPaths

        with tempfile.TemporaryDirectory() as tmp:
            create_demo_brain(TalamusPaths(Path(tmp)))
            resp = self._client(Path(tmp)).get("/api/graph")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertGreaterEqual(len(data["nodes"]), 3)
        node = data["nodes"][0]
        for key in ("id", "label", "x", "y", "r"):
            self.assertIn(key, node)
        self.assertIsInstance(data["edges"], list)
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** `src/talamus/webapi/graph_layout.py`:

```python
"""Server-side note-graph layout for the web graph hero.

Reuses the deterministic pure-Python force layout (talamus.ui.physics) so the client
only renders. Data comes from the graph service (the same seam the CLI/MCP use):
note nodes + the relations between them."""

from __future__ import annotations

from pathlib import Path

from talamus.services.graph import get_graph_snapshot
from talamus.ui import physics


def compute_note_graph(root: Path, width: float = 900.0, height: float = 600.0) -> dict:
    result = get_graph_snapshot(root)
    snapshot = result.data
    if snapshot is None:
        return {"nodes": [], "edges": [], "width": width, "height": height}
    note_ids = {node.id for node in snapshot.nodes if node.kind == "note"}
    labels = {node.id: node.label for node in snapshot.nodes if node.kind == "note"}
    edges = [
        (edge.source, edge.target, edge.type)
        for edge in snapshot.edges
        if edge.source in note_ids and edge.target in note_ids
    ]
    layout = physics.build_layout(sorted(note_ids), edges, width=width, height=height)
    physics.settle(layout)
    nodes = [
        {
            "id": node_id,
            "label": labels.get(node_id, node_id),
            "x": round(node.x, 1),
            "y": round(node.y, 1),
            "r": round(layout.radius(node_id), 1),
            "degree": node.degree,
        }
        for node_id, node in layout.nodes.items()
    ]
    out_edges = [
        {"source": src, "target": dst, "type": edge_type, "typed": edge_type != "related"}
        for src, dst, edge_type in layout.edges
    ]
    return {"nodes": nodes, "edges": out_edges, "width": width, "height": height}
```

In `app.py` add:

```python
from talamus.webapi.graph_layout import compute_note_graph
```

```python
    @app.get("/api/graph")
    def graph() -> dict:
        return {"success": True, "code": "graph_laid_out", "data": compute_note_graph(root)}
```

- [ ] **Step 4: Run to verify it passes.**

- [ ] **Step 5: Commit.**

```bash
git add src/talamus/webapi/graph_layout.py src/talamus/webapi/app.py tests/test_webapi.py
git commit -m "feat(webapi): server-side note-graph layout + /api/graph [P7]"
```

---

## Task 4: Static serving + the `python -m talamus.webapi` launcher

**Files:**
- Modify: `src/talamus/webapi/app.py` (serve `static/` if present)
- Create: `src/talamus/webapi/__main__.py`
- Create: `src/talamus/webapi/static/.gitkeep` (the React build lands here later)
- Test: `tests/test_webapi.py`

- [ ] **Step 1: Write the failing test** (root serves something; index fallback is OK
when the SPA isn't built yet):

```python
    def test_root_serves_index_or_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resp = self._client(Path(tmp)).get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Talamus", resp.text)
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** — in `app.py`, after the API routes, mount static and add
a root that returns the SPA index (or a placeholder before the first build):

```python
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

_STATIC = Path(__file__).parent / "static"
_PLACEHOLDER = "<!doctype html><title>Talamus</title><h1>Talamus web workbench</h1>"
```

```python
    index = _STATIC / "index.html"
    if index.is_file():
        app.mount("/assets", StaticFiles(directory=_STATIC / "assets"), name="assets")

        @app.get("/", response_class=HTMLResponse)
        def root() -> str:
            return index.read_text(encoding="utf-8")
    else:

        @app.get("/", response_class=HTMLResponse)
        def root() -> str:
            return _PLACEHOLDER
```

(Place this block before `return app`.)

- [ ] **Step 4: Implement the launcher** `src/talamus/webapi/__main__.py`:

```python
"""Launch the web workbench: `python -m talamus.webapi --root <brain> [--web] [--port N]`.

Serves the SPA + API on localhost and opens a native window (pywebview). With --web,
opens the default browser instead. The CLI `talamus ui` is re-pointed at parity."""

from __future__ import annotations

import argparse
import threading
from pathlib import Path

import uvicorn

from talamus.webapi.app import create_app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="talamus-webui")
    parser.add_argument("--root", default=".")
    parser.add_argument("--port", type=int, default=8760)
    parser.add_argument("--web", action="store_true", help="open the browser instead of a window")
    args = parser.parse_args(argv)

    app = create_app(Path(args.root).resolve())
    url = f"http://127.0.0.1:{args.port}"
    config = uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    server = uvicorn.Server(config)

    if args.web:
        threading.Thread(target=server.run, daemon=True).start()
        import webbrowser

        webbrowser.open(url)
        threading.Event().wait()
        return
    threading.Thread(target=server.run, daemon=True).start()
    try:
        import webview

        webview.create_window("Talamus", url, width=1280, height=820)
        webview.start()
    except ImportError:
        import webbrowser

        webbrowser.open(url)
        threading.Event().wait()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the static test to verify it passes;** then smoke the launcher in
`--web` mode (Ctrl-C to stop):

```bash
cd "C:/dev/Kortex"; python -m unittest tests.test_webapi -v
cd "C:/dev/Kortex"; python -m talamus.webapi --root .uidemo --web --port 8760   # opens the placeholder, then stop
```

Expected: tests PASS; the browser shows the placeholder page.

- [ ] **Step 6: Commit.**

```bash
git add src/talamus/webapi/app.py src/talamus/webapi/__main__.py src/talamus/webapi/static/.gitkeep tests/test_webapi.py
git commit -m "feat(webapi): static SPA serving + native-window launcher [P7]"
```

---

## Task 5: React scaffold + Aurora tokens + API client

**Files:**
- Create: `webui/` (Vite React TS), `webui/src/theme.css`, `webui/src/api.ts`

- [ ] **Step 1: Scaffold** (Node 24 / npm 11 present):

```bash
cd "C:/dev/Kortex"; npm create vite@latest webui -- --template react-ts
cd "C:/dev/Kortex/webui"; npm install
```

- [ ] **Step 2: Vite config** — `webui/vite.config.ts` (build to `dist`, dev-proxy the
API to the Python server on 8760):

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { proxy: { "/api": "http://127.0.0.1:8760" } },
  build: { outDir: "dist", assetsDir: "assets" },
});
```

- [ ] **Step 3: Aurora tokens** — `webui/src/theme.css`:

```css
:root {
  --bg: #0A0E14; --surface: #121826; --surface-2: #1A2230; --border: #263041;
  --text: #EAEFF7; --muted: #7E8CA3;
  --accent: #6E5BFF; --accent-2: #4FC3F7;
  --ok: #82D37B; --warn: #FFB74D; --danger: #FF8A8A;
  --radius: 10px; --pad: 16px;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font-family: ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif; }
```

- [ ] **Step 4: Typed API client** — `webui/src/api.ts`:

```ts
export type ServiceResult<T> = { success: boolean; message?: string; code?: string; data: T };
export type GraphNode = { id: string; label: string; x: number; y: number; r: number; degree: number };
export type GraphEdge = { source: string; target: string; type: string; typed: boolean };
export type GraphData = { nodes: GraphNode[]; edges: GraphEdge[]; width: number; height: number };

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`${path} -> ${resp.status}`);
  return (await resp.json()) as T;
}

export const api = {
  readiness: () => get<ServiceResult<Record<string, unknown>>>("/api/readiness"),
  library: () => get<ServiceResult<{ note_count: number; notes: any[] }>>("/api/library"),
  graph: () => get<ServiceResult<GraphData>>("/api/graph"),
};
```

- [ ] **Step 5: Commit.**

```bash
cd "C:/dev/Kortex"; git add webui/package.json webui/package-lock.json webui/vite.config.ts webui/tsconfig*.json webui/index.html webui/src/theme.css webui/src/api.ts
git commit -m "feat(webui): Vite React scaffold + Aurora tokens + API client [P7]"
```

---

## Task 6: The workbench shell

**Files:**
- Create: `webui/src/shell/Shell.tsx`, `webui/src/main.tsx` (replace scaffold), `webui/src/App.tsx`

- [ ] **Step 1: Shell** — `webui/src/shell/Shell.tsx` (activity bar + collapsible
sidebar + tabbed center + status bar; Aurora):

```tsx
import { useState, ReactNode } from "react";

const NAV = [
  { id: "home", label: "Home", icon: "⌂" },
  { id: "graph", label: "Graph", icon: "✸" },
  { id: "library", label: "Library", icon: "▤" },
];

export function Shell({ views }: { views: Record<string, ReactNode> }) {
  const [active, setActive] = useState("home");
  const [openTabs, setOpenTabs] = useState<string[]>(["home"]);
  const open = (id: string) => {
    setActive(id);
    setOpenTabs((t) => (t.includes(id) ? t : [...t, id]));
  };
  const label = (id: string) => NAV.find((n) => n.id === id)?.label ?? id;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "56px 220px 1fr", height: "100vh" }}>
      <nav style={{ background: "var(--surface)", borderRight: "1px solid var(--border)",
        display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 12, gap: 6 }}>
        {NAV.map((n) => (
          <button key={n.id} onClick={() => open(n.id)} aria-label={n.label}
            style={{ width: 40, height: 40, borderRadius: 10, fontSize: 18, cursor: "pointer",
              background: active === n.id ? "var(--surface-2)" : "transparent",
              color: active === n.id ? "var(--accent)" : "var(--muted)",
              border: "1px solid " + (active === n.id ? "var(--border)" : "transparent") }}>
            {n.icon}
          </button>
        ))}
      </nav>
      <aside style={{ background: "var(--surface)", borderRight: "1px solid var(--border)", padding: 16 }}>
        <div style={{ fontWeight: 500, fontSize: 18 }}>Talamus<span style={{ color: "var(--accent)" }}>●</span></div>
        <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 12, textTransform: "uppercase" }}>{label(active)}</div>
      </aside>
      <main style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <div style={{ display: "flex", gap: 4, padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
          {openTabs.map((id) => (
            <button key={id} onClick={() => setActive(id)}
              style={{ padding: "6px 12px", borderRadius: 8, cursor: "pointer",
                background: active === id ? "var(--surface-2)" : "transparent",
                color: active === id ? "var(--text)" : "var(--muted)",
                border: "1px solid " + (active === id ? "var(--border)" : "transparent") }}>
              {label(id)}
            </button>
          ))}
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 20 }}>{views[active]}</div>
        <footer style={{ borderTop: "1px solid var(--border)", padding: "6px 14px",
          color: "var(--muted)", fontSize: 12, display: "flex", gap: 16 }}>
          <span style={{ color: "var(--ok)" }}>● local-first</span>
          <span>token cost visible</span>
        </footer>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: App + main** — `webui/src/App.tsx`:

```tsx
import "./theme.css";
import { Shell } from "./shell/Shell";
import { Home } from "./views/Home";
import { Graph } from "./views/Graph";
import { Library } from "./views/Library";

export default function App() {
  return <Shell views={{ home: <Home />, graph: <Graph />, library: <Library /> }} />;
}
```

`webui/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 3: Commit** (views added next task; create stub `Library.tsx` returning
`<div>Library…</div>` so the build passes, replaced in Task 7).

```bash
cd "C:/dev/Kortex"; printf 'export function Library(){return <div style={{color:"var(--muted)"}}>Library…</div>;}\n' > webui/src/views/Library.tsx
git add webui/src/shell/Shell.tsx webui/src/App.tsx webui/src/main.tsx webui/src/views/Library.tsx
git commit -m "feat(webui): Aurora workbench shell (activity bar + tabs + status bar) [P7]"
```

---

## Task 7: Home view (real readiness data)

**Files:**
- Create: `webui/src/views/Home.tsx`, replace `webui/src/views/Library.tsx`

- [ ] **Step 1: Home** — `webui/src/views/Home.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api } from "../api";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: "var(--radius)", padding: 14, minWidth: 150 }}>
      <div style={{ color: "var(--muted)", fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 500, marginTop: 4 }}>{value}</div>
    </div>
  );
}

export function Home() {
  const [d, setD] = useState<Record<string, any> | null>(null);
  useEffect(() => {
    api.readiness().then((r) => setD(r.data)).catch(() => setD({}));
  }, []);
  if (!d) return <div style={{ color: "var(--muted)" }}>Loading…</div>;
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Command center</h2>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Metric label="Brain" value={`${d.notes ?? 0} notes`} />
        <Metric label="Sources" value={`${d.sources ?? 0}`} />
        <Metric label="Reviews" value={`${d.reviews_pending ?? 0}`} />
        <Metric label="Index" value={String(d.index_backend ?? "—")} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Replace the Library stub** with the real list — `webui/src/views/Library.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api } from "../api";

export function Library() {
  const [notes, setNotes] = useState<any[]>([]);
  useEffect(() => {
    api.library().then((r) => setNotes(r.data.notes)).catch(() => setNotes([]));
  }, []);
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Library</h2>
      {notes.map((n) => (
        <div key={n.title} style={{ background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: "var(--radius)", padding: 12, marginBottom: 8 }}>
          <div style={{ fontWeight: 500 }}>{n.title}</div>
          <div style={{ color: "var(--muted)", fontSize: 13 }}>{n.summary}</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Commit.**

```bash
cd "C:/dev/Kortex"; git add webui/src/views/Home.tsx webui/src/views/Library.tsx
git commit -m "feat(webui): Home (readiness) + Library views on real data [P7]"
```

---

## Task 8: The Graph hero view (canvas, Aurora constellation)

**Files:**
- Create: `webui/src/views/Graph.tsx`

- [ ] **Step 1: Graph** — `webui/src/views/Graph.tsx` (fetch `/api/graph`, draw on a
canvas: faint indigo edges, glowing indigo nodes via two stacked arcs, labels; pan via
drag, zoom via wheel; click logs the node):

```tsx
import { useEffect, useRef, useState } from "react";
import { api, GraphData } from "../api";

export function Graph() {
  const ref = useRef<HTMLCanvasElement>(null);
  const [g, setG] = useState<GraphData | null>(null);
  const view = useRef({ scale: 1, ox: 0, oy: 0, drag: false, px: 0, py: 0 });

  useEffect(() => {
    api.graph().then((r) => setG(r.data)).catch(() => setG({ nodes: [], edges: [], width: 900, height: 600 }));
  }, []);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !g) return;
    const ctx = canvas.getContext("2d")!;
    const byId = new Map(g.nodes.map((n) => [n.id, n]));
    const draw = () => {
      const { scale, ox, oy } = view.current;
      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
      ctx.fillStyle = "#0A0E14";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.translate(ox + canvas.width / 2 - (g.width / 2) * scale, oy + canvas.height / 2 - (g.height / 2) * scale);
      ctx.scale(scale, scale);
      for (const e of g.edges) {
        const a = byId.get(e.source), b = byId.get(e.target);
        if (!a || !b) continue;
        ctx.strokeStyle = e.typed ? "rgba(110,91,255,0.55)" : "rgba(110,91,255,0.25)";
        ctx.lineWidth = e.typed ? 1.4 : 1;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      for (const n of g.nodes) {
        ctx.beginPath(); ctx.fillStyle = "rgba(110,91,255,0.18)";
        ctx.arc(n.x, n.y, n.r + 6, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.fillStyle = n.degree > 2 ? "#B7ADFF" : "#8B7BFF";
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = "#C9D2E0"; ctx.font = "11px sans-serif";
        ctx.fillText(n.label, n.x + n.r + 4, n.y + 3);
      }
      ctx.restore();
    };
    draw();
    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      view.current.scale = Math.min(3, Math.max(0.3, view.current.scale * (ev.deltaY < 0 ? 1.1 : 0.9)));
      draw();
    };
    const onDown = (ev: MouseEvent) => { view.current.drag = true; view.current.px = ev.clientX; view.current.py = ev.clientY; };
    const onMove = (ev: MouseEvent) => {
      if (!view.current.drag) return;
      view.current.ox += ev.clientX - view.current.px; view.current.oy += ev.clientY - view.current.py;
      view.current.px = ev.clientX; view.current.py = ev.clientY; draw();
    };
    const onUp = () => { view.current.drag = false; };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("resize", draw);
    return () => {
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("resize", draw);
    };
  }, [g]);

  return (
    <div style={{ height: "100%" }}>
      <h2 style={{ marginTop: 0 }}>Graph</h2>
      <div style={{ color: "var(--muted)", fontSize: 13, marginBottom: 10 }}>
        the most connected notes — drag to pan, wheel to zoom
      </div>
      <canvas ref={ref} style={{ width: "100%", height: "calc(100% - 64px)",
        border: "1px solid var(--border)", borderRadius: "var(--radius)", cursor: "grab", display: "block" }} />
    </div>
  );
}
```

- [ ] **Step 2: Build the SPA** (catches type/build errors):

```bash
cd "C:/dev/Kortex/webui"; npm run build
```

Expected: build succeeds → `webui/dist/` produced.

- [ ] **Step 3: Commit.**

```bash
cd "C:/dev/Kortex"; git add webui/src/views/Graph.tsx
git commit -m "feat(webui): Aurora graph hero on canvas (pan/zoom) [P7]"
```

---

## Task 9: Wire the build into the package + end-to-end smoke

**Files:**
- Modify: `pyproject.toml` (include `src/talamus/webapi/static/**` as package data)
- Modify: `webui/vite.config.ts` (build `outDir` to the package static dir)
- Create: `webui/README.md` (build instructions for contributors)

- [ ] **Step 1: Point the Vite build at the package static dir** — set
`build.outDir` in `webui/vite.config.ts` to `"../src/talamus/webapi/static"` and
`emptyOutDir: true`. Rebuild:

```bash
cd "C:/dev/Kortex/webui"; npm run build
```

Expected: `src/talamus/webapi/static/index.html` + `assets/` exist.

- [ ] **Step 2: Ship static as package data** — in `pyproject.toml` ensure the
package includes `talamus/webapi/static/**` (e.g., add to `[tool.setuptools.package-data]`
`talamus = ["py.typed", "webapi/static/**/*"]`, matching the existing pattern).

- [ ] **Step 3: End-to-end smoke** — launch and confirm the real app renders:

```bash
cd "C:/dev/Kortex"; python -m talamus.webapi --root .uidemo --web --port 8760
```

Expected: the browser shows the Aurora shell; Home shows `3 notes`; the Graph tab
shows the constellation (Embedding / Reranking / RAG) with pan/zoom. Stop with Ctrl-C.

- [ ] **Step 4: Write `webui/README.md`** (one paragraph: `npm install`, `npm run dev`
with the Python API on `--port 8760`, `npm run build` outputs into the package; users
never need Node — release ships the prebuilt `static/`).

- [ ] **Step 5: Full Python gate.**

```bash
cd "C:/dev/Kortex"; PYTHONIOENCODING=utf-8 python dev.py
```

Expected: ALL GREEN (new webapi tests included; Flet + services tests unchanged).

- [ ] **Step 6: Commit.**

```bash
cd "C:/dev/Kortex"; git add pyproject.toml webui/vite.config.ts webui/README.md src/talamus/webapi/static
git commit -m "build(webui): ship prebuilt SPA as package data + e2e smoke [P7]"
```

---

## Task 10: Roadmap + decision record

**Files:**
- Modify: `dev/ROADMAP.md` (P7 section)

- [ ] **Step 1: Update P7** to record the foundation pivot: P7 is now the web
workbench (React on the services seam, pywebview native window, Aurora, graph hero);
the walking skeleton (FastAPI bridge + Home + Graph) is done; the Flet UI stays until
parity; remaining sub-projects (port views, multi-tab, onboarding, packaging, Flet
retirement) are listed. Link the spec.

- [ ] **Step 2: Commit.**

```bash
cd "C:/dev/Kortex"; git add dev/ROADMAP.md
git commit -m "docs(roadmap): P7 pivots to the web workbench; skeleton landed [P7]"
```

---

## Self-review notes

- **Spec coverage:** bridge over services (T1-3), static + native-window launcher
  (T4), React Aurora shell (T6), Home + Graph-hero on real data (T7-8), server-side
  physics layout reused (T3), package-data shipping + e2e (T9), roadmap (T10). The two
  skeleton views and the FastAPI endpoints from the spec are all covered.
- **Seam rule:** every endpoint calls a `services/` function (readiness, library,
  graph); `graph_layout` uses `get_graph_snapshot` (service) + `physics` (pure Python),
  never core business logic — consistent with CLI/MCP.
- **Type consistency:** `GraphData`/`GraphNode` fields (`id,label,x,y,r,degree` /
  `source,target,type,typed`) match between `graph_layout.py`, `api.ts`, and `Graph.tsx`.
- **Plug-and-play:** users never run Node (prebuilt `static/` shipped); launcher falls
  back to the browser if pywebview is absent.
- **Risk:** `get_graph_snapshot` node `kind`/edge `type` field names are assumed from
  `services/graph.py` — verify at T3 execution (the test asserts the shape).
- **FE tests:** deferred to sub-project 2 per the spec; the `npm run build` in T7/T9 is
  the build-time gate. The Python gate covers the bridge.
