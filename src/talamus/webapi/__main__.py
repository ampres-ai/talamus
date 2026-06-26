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
    threading.Thread(target=server.run, daemon=True).start()

    if not args.web:
        try:
            import webview

            webview.create_window("Talamus", url, width=1280, height=820)
            webview.start()
            return
        except ImportError:
            pass
    import webbrowser

    webbrowser.open(url)
    threading.Event().wait()


if __name__ == "__main__":
    main()
