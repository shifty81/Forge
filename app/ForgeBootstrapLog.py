from __future__ import annotations
import os, tempfile, threading, time
from datetime import datetime
from pathlib import Path
from typing import TextIO

BUILD_MARKER = "FORGEPY-F60R375"
_lock = threading.RLock()
_stream: TextIO | None = None
_path: Path | None = None
_latest: Path | None = None


def _candidate_dirs() -> list[Path]:
    package_root = Path(__file__).resolve().parents[1]
    rows = [package_root / "logs" / "bootstrap"]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        rows.append(Path(local) / "ForgePY" / "Logs" / "bootstrap")
    rows.append(Path(tempfile.gettempdir()) / "ForgePY" / "bootstrap")
    return rows


def initialize() -> Path | None:
    global _stream, _path, _latest
    if _stream is not None:
        return _path
    for directory in _candidate_dirs():
        try:
            directory.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            _path = directory / f"forgepy-bootstrap-{stamp}.log"
            _latest = directory / "forgepy-bootstrap-latest.log"
            _stream = _path.open("a", encoding="utf-8", buffering=1)
            _latest.write_text("", encoding="utf-8")
            trace("BOOTSTRAP_LOG_READY", path=str(_path), pid=os.getpid(), build=BUILD_MARKER)
            return _path
        except Exception:
            _stream = None; _path = None; _latest = None
    return None


def trace(event: str, **fields) -> None:
    global _stream
    line = f"{datetime.now().isoformat(timespec='milliseconds')} [{threading.current_thread().name}] {event}"
    if fields:
        line += " " + " ".join(f"{k}={v!r}" for k,v in fields.items())
    line += "\n"
    with _lock:
        try:
            if _stream is None:
                initialize()
            if _stream is not None:
                _stream.write(line); _stream.flush()
        except Exception:
            pass
        try:
            if _latest is not None:
                with _latest.open("a", encoding="utf-8") as fh:
                    fh.write(line); fh.flush()
        except Exception:
            pass


def path() -> Path | None:
    return _path or initialize()
