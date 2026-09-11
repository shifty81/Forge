#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import socketserver
import threading
from pathlib import Path
from typing import Any, Sequence

from VaultIde import list_files, monaco_root, read_file, runtime_ready, write_file
from VaultSettings import load_settings


class IdeApi:
    def __init__(self, root: Path, initial_file: str = "") -> None:
        self.root = root.resolve()
        self.initial_file = initial_file

    def bootstrap(self) -> dict[str, Any]:
        settings = load_settings().get("ide") or {}
        return {
            "projectRoot": str(self.root),
            "projectName": self.root.name,
            "initialFile": self.initial_file,
            "files": list_files(self.root),
            "options": {
                "fontSize": int(settings.get("fontSize", 13) or 13),
                "wordWrap": str(settings.get("wordWrap") or "off"),
                "minimap": bool(settings.get("minimap", True)),
            },
        }

    def read_file(self, path: str) -> dict[str, Any]:
        return read_file(self.root, path)

    def write_file(self, path: str, text: str) -> dict[str, Any]:
        return write_file(self.root, path, text)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: Any) -> None:
        return


def _serve(root: Path) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(QuietHandler, directory=str(root))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="VaultIdeHttp")
    thread.start()
    return server, int(server.server_address[1])


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vault Monaco pop-out window")
    ap.add_argument("--root", required=True)
    ap.add_argument("--file", default="")
    ns = ap.parse_args(argv)
    root = Path(ns.root).expanduser().resolve()
    if not runtime_ready():
        raise SystemExit("Monaco runtime is not installed. Install it from Vault > Settings > IDE.")
    try:
        import webview  # type: ignore
    except Exception as exc:
        raise SystemExit(f"pywebview is not installed: {exc}")

    runtime = monaco_root().resolve()
    server, port = _serve(runtime)
    api = IdeApi(root, str(ns.file or ""))
    settings = load_settings().get("ide") or {}
    width = int(settings.get("windowWidth", 1500) or 1500)
    height = int(settings.get("windowHeight", 920) or 920)
    try:
        webview.create_window(
            f"ForgePY IDE — {root.name}",
            f"http://127.0.0.1:{port}/index.html",
            js_api=api,
            width=width,
            height=height,
            min_size=(900, 600),
            background_color="#090b0e",
        )
        webview.start(debug=bool(settings.get("devTools", False)), private_mode=True)
    finally:
        with contextlib.suppress(Exception):
            server.shutdown()
        with contextlib.suppress(Exception):
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
