from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

from modules.persistence import unique_child_path
from modules.production_routes import create_production_router


class DummyCameras:
    def list_sources(self): return []
    def list_status(self): return []
    def get_program_source(self): return None
    def get_preview_source(self): return None
    def set_program_source(self, source_id): return True
    def set_preview_source(self, source_id): return True
    def register(self, source): return None


class DummyRecording:
    def __init__(self, base: Path):
        self.imports_dir = base
        self.imported_paths = []

    def list_profiles(self): return []
    def list_sessions(self): return []
    def storage_status(self): return {"ok": True}
    def privacy_matrix(self): return {"ok": True}

    def import_session(self, path: Path):
        self.imported_paths.append(path)
        return type("Session", (), {"to_dict": lambda self: {"session_id": path.stem}})()


def test_unique_child_path_avoids_clobbering(tmp_path):
    first = unique_child_path(tmp_path, "clip.zip")
    first.write_text("one", encoding="utf-8")
    second = unique_child_path(tmp_path, "clip.zip")
    assert second.name == "clip_1.zip"
    second.write_text("two", encoding="utf-8")
    third = unique_child_path(tmp_path, "clip.zip")
    assert third.name == "clip_2.zip"


def test_recording_import_avoids_overwriting_existing_zip(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    recording = DummyRecording(tmp_path)
    app = FastAPI()
    app.include_router(create_production_router(DummyCameras(), recording, None))

    existing = tmp_path / "bundle.zip"
    existing.write_bytes(b"existing")

    with TestClient(app) as client:
        response = client.post(
            "/api/recording/import",
            files={"file": ("bundle.zip", BytesIO(b"new-data"), "application/zip")},
        )
    assert response.status_code == 200
    assert existing.read_bytes() == b"existing"
    assert recording.imported_paths[-1].name == "bundle_1.zip"
    assert (tmp_path / "bundle_1.zip").read_bytes() == b"new-data"
