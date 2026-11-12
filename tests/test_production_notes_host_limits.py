"""Production-note attachments must fit through the host's real request-size guard.

tests/test_production_notes.py mounts the notes router on a bare FastAPI app, so it never meets
main.BodySizeLimitMiddleware. Before this test existed the host refused every attachment over 1 MB
("Request body too large (max 1MB)") although a note may carry 10 MB per file and 25 MB in total.
This test puts the real middleware in front of the real router.
"""
from __future__ import annotations

import io
import json
import os

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import main
from modules import auth, userdb
from modules import production_notes as pn

PW = "Str0ng-Production-Pass!"


@pytest.fixture()
def guarded(tmp_path, monkeypatch):
    monkeypatch.setattr(userdb, "_DB_PATH", tmp_path / "users.db")
    userdb._sync_init_db()
    assert userdb._sync_create_owner_via_setup("josie", PW, "", "Josie")
    spots = tmp_path / "note_spots.json"
    spots.write_text(json.dumps({"spots": {"mirror": {"label": "Makeup mirror"}}}), encoding="utf-8")
    app = FastAPI()
    app.add_middleware(main.BodySizeLimitMiddleware)
    app.include_router(pn.create_production_notes_router(tmp_path / "data", spots))
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + auth.create_access_token({"sub": "josie", "role": "owner"})}
    me = client.get("/api/profile/me", headers=headers).json()
    return client, headers, me["user_id"], tmp_path


def _send(client, headers, me, sizes):
    files = [("files", (f"f{i}.bin", io.BytesIO(os.urandom(n)), "application/octet-stream")) for i, n in enumerate(sizes)]
    return client.post("/api/notes", headers=headers, files=files,
                       data={"note": json.dumps({"subject": "attachments", "to": [me]})})


def test_the_guard_allows_what_the_notes_route_allows():
    assert main.BodySizeLimitMiddleware.limit_for("/api/notes") > pn.FILES_TOTAL_MAX
    # The other note routes carry no bodies of that size and keep the default ceiling.
    assert main.BodySizeLimitMiddleware.limit_for("/api/notes/n_0123456789abcdef0123/save") == main.BodySizeLimitMiddleware.MAX_BODY


def test_attachments_above_one_megabyte_arrive_through_the_guard(guarded):
    client, headers, me, _ = guarded
    response = _send(client, headers, me, [pn.FILE_BYTES_MAX])
    assert response.status_code == 201, response.text
    assert response.json()["files"] == 1


def test_the_route_still_enforces_its_own_ceilings_behind_the_guard(guarded):
    client, headers, me, root = guarded
    assert _send(client, headers, me, [pn.FILE_BYTES_MAX + 1]).status_code == 413
    # Three files of 9 MB are 27 MB: over the 25 MB note total, and over the guard as well. Either refusal is correct;
    # what must not happen is acceptance.
    assert _send(client, headers, me, [9 * 1024 * 1024] * 3).status_code == 413
    # And nothing refused is left behind on disk.
    notes_root = root / "data" / "notes"
    assert list((notes_root / "incoming").iterdir()) == []
    assert [p for p in (notes_root / "files").iterdir()] == []


def test_a_refused_note_leaves_no_temporary_upload_files_open(guarded):
    """The route parses the multipart form itself, so it must close it: uploads over 1 MB spool to disk."""
    import gc
    import warnings
    client, headers, me, _ = guarded
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert _send(client, headers, me, [pn.FILE_BYTES_MAX + 1]).status_code == 413
        # A note with nobody to send to is refused after the files were already received by the parser.
        files = [("files", ("big.bin", io.BytesIO(os.urandom(3 * 1024 * 1024)), "application/octet-stream"))]
        assert client.post("/api/notes", headers=headers, files=files, data={"note": json.dumps({"subject": "x", "to": []})}).status_code == 400
        gc.collect()
    assert [str(w.message) for w in caught if "Unclosed file" in str(w.message) or "unclosed file" in str(w.message)] == []
