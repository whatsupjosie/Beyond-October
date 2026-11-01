"""Real-process probe for the minimal PubPartner control plane.

Proves the canonical launcher starts Alex/Jeremy/Pub Manager/Governance together,
permits bounded reversible containment, requires human review for bans, and
rejects replay of a consumed authority grant.
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


def _request(base: str, path: str, *, method: str = "GET", payload: dict | None = None,
             token: str = "") -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - loopback only
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
        time.sleep(0.25)
    raise TimeoutError("server did not become ready")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pubpartner_control_plane_") as tmp:
        data_dir = Path(tmp) / "data"
        log_path = Path(tmp) / "server.log"
        port = _free_port()
        base = f"http://127.0.0.1:{port}"
        log = log_path.open("a", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "run_pubpartner.py", "--no-browser", "--port", str(port), "--data-dir", str(data_dir)],
            cwd=ROOT,
            env={k: v for k, v in os.environ.items() if k != "PUBCAST_OWNER_PASSWORD"},
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            _wait(base, process)
            password = "Control!Plane7Proof"
            setup_status, setup = _request(base, "/api/auth/setup", method="POST", payload={
                "username": "owner",
                "password": password,
                "confirm_password": password,
            })
            token = str(setup.get("access_token") or "")

            health_status, health = _request(base, "/api/pubpartner/app-health")
            policy_status, policy = _request(base, "/api/pubmanager/policy", token=token)

            ban_status, ban = _request(base, "/api/pubmanager/authority/requests", method="POST", token=token, payload={
                "action": "ban_user",
                "target_user_id": "target-ban",
                "packet_user_id": "target-ban",
                "session_id": "control-session-ban",
                "requested_by": "owner",
                "urgency": "critical",
                "evidence": {"severity": 1.0, "confidence": 1.0, "security_risk": True, "repeat_count": 10},
                "ai_advisory": {"approved": True, "recommendation": "approve", "confidence": 1.0},
            })
            ban_row = ban.get("request") or {}

            freeze_status, freeze = _request(base, "/api/pubmanager/authority/requests", method="POST", token=token, payload={
                "action": "freeze_actor",
                "target_user_id": "target-freeze",
                "packet_user_id": "target-freeze",
                "session_id": "control-session-freeze",
                "requested_by": "owner",
                "urgency": "critical",
                "requested_duration_seconds": 30,
                "evidence": {"severity": 0.96, "confidence": 0.98, "security_risk": True, "repeat_count": 5},
            })
            freeze_row = freeze.get("request") or {}
            request_id = str(freeze_row.get("request_id") or "")

            action_payload = {
                "user_id": "target-freeze",
                "frozen_by": "owner",
                "reason": "control-plane probe",
                "duration_seconds": 30,
                "authority_source": "alex_jeremy",
                "authority_request_id": request_id,
                "authority_session_id": "control-session-freeze",
                "authority_user_id": "target-freeze",
            }
            execute_status, execute = _request(base, "/api/governance/freeze", method="POST", token=token, payload=action_payload)
            replay_status, replay = _request(base, "/api/governance/freeze", method="POST", token=token, payload=action_payload)

            ok = all([
                setup_status == 201,
                bool(token),
                health_status == 200,
                health.get("control_plane") == "alex_jeremy_pub_manager_governance",
                policy_status == 200,
                "ban_user" in ((policy.get("policy") or {}).get("actions") or policy.get("policy") or {}),
                ban_status == 200,
                ban_row.get("approved") is False,
                ban_row.get("status") == "human_required",
                freeze_status == 200,
                freeze_row.get("approved") is True,
                freeze_row.get("status") == "auto_approved",
                execute_status == 200,
                execute.get("ok") is True,
                replay_status == 403,
            ])
            report = {
                "ok": ok,
                "setup_status": setup_status,
                "health": health,
                "policy_status": policy_status,
                "ban": {"status": ban_status, "approved": ban_row.get("approved"), "decision": ban_row.get("status")},
                "freeze": {"status": freeze_status, "approved": freeze_row.get("approved"), "decision": freeze_row.get("status")},
                "execute_status": execute_status,
                "replay_status": replay_status,
            }
            print(json.dumps(report, indent=2))
            if not ok:
                print(log_path.read_text(encoding="utf-8", errors="replace")[-16000:], file=sys.stderr)
            return 0 if ok else 1
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
