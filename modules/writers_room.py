"""Reach's 2i document store: caller-scoped, transactional, revision checked.

Manuscripts remain documents. Saving a fictional scene never inserts facts into
partner or System Alex memory. The existing PubPartner spine owns live turns.
"""
from __future__ import annotations

import json
import hashlib
import zlib
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .route_security import current_identity
from .local_model_config import default_provider


class DocumentWrite(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    state: dict[str, Any]
    expected_revision: int = Field(ge=0)
    format: str = "2i-document"
    version: int = 4

    @field_validator("state")
    @classmethod
    def validate_state(cls, value):
        for key in ("committed", "buffer", "pool"):
            rows = value.get(key, [])
            if not isinstance(rows, list) or any(not isinstance(row, str) for row in rows):
                raise ValueError(f"{key} must be an array of text lines")
        if len(json.dumps(value, ensure_ascii=False).encode()) > 2_000_000:
            raise ValueError("document exceeds 2 MB; export or split it before syncing")
        return value


class VersionAction(BaseModel):
    action: Literal["main", "working", "depart", "reactivate", "reviewed", "needs_review"]
    expected_epoch: int = Field(ge=0)
    expected_revision: int = Field(ge=1)


class VersionFork(BaseModel):
    source_revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)


def create_writers_room_router(data_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api/writers-room", tags=["writers-room"])
    folder = Path(data_dir) / "writers_room"
    folder.mkdir(parents=True, exist_ok=True)
    database = folder / "documents.sqlite3"

    @contextmanager
    def connect():
        db = sqlite3.connect(database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def ensure_root(db, owner, doc_id):
        db.execute("INSERT OR IGNORE INTO story_families VALUES (?,?,?,?,?)",
                   (owner,doc_id,doc_id,doc_id,0))
        db.execute("""INSERT OR IGNORE INTO story_versions
            (owner,document_id,family_id,ordinal,parent_id,parent_revision,departed,reviewed_revision)
            VALUES (?,?,?,1,NULL,NULL,0,NULL)""",(owner,doc_id,doc_id))

    def version_rows(db, owner, family_id=None):
        return [dict(r) for r in db.execute("""SELECT d.id,d.title,d.revision,d.updated,
            v.family_id,v.ordinal,v.parent_id,v.parent_revision,v.departed,v.reviewed_revision,
            f.main_id,f.working_id,f.epoch,
            CASE WHEN v.reviewed_revision=d.revision THEN 'reviewed' ELSE 'needs_review' END AS review_status
            FROM documents d JOIN story_versions v ON v.owner=d.owner AND v.document_id=d.id
            JOIN story_families f ON f.owner=v.owner AND f.family_id=v.family_id
            WHERE d.owner=? AND (? IS NULL OR v.family_id=?)
            ORDER BY v.family_id,v.ordinal""",(owner,family_id,family_id))]

    def version_row(db, owner, doc_id):
        row = db.execute("SELECT family_id FROM story_versions WHERE owner=? AND document_id=?",
                         (owner,doc_id)).fetchone()
        if row is None:
            raise HTTPException(404,"version not found")
        result=next((r for r in version_rows(db,owner,row["family_id"]) if r["id"]==doc_id),None)
        if result is None:
            raise HTTPException(409,"Version registry is inconsistent; preserve the document and repair its metadata.")
        return result

    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS documents (
            owner TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL,
            title TEXT NOT NULL, payload TEXT NOT NULL, updated REAL NOT NULL,
            PRIMARY KEY(owner, id))""")
        db.execute("""CREATE TABLE IF NOT EXISTS document_revisions (
            owner TEXT NOT NULL, document_id TEXT NOT NULL, revision INTEGER NOT NULL,
            title TEXT NOT NULL, payload BLOB NOT NULL, digest TEXT NOT NULL, updated REAL NOT NULL,
            PRIMARY KEY(owner, document_id, revision))""")
        # Preserve the latest available pre-upgrade snapshot; do not invent
        # older revisions that prior versions had replaced.
        missing = db.execute("""SELECT d.* FROM documents d
            WHERE NOT EXISTS (SELECT 1 FROM document_revisions r
                WHERE r.owner=d.owner AND r.document_id=d.id AND r.revision=d.revision)""").fetchall()
        for row in missing:
            raw = row["payload"].encode("utf-8")
            db.execute("INSERT OR IGNORE INTO document_revisions VALUES (?,?,?,?,?,?,?)",
                (row["owner"],row["id"],row["revision"],row["title"],zlib.compress(raw),hashlib.sha256(raw).hexdigest(),row["updated"]))

        db.execute("""CREATE TABLE IF NOT EXISTS story_families (
            owner TEXT NOT NULL, family_id TEXT NOT NULL, main_id TEXT NOT NULL,
            working_id TEXT NOT NULL, epoch INTEGER NOT NULL,
            PRIMARY KEY(owner,family_id))""")
        db.execute("""CREATE TABLE IF NOT EXISTS story_versions (
            owner TEXT NOT NULL, document_id TEXT NOT NULL, family_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL, parent_id TEXT, parent_revision INTEGER,
            departed INTEGER NOT NULL DEFAULT 0, reviewed_revision INTEGER,
            PRIMARY KEY(owner,document_id), UNIQUE(owner,family_id,ordinal))""")
        # Before this feature no reliable lineage was stored. Existing documents
        # become independent roots; do not infer relationships from their titles.
        for row in db.execute("""SELECT d.owner,d.id FROM documents d
            LEFT JOIN story_versions v ON v.owner=d.owner AND v.document_id=d.id
            WHERE v.document_id IS NULL""").fetchall():
            ensure_root(db,row["owner"],row["id"])

    def document_id(value):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
            raise HTTPException(400, "invalid document id")
        return value

    @router.get("/config")
    async def config(identity=Depends(current_identity)):
        return {
            "ok": True, "user_id": identity["user_id"], "build": "reach-writers-room-1",
            "provider": default_provider(),
            "documents": "server", "partner_status_url": "/api/pubpartner/status",
        }

    @router.get("/documents")
    async def documents(identity=Depends(current_identity)):
        with connect() as db:
            rows = version_rows(db,identity["user_id"])
        return {"ok":True,"documents":sorted(rows,key=lambda r:r["updated"],reverse=True)}

    @router.get("/documents/{doc_id}")
    async def read_document(doc_id: str, identity=Depends(current_identity)):
        with connect() as db:
            row = db.execute("SELECT * FROM documents WHERE owner=? AND id=?", (identity["user_id"], document_id(doc_id))).fetchone()
        if row is None:
            raise HTTPException(404, "document not found")
        return {"ok": True, "id": doc_id, "revision": row["revision"], "updated": row["updated"], **json.loads(row["payload"])}

    @router.get("/documents/{doc_id}/revisions")
    async def list_revisions(doc_id: str, limit: int = Query(100, ge=1, le=500),
                             before: int | None = Query(None, ge=1),
                             identity=Depends(current_identity)):
        doc_id = document_id(doc_id)
        with connect() as db:
            rows = db.execute("""SELECT revision,title,updated FROM document_revisions
                WHERE owner=? AND document_id=? AND (? IS NULL OR revision < ?)
                ORDER BY revision DESC LIMIT ?""",
                (identity["user_id"],doc_id,before,before,limit+1)).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        return {"ok":True,"id":doc_id,"revisions":[dict(row) for row in rows],
                "next_before":rows[-1]["revision"] if more else None}

    @router.get("/documents/{doc_id}/revisions/{number}")
    async def read_revision(doc_id: str, number: int, identity=Depends(current_identity)):
        doc_id = document_id(doc_id)
        with connect() as db:
            row = db.execute("""SELECT revision,payload,digest,updated FROM document_revisions
                WHERE owner=? AND document_id=? AND revision=?""",
                (identity["user_id"],doc_id,number)).fetchone()
        if row is None:
            raise HTTPException(404,"document revision not found")
        try:
            raw = zlib.decompress(row["payload"])
            if hashlib.sha256(raw).hexdigest() != row["digest"]:
                raise ValueError("revision checksum mismatch")
            payload = json.loads(raw)
        except (ValueError, TypeError, zlib.error, UnicodeError) as error:
            raise HTTPException(500,"Stored revision failed integrity verification; no replacement was made") from error
        return {"ok":True,"id":doc_id,"revision":row["revision"],"updated":row["updated"],**payload}

    @router.get("/documents/{doc_id}/versions")
    async def versions(doc_id: str, identity=Depends(current_identity)):
        owner=identity["user_id"]
        with connect() as db:
            db.execute("BEGIN")  # One consistent family snapshot across both reads.
            current=version_row(db,owner,document_id(doc_id))
            rows=version_rows(db,owner,current["family_id"])
        return {"ok":True,"current":current,"versions":rows}

    @router.post("/documents/{doc_id}/version-action")
    async def change_version(doc_id: str, body: VersionAction, identity=Depends(current_identity)):
        owner=identity["user_id"]
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            v=version_row(db,owner,document_id(doc_id))
            if v["epoch"]!=body.expected_epoch or v["revision"]!=body.expected_revision:
                raise HTTPException(409,"Version changed; refresh before applying this action.")
            action=body.action
            if action in ("main","working") and v["departed"]:
                raise HTTPException(409,"Reactivate this departed version first.")
            if action=="depart" and doc_id in (v["main_id"],v["working_id"]):
                raise HTTPException(409,"Select another main and/or working version first.")
            if action=="main":
                db.execute("UPDATE story_families SET main_id=? WHERE owner=? AND family_id=?",(doc_id,owner,v["family_id"]))
            elif action=="working":
                db.execute("UPDATE story_families SET working_id=? WHERE owner=? AND family_id=?",(doc_id,owner,v["family_id"]))
            elif action in ("depart","reactivate"):
                db.execute("UPDATE story_versions SET departed=? WHERE owner=? AND document_id=?",(int(action=="depart"),owner,doc_id))
            else:
                db.execute("UPDATE story_versions SET reviewed_revision=? WHERE owner=? AND document_id=?",
                           (v["revision"] if action=="reviewed" else None,owner,doc_id))
            db.execute("UPDATE story_families SET epoch=epoch+1 WHERE owner=? AND family_id=?",(owner,v["family_id"]))
            return {"ok":True,"current":version_row(db,owner,doc_id)}

    @router.post("/documents/{doc_id}/fork")
    async def fork_version(doc_id: str, body: VersionFork, identity=Depends(current_identity)):
        """Fork a confirmed saved revision without modifying its source."""
        owner=identity["user_id"]
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            source=version_row(db,owner,document_id(doc_id))
            row=db.execute("""SELECT payload,digest FROM document_revisions
                WHERE owner=? AND document_id=? AND revision=?""",(owner,doc_id,body.source_revision)).fetchone()
            if row is None:
                raise HTTPException(404,"source revision not found")
            try:
                raw=zlib.decompress(row["payload"])
                if hashlib.sha256(raw).hexdigest()!=row["digest"]:
                    raise ValueError("checksum")
                payload=json.loads(raw)
                payload["title"]=body.title
                payload["state"]["conversationIds"]={}
                raw=json.dumps(payload,ensure_ascii=False).encode("utf-8")
            except (ValueError,TypeError,KeyError,zlib.error,UnicodeError) as error:
                raise HTTPException(500,"Source revision failed integrity verification; no fork was created") from error
            new_id=uuid.uuid4().hex
            ordinal=db.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM story_versions WHERE owner=? AND family_id=?",
                               (owner,source["family_id"])).fetchone()[0]
            now=time.time()
            db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?)",(owner,new_id,1,body.title,raw.decode("utf-8"),now))
            db.execute("INSERT INTO document_revisions VALUES (?,?,?,?,?,?,?)",
                       (owner,new_id,1,body.title,zlib.compress(raw),hashlib.sha256(raw).hexdigest(),now))
            db.execute("""INSERT INTO story_versions
                (owner,document_id,family_id,ordinal,parent_id,parent_revision,departed,reviewed_revision)
                VALUES (?,?,?,?,?,?,0,NULL)""",(owner,new_id,source["family_id"],ordinal,doc_id,body.source_revision))
            db.execute("UPDATE story_families SET epoch=epoch+1 WHERE owner=? AND family_id=?",(owner,source["family_id"]))
            return {"ok":True,"id":new_id,"revision":1,**payload,"version_info":version_row(db,owner,new_id)}

    @router.put("/documents/{doc_id}")
    async def write_document(doc_id: str, body: DocumentWrite, identity=Depends(current_identity)):
        document_id(doc_id)
        if body.format != "2i-document" or body.version != 4:
            raise HTTPException(400, "unsupported document format/version")
        payload = json.dumps({"format": body.format, "version": body.version, "title": body.title, "state": body.state}, ensure_ascii=False)
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT revision FROM documents WHERE owner=? AND id=?", (identity["user_id"], doc_id)).fetchone()
            revision = current["revision"] if current else 0
            if revision != body.expected_revision:
                raise HTTPException(409, {"error": "revision_conflict", "revision": revision, "message": "This document changed elsewhere. Save a copy or reload before continuing."})
            revision += 1
            now = time.time()
            raw = payload.encode("utf-8")
            db.execute("INSERT INTO document_revisions VALUES (?,?,?,?,?,?,?)",
                (identity["user_id"],doc_id,revision,body.title,zlib.compress(raw),hashlib.sha256(raw).hexdigest(),now))
            db.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?)", (identity["user_id"], doc_id, revision, body.title, payload, now))
            if not current:
                ensure_root(db,identity["user_id"],doc_id)
        return {"ok": True, "id": doc_id, "revision": revision, "updated": now}

    return router
