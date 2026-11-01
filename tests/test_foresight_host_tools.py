"""Real owned shell process, authorization, lifecycle and supervised Quit."""

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import pytest
from modules.auth import create_access_token
from modules.foresight_host_tools import create_host_tools_router


def token(role="owner"):
    return create_access_token({"sub": "host-test", "role": role})


def test_quit_requires_actual_owner_and_supervisor(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    app = FastAPI()
    app.include_router(create_host_tools_router(tmp_path))
    client = TestClient(app)
    assert (
        client.post(
            "/api/foresight/host/quit", headers={"X-Dev-Role": "owner"}
        ).status_code
        == 403
    )
    headers = {"Authorization": "Bearer " + token()}
    assert client.post("/api/foresight/host/quit", headers=headers).status_code == 409
    called = []
    app.state.foresight_request_exit = lambda: called.append(True)
    assert (
        client.post("/api/foresight/host/quit", headers=headers).json()["status"]
        == "quitting"
    )
    assert called == [True]


def test_shell_executes_and_disconnect_cleans_up(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ALLOWED_ORIGINS", "http://testserver")
    app = FastAPI()
    app.include_router(create_host_tools_router(tmp_path))
    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/foresight/host/shell", headers={"origin": "http://testserver"}
        ) as ws:
            ws.send_json({"token": token()})
            started = ws.receive_json()
            assert started["type"] == "started"
            ws.send_json({"type": "input", "text": 'printf "CURTSEY_SHELL_OK\\n"\n'})
            output = ""
            while "CURTSEY_SHELL_OK" not in output:
                data = ws.receive_json()
                assert data["type"] == "output"
                output += data["text"]
            assert Path(started["cwd"]) == tmp_path / "workspace"
        deadline = time.monotonic() + 5
        while (
            client.get(
                "/api/foresight/host/status",
                headers={"Authorization": "Bearer " + token()},
            ).json()["shell_sessions"]
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        assert (
            client.get(
                "/api/foresight/host/status",
                headers={"Authorization": "Bearer " + token()},
            ).json()["shell_sessions"]
            == 0
        )
        import os

        if os.name != "nt":
            with pytest.raises(ProcessLookupError):
                os.kill(started["pid"], 0)


def test_shell_refuses_non_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ALLOWED_ORIGINS", "http://testserver")
    app = FastAPI()
    app.include_router(create_host_tools_router(tmp_path))
    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/foresight/host/shell", headers={"origin": "http://testserver"}
        ) as ws:
            ws.send_json({"token": token("guest")})
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


def test_python_working_copy_runs_locally_and_reports_traceback(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ALLOWED_ORIGINS", "http://testserver")
    app = FastAPI()
    app.include_router(create_host_tools_router(tmp_path))
    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/foresight/host/shell", headers={"origin": "http://testserver"}
        ) as ws:
            ws.send_json(
                {
                    "token": token(),
                    "mode": "python",
                    "name": "example.py",
                    "source": 'print("LOCAL_PYTHON_OK",flush=True)\nraise ValueError("visible traceback")\n',
                }
            )
            started = ws.receive_json()
            assert started["mode"] == "python"
            text = ""
            while True:
                message = ws.receive_json()
                if message["type"] == "exited":
                    assert message["code"] != 0
                    break
                text += message.get("text", "")
            assert "LOCAL_PYTHON_OK" in text and "ValueError: visible traceback" in text
            assert (Path(started["cwd"]) / "example.py").is_file()
