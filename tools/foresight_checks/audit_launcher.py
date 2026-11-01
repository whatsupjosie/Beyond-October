"""Exercise the real launcher over loopback HTTP with disposable user data.

Run from the existing repository: python tools/foresight_checks/audit_launcher.py
No browser, external model or optional Node sidecar is started by this check.
"""

from pathlib import Path
import json
import os
import socket
import secrets
import base64
import subprocess
import sys
import tempfile
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]


def main():
    with tempfile.TemporaryDirectory(prefix="foresight-launch-audit-") as directory:
        scratch = Path(directory)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        log_path = scratch / "launcher.log"
        with log_path.open("w") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "run_reach.py"),
                    "--port",
                    str(port),
                    "--data-dir",
                    str(scratch / "user-data"),
                    "--no-browser",
                    "--start-page",
                    "foresight-counter",
                ],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            try:
                base = f"http://127.0.0.1:{port}"
                with httpx.Client(base_url=base, trust_env=False, timeout=1) as client:
                    deadline = time.monotonic() + 45
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError(
                                f"Launcher exited with code {process.returncode}"
                            )
                        try:
                            ready = client.get("/foresight-counter")
                            if ready.status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        if time.monotonic() >= deadline:
                            raise TimeoutError(
                                "Reach did not become ready within 45 seconds"
                            )
                        time.sleep(0.1)
                    assert (
                        ready.content
                        == (ROOT / "static/foresight_counter.html").read_bytes()
                    )
                    script = client.get("/static/foresight_counter.js")
                    assert script.status_code == 200
                    assert (
                        script.content
                        == (ROOT / "static/foresight_counter.js").read_bytes()
                    )
                    protected = client.get("/api/pubpartner/status")
                    assert protected.status_code == 401
                    bridge = client.get("/api/foresight/bridge/health")
                    assert bridge.status_code == 200 and bridge.json()["ok"]
                    assert f"Reach: {base}/foresight-counter" in log_path.read_text()
                    password = secrets.token_urlsafe(32)
                    setup = client.post(
                        "/api/auth/setup",
                        json={
                            "username": "audit-owner",
                            "password": password,
                            "confirm_password": password,
                        },
                        timeout=10,
                    )
                    assert setup.status_code in (200, 201), setup.text
                    token = setup.json()["access_token"]
                    headers = {"Authorization": "Bearer " + token}
                    raw = b"Offline workspace proof\n"
                    saved = client.post(
                        "/api/foresight/workspace/file",
                        headers=headers,
                        json={
                            "path": "Checks/offline.txt",
                            "data": base64.b64encode(raw).decode(),
                        },
                    )
                    assert saved.status_code == 200, saved.text
                    reopened = client.get(
                        "/api/foresight/workspace/file",
                        headers=headers,
                        params={"path": "Checks/offline.txt"},
                    )
                    assert (
                        reopened.status_code == 200
                        and base64.b64decode(reopened.json()["data"]) == raw
                    )
                    syntax = client.post(
                        "/api/foresight/workspace/check-python",
                        headers=headers,
                        json={"text": "print(42)"},
                    )
                    assert syntax.status_code == 200 and syntax.json()["ok"]
                    host = client.get("/api/foresight/host/status", headers=headers)
                    assert host.status_code == 200 and host.json()["quit_available"]
                    quit_result = client.post(
                        "/api/foresight/host/quit", headers=headers
                    )
                    assert quit_result.status_code == 200, quit_result.text
                    process.wait(timeout=15)
                    assert process.returncode == 0, log_path.read_text()[-3000:]
                    print(
                        json.dumps(
                            {
                                "launcher": "passed",
                                "counter": ready.status_code,
                                "served_updated_script": True,
                                "anonymous_pubpartner": protected.status_code,
                                "bridge": bridge.status_code,
                                "supervised_quit": True,
                                "local_disk_save_and_reopen": True,
                                "python_syntax_check": True,
                            }
                        )
                    )
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
