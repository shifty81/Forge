#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from VaultSettings import load_settings, save_settings

FORGEJO_VERSION = "VAULT-FORGEJO-0.4"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def config() -> dict[str, Any]:
    settings = load_settings()
    cfg = dict(settings.get("forgejo") or {})
    home = Path(str(settings.get("vaultHome") or Path.home() / "Vault"))
    cfg.setdefault("url", "http://127.0.0.1:3000")
    cfg.setdefault("workPath", str(home / "Forgejo"))
    cfg.setdefault("config", str(Path(cfg["workPath"]) / "custom" / "conf" / "app.ini"))
    cfg.setdefault("binary", "")
    return cfg


def work_path() -> Path:
    return Path(str(config()["workPath"])).expanduser()


def config_path() -> Path:
    return Path(str(config()["config"])).expanduser()


def binary_path() -> Path | None:
    cfg = config()
    candidates: list[Path] = []
    env = str(os.environ.get("VAULT_FORGEJO_BIN") or "").strip()
    if env:
        candidates.append(Path(env).expanduser())
    if str(cfg.get("binary") or "").strip():
        candidates.append(Path(str(cfg["binary"])).expanduser())
    found = shutil.which("forgejo") or shutil.which("forgejo.exe")
    if found:
        candidates.append(Path(found))
    work = Path(str(cfg["workPath"]))
    candidates.extend([work / "bin" / "forgejo.exe", work / "bin" / "forgejo", work / "forgejo.exe", work / "forgejo"])
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None


def _global_args(binary: Path) -> list[str]:
    args = [str(binary), "--work-path", str(work_path())]
    cfg = config_path()
    if cfg.is_file():
        args.extend(["--config", str(cfg)])
    return args


def _run(*tail: str, timeout: float = 90.0, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    binary = binary_path()
    if binary is None:
        raise RuntimeError("Forgejo binary is not configured. Place forgejo.exe under Vault\\Forgejo\\bin or configure VAULT_FORGEJO_BIN.")
    target_cwd = cwd or work_path()
    target_cwd.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [*_global_args(binary), *tail], cwd=str(target_cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
        creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0,
    )


def _api(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None, token: str | None = None, timeout: float = 3.0) -> tuple[int, Any]:
    base = str(config().get("url") or "http://127.0.0.1:3000").rstrip("/")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    tok = token or str(os.environ.get("VAULT_FORGEJO_TOKEN") or "").strip()
    if tok:
        headers["Authorization"] = f"token {tok}"
    request = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            try:
                data = json.loads(raw.decode("utf-8")) if raw else None
            except Exception:
                data = raw.decode("utf-8", errors="replace")
            return int(response.status), data
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            data = json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            data = raw.decode("utf-8", errors="replace")
        return int(exc.code), data


def server_status() -> dict[str, Any]:
    binary = binary_path()
    result: dict[str, Any] = {
        "schema": "vault.forgejo.status.v1", "version": FORGEJO_VERSION,
        "binaryReady": binary is not None, "binary": str(binary) if binary else "",
        "binaryVersion": "", "url": str(config().get("url") or ""), "online": False,
        "serverVersion": "", "workPath": str(work_path()), "config": str(config_path()),
        "tokenConfigured": bool(str(os.environ.get("VAULT_FORGEJO_TOKEN") or "").strip()),
    }
    if binary is not None:
        try:
            cp = subprocess.run([str(binary), "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5, check=False)
            result["binaryVersion"] = cp.stdout.strip()
        except Exception as exc:
            result["binaryVersion"] = f"error: {exc}"
    for endpoint in ("/api/forgejo/v1/version", "/api/v1/version"):
        try:
            code, data = _api(endpoint)
            if code == 200:
                result["online"] = True
                if isinstance(data, dict):
                    result["serverVersion"] = str(data.get("version") or data.get("Version") or "online")
                else:
                    result["serverVersion"] = str(data or "online")
                break
        except Exception:
            pass
    return result


def _state_path() -> Path:
    path = work_path() / "vault-forgejo-process.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def start_server() -> dict[str, Any]:
    current = server_status()
    if current.get("online"):
        return {"status": "already-running", **current}
    binary = binary_path()
    if binary is None:
        raise RuntimeError("Forgejo binary is not configured.")
    work = work_path(); work.mkdir(parents=True, exist_ok=True)
    log_dir = work / "log"; log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "vault-forgejo.log"
    log = log_path.open("a", encoding="utf-8")
    args = [*_global_args(binary), "web"]
    port = str(config().get("port") or "3000")
    args.extend(["--port", port])
    flags = 0
    if os.name == "nt":
        flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    proc = subprocess.Popen(args, cwd=str(work), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
    state = {"schema": "vault.forgejo.process.v1", "pid": proc.pid, "startedUtc": utc_now(), "args": args, "log": str(log_path)}
    _state_path().write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return {"status": "started", **state}


def stop_server() -> dict[str, Any]:
    state_path = _state_path()
    if not state_path.is_file():
        return {"status": "no-managed-process"}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
        pid = int(state.get("pid") or 0)
    except Exception:
        pid = 0
    if pid > 0:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    state_path.unlink(missing_ok=True)
    return {"status": "stopped", "pid": pid}


def doctor(*, all_checks: bool = False) -> subprocess.CompletedProcess[str]:
    tail = ["doctor", "check", "--log-file", "-"]
    if all_checks:
        tail.append("--all")
    else:
        tail.append("--default")
    return _run(*tail, timeout=300.0)


def backup() -> subprocess.CompletedProcess[str]:
    backup_dir = work_path() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    output = backup_dir / ("forgejo-dump-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip")
    return _run("dump", "--file", str(output), timeout=1200.0, cwd=work_path())


def admin_users() -> subprocess.CompletedProcess[str]:
    return _run("admin", "user", "list")


def runner_token(scope: str = "") -> subprocess.CompletedProcess[str]:
    tail = ["forgejo-cli", "actions", "generate-runner-token"]
    if scope.strip():
        tail.extend(["--scope", scope.strip()])
    return _run(*tail, timeout=90.0)


def action_secret() -> subprocess.CompletedProcess[str]:
    return _run("forgejo-cli", "actions", "generate-secret", timeout=90.0)


def list_repositories() -> tuple[int, Any]:
    return _api("/api/v1/user/repos?limit=100")


def create_repository(name: str, *, private: bool = True) -> tuple[int, Any]:
    return _api("/api/v1/user/repos", method="POST", payload={"name": name, "private": bool(private), "auto_init": False, "default_branch": "main"})


def open_web() -> None:
    webbrowser.open(str(config().get("url") or "http://127.0.0.1:3000"))


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vault-owned local Forgejo control surface")
    ap.add_argument("action", choices=("status", "start", "stop", "doctor", "doctor-all", "backup", "users", "repos", "create-repo", "runner-token", "action-secret"))
    ap.add_argument("--name")
    ap.add_argument("--scope", default="")
    ns = ap.parse_args(argv)
    if ns.action == "status":
        print(json.dumps(server_status(), indent=2, sort_keys=True)); return 0
    if ns.action == "start":
        print(json.dumps(start_server(), indent=2, sort_keys=True)); return 0
    if ns.action == "stop":
        print(json.dumps(stop_server(), indent=2, sort_keys=True)); return 0
    if ns.action == "repos":
        code, data = list_repositories(); print(json.dumps({"http": code, "data": data}, indent=2, sort_keys=True)); return 0 if code == 200 else 1
    if ns.action == "create-repo":
        if not ns.name:
            print("[FAIL] --name is required for create-repo"); return 2
        code, data = create_repository(ns.name); print(json.dumps({"http": code, "data": data}, indent=2, sort_keys=True)); return 0 if code in (201, 409, 422) else 1
    if ns.action == "doctor":
        cp = doctor(all_checks=False)
    elif ns.action == "doctor-all":
        cp = doctor(all_checks=True)
    elif ns.action == "backup":
        cp = backup()
    elif ns.action == "users":
        cp = admin_users()
    elif ns.action == "runner-token":
        cp = runner_token(ns.scope)
    else:
        cp = action_secret()
    print(cp.stdout, end=""); return int(cp.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
