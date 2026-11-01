"""Portable disk saving, conflicts and identity boundaries without browser APIs."""

import base64
from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules.auth import create_access_token
from modules.foresight_workspace import create_workspace_router


def test_disk_files_reopen_after_router_restart_and_reject_conflicts(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")

    def client():
        app = FastAPI()
        app.include_router(create_workspace_router(tmp_path))
        return TestClient(app)

    headers = {
        "Authorization": "Bearer "
        + create_access_token({"sub": "writer", "role": "owner"})
    }
    data = {
        "path": "Scripts/example.py",
        "data": base64.b64encode(b'print("offline")\n').decode(),
    }
    c = client()
    assert c.post("/api/foresight/workspace/file", json=data).status_code == 401
    r = c.post("/api/foresight/workspace/file", headers=headers, json=data)
    assert r.status_code == 200, r.text
    saved = r.json()
    c.close()
    c = client()
    r = c.get(
        "/api/foresight/workspace/file", params={"path": data["path"]}, headers=headers
    )
    assert base64.b64decode(r.json()["data"]) == b'print("offline")\n'
    assert list(tmp_path.rglob("example.py"))[0].read_bytes() == b'print("offline")\n'
    assert (
        c.post("/api/foresight/workspace/file", headers=headers, json=data).status_code
        == 409
    )
    data["expected_revision"] = saved["revision"]
    data["data"] = base64.b64encode(b"edited").decode()
    assert (
        c.post("/api/foresight/workspace/file", headers=headers, json=data).status_code
        == 200
    )
    assert (
        c.post("/api/foresight/workspace/file", headers=headers, json=data).status_code
        == 409
    )
    for path in [
        "../outside.py",
        "/outside.py",
        "C:/outside.py",
        ".hidden/file",
        "CON",
        "Scripts/NUL.txt",
        "trailing. ",
    ]:
        assert (
            c.get(
                "/api/foresight/workspace/file", params={"path": path}, headers=headers
            ).status_code
            == 422
        )
    other = {
        "Authorization": "Bearer "
        + create_access_token({"sub": "different-writer", "role": "owner"})
    }
    assert c.get("/api/foresight/workspace/files", headers=other).json()["files"] == []
    assert (
        c.get(
            "/api/foresight/workspace/file",
            headers=other,
            params={"path": "Scripts/example.py"},
        ).status_code
        == 404
    )


def test_python_syntax_check_does_not_execute_source(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    app = FastAPI()
    app.include_router(create_workspace_router(tmp_path))
    c = TestClient(app)
    sentinel = tmp_path / "should-not-exist"
    assert c.post(
        "/api/foresight/workspace/check-python",
        json={"text": f'open({str(sentinel)!r},"w").write("wrong")'},
    ).json()["ok"]
    assert not sentinel.exists()
    result = c.post(
        "/api/foresight/workspace/check-python", json={"text": "if broken\n  pass"}
    ).json()
    assert not result["ok"] and result["line"] == 1


def test_optional_sidecar_does_not_install_on_normal_startup(tmp_path, monkeypatch):
    from modules.foresight_sidecar import Legacy2iService

    (tmp_path / "2i-backend").mkdir()
    (tmp_path / "2i-backend" / "server.js").write_text("")
    monkeypatch.setattr(
        "modules.foresight_sidecar.shutil.which", lambda _: "/installed/tool"
    )

    def forbidden(*a, **k):
        raise AssertionError("Normal startup attempted an installer")

    monkeypatch.setattr("modules.foresight_sidecar.subprocess.run", forbidden)
    service = Legacy2iService(tmp_path, tmp_path / "data", 8000)
    service.start()
    assert service.process is None
