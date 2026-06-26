# Talamus web workbench (frontend)

React + Vite + TypeScript SPA for the Talamus workbench. It talks to the local
FastAPI bridge (`src/talamus/webapi/`) over `/api/*`.

**Users never need Node.** A release ships the prebuilt assets inside the Python
package (`src/talamus/webapi/static/`), and `python -m talamus.webapi` serves them.

## Develop

```bash
cd webui
npm install
# in another terminal, run the API on port 8760:
#   python -m talamus.webapi --root <brain> --web --port 8760
npm run dev          # Vite dev server; /api is proxied to 8760
```

## Build (what release does)

```bash
cd webui
npm run build        # outputs into ../src/talamus/webapi/static/ (committed, shipped)
```

Then `python -m talamus.webapi --root <brain>` serves the built app in a native
window (pywebview) or, with `--web`, in the browser.
