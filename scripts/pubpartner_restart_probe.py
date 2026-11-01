"""Authenticated restart/continuity probe for the packaged application.

Starts the real launcher twice against one temporary data directory and proves:
* first-run owner setup;
* protected PubPartner routes reject anonymous access;
* a session and exact-source turn persist;
* the signing secret survives restart;
* login and old-token verification still work after restart.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(base: str, path: str, *, method: str = "GET", payload: dict | None = None, token: str = "") -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed loopback URL
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw}
        return exc.code, data


def _wait(base: str, process: subprocess.Popen[str], timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited early with code {process.returncode}")
        try:
            status, _ = _request(base, "/api/auth/status")
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise TimeoutError("server did not become ready")


def _start(port: int, data_dir: Path, log_path: Path) -> subprocess.Popen[str]:
    log = log_path.open("a", encoding="utf-8")
    env = dict(os.environ)
    env.pop("PUBCAST_OWNER_PASSWORD", None)
    return subprocess.Popen(
        [sys.executable, "run_pubpartner.py", "--no-browser", "--port", str(port), "--data-dir", str(data_dir)],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pubpartner_restart_") as tmp:
        data_dir = Path(tmp) / "data"
        log_path = Path(tmp) / "server.log"
        port = _free_port()
        base = f"http://127.0.0.1:{port}"
        password = "Lantern!River9Stone"
        token = ""
        source_id = ""

        first = _start(port, data_dir, log_path)
        try:
            _wait(base, first)
            anon_status, _ = _request(base, "/api/pubpartner/status")
            setup_status, setup = _request(base, "/api/auth/setup", method="POST", payload={
                "username": "owner",
                "password": password,
                "confirm_password": password,
            })
            token = str(setup.get("access_token") or "")
            protected_status, _ = _request(base, "/api/pubpartner/status", token=token)
            session_status, _ = _request(base, "/api/pubpartner/sessions", method="POST", token=token, payload={
                "user_id": "owner",
                "session_id": "restart-proof",
                "friend": "alex",
                "provider": "mock",
                "project_id": "pubpartner",
                "room_id": "phone",
            })
            turn_status, turn = _request(base, "/api/pubpartner/turns/live", method="POST", token=token, payload={
                "user_id": "owner",
                "session_id": "restart-proof",
                "message": "Never alter this exact restart proof line.",
                "content_kind": "quote",
                "provider": {"provider": "mock"},
                "project_id": "pubpartner",
                "room_id": "phone",
            })
            source_id = str((turn.get("source") or {}).get("id") or "")
            first_ok = (
                anon_status == 401
                and setup_status == 201
                and bool(token)
                and protected_status == 200
                and session_status == 200
                and turn_status == 200
                and bool(source_id)
            )
            if not first_ok:
                raise RuntimeError({
                    "anon_status": anon_status,
                    "setup_status": setup_status,
                    "protected_status": protected_status,
                    "session_status": session_status,
                    "turn_status": turn_status,
                    "source_id": source_id,
                })
        finally:
            _stop(first)

        second = _start(port, data_dir, log_path)
        try:
            _wait(base, second)
            old_token_status, old_token = _request(base, "/api/auth/verify", token=token)
            login_status, login = _request(base, "/api/auth/login", method="POST", payload={
                "username": "owner", "password": password,
            })
            new_token = str(login.get("access_token") or "")
            turns_status, turns = _request(
                base,
                "/api/pubpartner/sessions/restart-proof/turns?user_id=owner&limit=10",
                token=new_token,
            )
            source_status, source = _request(
                base,
                f"/api/pubpartner/sources/{source_id}?user_id=owner&session_id=restart-proof",
                token=new_token,
            )
            expected = "Never alter this exact restart proof line."
            ok = (
                old_token_status == 200
                and old_token.get("valid") is True
                and login_status == 200
                and bool(new_token)
                and turns_status == 200
                and len(turns.get("turns", [])) >= 1
                and source_status == 200
                and source.get("text") == expected
            )
            report = {
                "ok": ok,
                "auth_setup": True,
                "anonymous_pubpartner_rejected": True,
                "persistent_signing_secret": old_token_status == 200,
                "login_after_restart": login_status == 200,
                "turns_after_restart": len(turns.get("turns", [])),
                "exact_source_restored": source.get("text") == expected,
                "data_dir": str(data_dir),
            }
            print(json.dumps(report, indent=2))
            if not ok:
                print(log_path.read_text(encoding="utf-8", errors="replace")[-12000:], file=sys.stderr)
            return 0 if ok else 1
        finally:
            _stop(second)


if __name__ == "__main__":
    raise SystemExit(main())
