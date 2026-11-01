"""Independent fresh-process HTTP/restart probe; all user data is disposable."""
from __future__ import annotations
import argparse
import json
import hashlib
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--launcher", choices=["run_reach.py", "start_reach.py"], default="run_reach.py")
    args = parser.parse_args()
    evidence = {"transport": "real HTTP over loopback", "launcher": args.launcher, "model_generation_tested": False, "checks": []}
    with tempfile.TemporaryDirectory(prefix="reach-http-") as tmp:
        data = Path(tmp) / "data"
        log = Path(tmp) / "boot.log"
        with socket.socket() as free:
            free.bind(("127.0.0.1", 0)); port = free.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = dict(os.environ)
        for key in ("PUBCAST_OWNER_PASSWORD", "PUBCAST_OWNER_USERNAME", "PUBCAST_JWT_SECRET", "PUBCAST_DATA_DIR"):
            env.pop(key, None)
        process = None
        def start():
            nonlocal process
            with log.open("a") as output:
                process = subprocess.Popen([sys.executable, args.launcher, "--no-browser", "--port", str(port), "--data-dir", str(data)], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
            until = time.monotonic() + 40
            while time.monotonic() < until:
                if process.poll() is not None:
                    raise RuntimeError("Reach exited during boot: " + log.read_text()[-3000:])
                try:
                    r = httpx.get(base + "/api/auth/status", timeout=0.8, trust_env=False)
                    if r.status_code == 200: return
                except httpx.HTTPError:
                    pass
                time.sleep(0.15)
            raise RuntimeError("HTTP startup timeout")
        def stop():
            if process is not None and process.poll() is None:
                process.terminate()
                try: process.wait(8)
                except subprocess.TimeoutExpired: process.kill(); process.wait(3)
        try:
            start()
            with httpx.Client(base_url=base, timeout=8, trust_env=False) as client:
                assert client.get("/writers-room").status_code == 200
                assert client.get("/2i-assets/reach.js").status_code == 200
                assert client.get("/2i-assets/reach.css").status_code == 200
                assert client.get("/2i-assets/artwork.js").status_code == 200
                assert client.get("/2i-assets/artwork.css").status_code == 200
                phone_page = client.get("/writers-room?view=phone")
                assert phone_page.status_code == 200
                assert '2i-assets/phone.js' in phone_page.text
                for asset in ("phone.js", "phone.css", "reader.js", "reader.css", "desk-controls.js", "button-bindings.js"):
                    response = client.get("/2i-assets/" + asset)
                    assert response.status_code == 200
                    assert response.content == (ROOT / "2i" / "2i-assets" / asset).read_bytes()
                evidence["checks"].append("phone entry and exact phone JS/CSS assets served")
                map_response = client.get("/2i-assets/hotspots.json")
                assert map_response.status_code == 200
                artwork = client.get("/2i-assets/writers-room-art.webp")
                assert artwork.status_code == 200
                assert hashlib.sha256(artwork.content).hexdigest() == map_response.json()["image"]["sha256"]
                evidence["checks"].append("original picture hash and button map served intact")
                evidence["checks"].append("fresh launcher boot and UI/assets 200")
                assert client.get("/api/auth/status").json()["setup_required"]
                assert client.get("/api/writers-room/documents").status_code == 401
                password = secrets.token_urlsafe(24) + "Aa9!"
                setup = client.post("/api/auth/setup", json={"username": "audit_writer", "password": password, "confirm_password": password})
                assert setup.status_code == 201, setup.text
                token = setup.json()["access_token"]
                client.headers["Authorization"] = "Bearer " + token
                doc = {"title": "HTTP restart proof", "expected_revision": 0, "state": {"committed": ["Synthetic manuscript — exact  spaces.", "", "End."], "buffer": [], "pool": []}}
                saved = client.put("/api/writers-room/documents/proof", json=doc)
                assert saved.status_code == 200, saved.text
                assert client.get("/api/writers-room/documents/proof").json()["state"] == doc["state"]
                assert client.get("/api/pubpartner/status").json()["live_loop"]
                evidence["checks"].append("owner setup, authenticated save/read, PubPartner runtime ready")
            stop(); start()
            with httpx.Client(base_url=base, timeout=8, trust_env=False, headers={"Authorization": "Bearer " + token}) as client:
                restored = client.get("/api/writers-room/documents/proof")
                assert restored.status_code == 200, restored.text
                assert restored.json()["state"] == doc["state"]
                assert restored.json()["revision"] == 1
                assert not client.get("/api/auth/status").json()["setup_required"]
                evidence["checks"].append("process restart preserves token, account, manuscript and revision")
            evidence["ok"] = True
        finally:
            stop()
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
