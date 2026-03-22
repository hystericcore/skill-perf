"""Local HTTP server for viewing skill-perf HTML reports."""

from __future__ import annotations

import http.server
import threading
import webbrowser
from functools import partial
from pathlib import Path


def serve_report(
    html_path: str,
    port: int = 8888,
    open_browser: bool = True,
) -> None:
    """Start a local HTTP server and open the report in a browser.

    The server serves the directory containing *html_path* so that any
    relative assets (if any) resolve correctly.

    Args:
        html_path: Path to the generated HTML report file.
        port: TCP port for the local server. Defaults to ``8888``.
        open_browser: Whether to automatically open the system browser.
    """
    path = Path(html_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Report file not found: {html_path}")

    serve_dir = str(path.parent)
    filename = path.name

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=serve_dir)
    server = http.server.HTTPServer(("127.0.0.1", port), handler)

    url = f"http://127.0.0.1:{port}/{filename}"
    print(f"Serving report at {url}")
    print("Press Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
