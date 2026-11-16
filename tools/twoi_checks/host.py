"""Start the real PubCast host for a 2i check, on a throwaway data folder, and sign a browser in.

Shared by the checks in this folder. Nothing under the repository's own ``data/`` is touched: the host is started
as ``run_reach.py --data-dir <temporary folder> --no-browser --no-legacy-2i`` on a free port, the owner account is
created through ``/api/auth/setup`` with a random password, and the browser signs in through the real ``/login``
page. The host is stopped when the ``with`` block ends.
"""
from __future__ import annotations

import contextlib
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
PAGE_ON_DISK = (REPO / "2i" / "writers-room-v22.html").as_uri()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def running_host(user: str = "twoi-check"):
    """Yield (base_url, user, password) for a freshly started, freshly set-up host."""
    data = Path(tempfile.mkdtemp(prefix="twoi_check_"))
    port = _free_port()
    log_path = data / "reach.log"
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen([sys.executable, "run_reach.py", "--port", str(port), "--data-dir", str(data),
                                 "--no-browser", "--no-legacy-2i"], cwd=str(REPO), stdout=log, stderr=subprocess.STDOUT)
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.time() + 120
            while True:
                if proc.poll() is not None:
                    log.flush()
                    raise RuntimeError("run_reach.py stopped during start-up:\n" + log_path.read_text(encoding="utf-8")[-3000:])
                try:
                    if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                if time.time() > deadline:
                    raise RuntimeError("the host did not answer /health within 120 seconds")
                time.sleep(0.3)
            password = secrets.token_urlsafe(20)
            r = httpx.post(base + "/api/auth/setup", json={"username": user, "password": password, "confirm_password": password}, timeout=10)
            if r.status_code not in (200, 201):
                raise RuntimeError(f"owner set-up failed: {r.status_code} {r.text[:300]}")
            yield base, user, password
        finally:
            proc.terminate()
            try:
                proc.wait(20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(5)


def open_writers_room(context, login):
    """Sign in through the real login page and return the 2i page once its own start-up has finished."""
    base, user, password = login
    page = context.new_page()
    page.goto(base + "/login?next=%2Fwriters-room")
    page.fill("#loginUser", user)
    page.fill("#loginPass", password)
    page.keyboard.press("Enter")
    page.wait_for_url("**/writers-room**", timeout=20000)
    page.wait_for_function("!!document.getElementById('twoiMenuBar') && typeof initializing !== 'undefined' && !initializing", timeout=30000)
    page.wait_for_timeout(400)
    return page
