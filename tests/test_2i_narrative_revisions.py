"""Regression contracts for durable 2i revision history."""
import sqlite3
from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules.writers_room import create_writers_room_router
from modules.route_security import current_identity


def build(tmp_path, identity):
    app = FastAPI()
    app.include_router(create_writers_room_router(tmp_path))
    app.dependency_overrides[current_identity] = lambda: identity.copy()
    return app


def payload(text, revision):
    return {"title":"Story","state":{"committed":[text]},"expected_revision":revision}


def test_history_conflicts_pagination_ownership_and_corruption(tmp_path):
    identity = {"user_id":"author-a","role":"owner"}
    path = "/api/writers-room/documents/story"
    with TestClient(build(tmp_path, identity)) as client:
        assert client.put(path,json=payload("first",0)).json()["revision"] == 1
        assert client.put(path,json=payload("second",1)).json()["revision"] == 2
        assert client.put(path,json=payload("stale",1)).status_code == 409
        page = client.get(path+"/revisions?limit=1").json()
        assert [x["revision"] for x in page["revisions"]] == [2]
        assert page["next_before"] == 2
        assert [x["revision"] for x in client.get(path+"/revisions?before=2").json()["revisions"]] == [1]
        assert client.get(path+"/revisions/1").json()["state"]["committed"] == ["first"]
        assert client.get(path).json()["state"]["committed"] == ["second"]
        identity["user_id"] = "author-b"
        assert client.get(path+"/revisions/1").status_code == 404
        assert client.get(path+"/revisions").json()["revisions"] == []
        assert client.put(path,json=payload("separate",0)).json()["revision"] == 1
        identity["user_id"] = "author-a"
        with sqlite3.connect(tmp_path/"writers_room"/"documents.sqlite3") as db:
            db.execute("UPDATE document_revisions SET digest='wrong' WHERE owner='author-a' AND revision=1")
        assert client.get(path+"/revisions/1").status_code == 500
        assert client.get(path).json()["state"]["committed"] == ["second"]


def test_migration_seeds_only_latest_existing_revision(tmp_path):
    import json
    folder=tmp_path/"writers_room"
    folder.mkdir()
    with sqlite3.connect(folder/"documents.sqlite3") as db:
        db.execute("CREATE TABLE documents (owner TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL,title TEXT NOT NULL,payload TEXT NOT NULL,updated REAL NOT NULL,PRIMARY KEY(owner,id))")
        body={"format":"2i-document","version":4,"title":"Story","state":{"committed":["legacy"]}}
        db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?)",("author-a","story",7,"Story",json.dumps(body),123.0))
    identity={"user_id":"author-a","role":"owner"}
    path="/api/writers-room/documents/story"
    with TestClient(build(tmp_path,identity)) as client:
        assert [r["revision"] for r in client.get(path+"/revisions").json()["revisions"]] == [7]
        assert client.get(path+"/revisions/6").status_code == 404
        assert client.get(path+"/revisions/7").json()["state"]["committed"] == ["legacy"]
        assert client.put(path,json=payload("next",7)).json()["revision"] == 8
    with TestClient(build(tmp_path,identity)) as client:
        assert [r["revision"] for r in client.get(path+"/revisions").json()["revisions"]] == [8,7]
