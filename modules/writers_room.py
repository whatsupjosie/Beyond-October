"""Reach's 2i document store: caller-scoped, transactional, revision checked.

Manuscripts remain documents. Saving a fictional scene never inserts facts into
partner or System Alex memory. The existing PubPartner spine owns live turns.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
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

    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS documents (
            owner TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL,
            title TEXT NOT NULL, payload TEXT NOT NULL, updated REAL NOT NULL,
            PRIMARY KEY(owner, id))""")

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
            rows = db.execute(
                "SELECT id,title,revision,updated FROM documents WHERE owner=? ORDER BY updated DESC",
                (identity["user_id"],),
            ).fetchall()
        return {"ok": True, "documents": [dict(row) for row in rows]}

    @router.get("/documents/{doc_id}")
    async def read_document(doc_id: str, identity=Depends(current_identity)):
        with connect() as db:
            row = db.execute("SELECT * FROM documents WHERE owner=? AND id=?", (identity["user_id"], document_id(doc_id))).fetchone()
        if row is None:
            raise HTTPException(404, "document not found")
        return {"ok": True, "id": doc_id, "revision": row["revision"], "updated": row["updated"], **json.loads(row["payload"])}

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
            db.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?)", (identity["user_id"], doc_id, revision, body.title, payload, now))
        return {"ok": True, "id": doc_id, "revision": revision, "updated": now}

    return router
