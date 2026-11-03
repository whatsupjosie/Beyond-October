# PubCast AI — production_notes.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""Production notes: the sticky notes people in a production leave for each other, plus the PubCast profile they hang on.

A note is laid out like an email (from, to, CC, BCC, subject, message, attachments), with an optional project so the
notes menu can group by project as well as by date. A note can be to yourself. In the studio it shows as a sticky
note: on the recipient's makeup mirror always, and on any other spot the sender chose for them (the audio console, the
director's console...). Notes live on this PubCast host, so they wait for people who are offline and survive restarts.

People
    Everyone with an account on this PubCast is in the production. The owner makes the first account at setup; the
    owner or a moderator adds crew accounts from the profile page. Each account has a profile with a permanent user ID,
    a display name and an optional email (used only to address a copy of a note in the sender's own email program).

Storage
    <data>/users.db          profiles (see modules/userdb.py)
    <data>/notes/notes.db    notes, who each one is for, read / saved / trashed per person, attachments
    <data>/notes/files/      attachment bytes, stored under random names; served only to the sender and recipients

Routes
    GET   /api/profile/me                 your profile
    PATCH /api/profile/me                 change your display name or email
    POST  /api/profile/password           change your password (current password required)
    GET   /api/production/people          everyone in the production (members only)
    POST  /api/production/people          add a crew account (owner or moderator)
    GET   /api/notes/spots                where a note can be stuck
    GET   /api/notes?box=inbox|saved|sent your notes, newest first (each with its optional project, for grouping)
    POST  /api/notes                      send a note (JSON, or multipart with attachments)
    GET   /api/notes/{id}[?mark_read=1]   one note in full; BCC is shown only to its sender
    POST  /api/notes/{id}/read | save | unsave | trash
    GET   /api/notes/{id}/files/{file_id} an attachment (download)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from modules import userdb
from modules.auth import get_password_hash, role_gte, verify_password
from modules.route_security import current_identity

logger = logging.getLogger(__name__)

SUBJECT_MAX = 120
PROJECT_MAX = 60
BODY_MAX = 20_000
RECIPIENTS_MAX = 200
FILES_MAX = 8
FILE_BYTES_MAX = 10 * 1024 * 1024
FILES_TOTAL_MAX = 25 * 1024 * 1024
FILENAME_MAX = 120
LIST_LIMIT_MAX = 500
PRODUCTION = "@production"            # "everyone in the production but me"
KINDS = ("to", "cc", "bcc")
NOTE_ID_RE = re.compile(r"^n_[0-9a-f]{20}$")
FILE_ID_RE = re.compile(r"^f_[0-9a-f]{20}$")
ALWAYS_SPOT = "mirror"


def _now() -> float:
    return time.time()


def _clean_text(value: Any, limit: int, what: str, *, single_line: bool) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise HTTPException(400, f"{what} must be text")
    value = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    value = "".join(ch for ch in value if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    if single_line:
        value = " ".join(value.split())
    value = value.strip()
    if len(value) > limit:
        raise HTTPException(400, f"{what} is longer than {limit:,} characters")
    return value


def _clean_filename(name: str) -> str:
    name = unicodedata.normalize("NFC", (name or "").replace("\\", "/").rsplit("/", 1)[-1])
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip().strip(".")
    if len(name) > FILENAME_MAX:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: FILENAME_MAX - len(ext) - 1] + "." + ext) if dot and len(ext) <= 10 else name[:FILENAME_MAX]
    return name or "attachment"


class Spots:
    """The places a note can be stuck, read from the studio's own spot file so the host and the walker agree."""

    def __init__(self, path: Path):
        self.path = path
        self._cache: Tuple[float, Dict[str, Any]] = (-1.0, {})

    def catalog(self) -> Dict[str, Any]:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return {ALWAYS_SPOT: {"label": "Makeup mirror", "always": True}}
        if mtime != self._cache[0]:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                spots = data.get("spots") if isinstance(data, dict) else None
                self._cache = (mtime, spots if isinstance(spots, dict) else {})
            except (OSError, ValueError):
                logger.exception("production notes: could not read %s", self.path)
                self._cache = (mtime, {})
        cat = dict(self._cache[1])
        cat.setdefault(ALWAYS_SPOT, {"label": "Makeup mirror", "always": True})
        return cat

    def clean(self, chosen: Any) -> List[str]:
        if chosen is None:
            chosen = []
        if not isinstance(chosen, list) or not all(isinstance(s, str) for s in chosen):
            raise HTTPException(400, "spots must be a list of spot names")
        cat = self.catalog()
        unknown = sorted({s for s in chosen if s not in cat})
        if unknown:
            raise HTTPException(400, "Unknown spot: " + ", ".join(unknown))
        out = [ALWAYS_SPOT]                       # the mirror always gets a copy
        for s in chosen:
            if s not in out:
                out.append(s)
        return out


class NotesStore:
    def __init__(self, root: Path):
        self.root = root
        self.files = root / "files"
        self.files.mkdir(parents=True, exist_ok=True)
        self.db_path = root / "notes.db"
        self._lock = threading.Lock()
        with self._conn() as conn:
            conn.executescript("""
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS notes (
                    id          TEXT PRIMARY KEY,
                    sender_id   TEXT NOT NULL,
                    subject     TEXT NOT NULL,
                    body        TEXT NOT NULL,
                    created_at  REAL NOT NULL,
                    reply_to    TEXT,
                    thread_id   TEXT NOT NULL,
                    sender_trashed_at REAL,
                    project     TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS recipients (
                    note_id     TEXT NOT NULL REFERENCES notes(id),
                    user_id     TEXT NOT NULL,
                    kind        TEXT NOT NULL CHECK (kind IN ('to','cc','bcc')),
                    spots       TEXT NOT NULL DEFAULT '["mirror"]',
                    read_at     REAL,
                    saved       INTEGER NOT NULL DEFAULT 0,
                    trashed_at  REAL,
                    PRIMARY KEY (note_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS files (
                    id          TEXT PRIMARY KEY,
                    note_id     TEXT NOT NULL REFERENCES notes(id),
                    name        TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size        INTEGER NOT NULL,
                    sha256      TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_recipients_user ON recipients(user_id, trashed_at);
                CREATE INDEX IF NOT EXISTS idx_notes_sender ON notes(sender_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_files_note ON files(note_id);
            """)
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(notes)")}
            if "project" not in cols:                     # a notes.db from before projects existed
                conn.execute("ALTER TABLE notes ADD COLUMN project TEXT NOT NULL DEFAULT ''")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # -- writing --
    def create(self, sender_id: str, subject: str, body: str, recipients: List[Tuple[str, str]], spots: List[str],
               reply_to: Optional[str], files: List[Dict[str, Any]], project: str = "") -> str:
        """recipients: (user_id, kind). files: dicts with id, name, content_type, size, sha256, tmp (a written file)."""
        note_id = "n_" + secrets.token_hex(10)
        created = _now()
        with self._lock, self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                thread_id = note_id
                if reply_to:
                    row = conn.execute("SELECT thread_id FROM notes WHERE id = ?", (reply_to,)).fetchone()
                    thread_id = row["thread_id"] if row else note_id
                conn.execute("INSERT INTO notes (id, sender_id, subject, body, created_at, reply_to, thread_id, project) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (note_id, sender_id, subject, body, created, reply_to, thread_id, project))
                spots_json = json.dumps(spots)
                conn.executemany("INSERT INTO recipients (note_id, user_id, kind, spots) VALUES (?, ?, ?, ?)",
                                 [(note_id, uid, kind, spots_json) for uid, kind in recipients])
                folder = self.files / note_id
                if files:
                    folder.mkdir(parents=True, exist_ok=False)
                for f in files:
                    f["tmp"].replace(folder / f["id"])            # same disk: an atomic rename into place
                    conn.execute("INSERT INTO files (id, note_id, name, content_type, size, sha256) VALUES (?, ?, ?, ?, ?, ?)",
                                 (f["id"], note_id, f["name"], f["content_type"], f["size"], f["sha256"]))
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                for f in files:                                   # nothing half-saved: put no files where nothing points to them
                    for p in (self.files / note_id / f["id"], f["tmp"]):
                        try:
                            p.unlink()
                        except OSError:
                            pass
                try:
                    (self.files / note_id).rmdir()
                except OSError:
                    pass
                raise
        return note_id

    def mark(self, note_id: str, user_id: str, field: str) -> bool:
        sql = {
            "read": "UPDATE recipients SET read_at = COALESCE(read_at, ?) WHERE note_id = ? AND user_id = ? AND trashed_at IS NULL",
            "save": "UPDATE recipients SET saved = 1, read_at = COALESCE(read_at, ?) WHERE note_id = ? AND user_id = ? AND trashed_at IS NULL",
            "unsave": "UPDATE recipients SET saved = 0 WHERE ? IS NOT NULL AND note_id = ? AND user_id = ? AND trashed_at IS NULL",
            "trash": "UPDATE recipients SET trashed_at = ?, read_at = COALESCE(read_at, trashed_at, ?) WHERE note_id = ? AND user_id = ? AND trashed_at IS NULL",
        }[field]
        now = _now()
        args = (now, now, note_id, user_id) if field == "trash" else (now, note_id, user_id)
        with self._lock, self._conn() as conn:
            changed = conn.execute(sql, args).rowcount
            if field == "trash" and not changed:          # the sender taking their own copy out of Sent
                changed = conn.execute("UPDATE notes SET sender_trashed_at = ? WHERE id = ? AND sender_id = ? "
                                       "AND sender_trashed_at IS NULL", (now, note_id, user_id)).rowcount
        return bool(changed)

    # -- reading --
    def list(self, user_id: str, box: str, limit: int) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            if box == "sent":
                rows = conn.execute(
                    "SELECT n.*, NULL AS kind, '[]' AS spots, 1 AS is_read, 0 AS saved, "
                    "(SELECT COUNT(*) FROM files f WHERE f.note_id = n.id) AS file_count "
                    "FROM notes n WHERE n.sender_id = ? AND n.sender_trashed_at IS NULL "
                    "ORDER BY n.created_at DESC LIMIT ?", (user_id, limit)).fetchall()
            else:
                saved_only = "AND r.saved = 1" if box == "saved" else ""
                rows = conn.execute(
                    "SELECT n.*, r.kind, r.spots, (r.read_at IS NOT NULL) AS is_read, r.saved, "
                    "(SELECT COUNT(*) FROM files f WHERE f.note_id = n.id) AS file_count "
                    f"FROM recipients r JOIN notes n ON n.id = r.note_id WHERE r.user_id = ? AND r.trashed_at IS NULL {saved_only} "
                    "ORDER BY n.created_at DESC LIMIT ?", (user_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def get(self, note_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """The note as `user_id` may see it, or None. The sender sees everything; a recipient sees To and CC only."""
        with self._conn() as conn:
            note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
            if not note:
                return None
            mine = conn.execute("SELECT * FROM recipients WHERE note_id = ? AND user_id = ?", (note_id, user_id)).fetchone()
            is_sender = note["sender_id"] == user_id
            if not is_sender and (mine is None or mine["trashed_at"] is not None):
                return None
            people = conn.execute("SELECT user_id, kind FROM recipients WHERE note_id = ? ORDER BY rowid", (note_id,)).fetchall()
            files = conn.execute("SELECT id, name, content_type, size FROM files WHERE note_id = ? ORDER BY rowid", (note_id,)).fetchall()
        out = dict(note)
        out["is_sender"] = is_sender
        out["to"] = [p["user_id"] for p in people if p["kind"] == "to"]
        out["cc"] = [p["user_id"] for p in people if p["kind"] == "cc"]
        out["bcc"] = [p["user_id"] for p in people if p["kind"] == "bcc"] if is_sender else []
        out["you_were_bcc"] = bool(mine and mine["kind"] == "bcc")
        out["spots"] = json.loads(mine["spots"]) if mine else []
        out["is_read"] = bool(mine and mine["read_at"] is not None) or is_sender
        out["saved"] = bool(mine and mine["saved"])
        out["files"] = [dict(f) for f in files]
        return out

    def file(self, note_id: str, file_id: str, user_id: str) -> Optional[Tuple[Path, Dict[str, Any]]]:
        if self.get(note_id, user_id) is None:
            return None
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM files WHERE id = ? AND note_id = ?", (file_id, note_id)).fetchone()
        if not row:
            return None
        path = self.files / note_id / file_id
        return (path, dict(row)) if path.is_file() else None


def create_production_notes_router(data_dir: Path, spots_file: Path) -> APIRouter:
    router = APIRouter(tags=["production-notes"])
    store = NotesStore(Path(data_dir) / "notes")
    spots = Spots(spots_file)
    incoming = store.root / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    for stale in incoming.glob("*"):                 # uploads a crash left half-written: never attached to anything
        try:
            stale.unlink()
        except OSError:
            pass

    async def me(identity: Dict[str, Any] = Depends(current_identity)) -> Dict[str, Any]:
        # Only a signed-in person. With login switched off, a request can name anyone in a header; notes are private,
        # so that development shortcut never reaches them.
        if not identity.get("authenticated"):
            raise HTTPException(401, "Sign in to use production notes")
        name = str(identity.get("user_id") or "").strip()
        profile = await userdb.get_profile_by_username(name) if name else None
        if not profile:
            raise HTTPException(403, "You need a PubCast account on this host to use production notes")
        return profile

    def public(p: Dict[str, Any], *, with_email: bool) -> Dict[str, Any]:
        out = {"user_id": p["user_id"], "username": p["username"], "display_name": p["display_name"] or p["username"],
               "role": p.get("role", "guest")}
        if with_email:
            out["email"] = p.get("email", "")
        return out

    # ---------------------------------------------------------------- profile
    @router.get("/api/profile/me")
    async def profile_me(profile: Dict[str, Any] = Depends(me)) -> Dict[str, Any]:
        return dict(public(profile, with_email=True), created_at=profile["created_at"])

    @router.patch("/api/profile/me")
    async def profile_update(request: Request, profile: Dict[str, Any] = Depends(me)) -> Dict[str, Any]:
        body = await _json(request)
        unknown = set(body) - {"display_name", "email"}
        if unknown:
            raise HTTPException(400, "Only display_name and email can be changed here")
        for key in ("display_name", "email"):
            if key in body and not isinstance(body[key], str):
                raise HTTPException(400, f"{key} must be text")
        try:
            updated = await userdb.update_profile(profile["user_id"], body.get("display_name"), body.get("email"))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return dict(public(updated, with_email=True), created_at=updated["created_at"])

    @router.post("/api/profile/password")
    async def profile_password(request: Request, profile: Dict[str, Any] = Depends(me)) -> Dict[str, Any]:
        from modules.auth_routes import _validate_password      # the same password rules as first-run setup
        body = await _json(request)
        current, new = body.get("current_password"), body.get("new_password")
        if not isinstance(current, str) or not isinstance(new, str):
            raise HTTPException(400, "current_password and new_password are required")
        user = await userdb.get_user(profile["username"])
        if not user or not await run_in_threadpool(verify_password, current, user["hashed_password"]):
            raise HTTPException(403, "Your current password is not right")
        _validate_password(new, profile["username"])
        await userdb.update_password_hash(user["username"], await run_in_threadpool(get_password_hash, new))
        return {"ok": True}

    # ---------------------------------------------------------------- people
    @router.get("/api/production/people")
    async def people(profile: Dict[str, Any] = Depends(me)) -> Dict[str, Any]:
        everyone = await userdb.list_profiles()
        return {"me": profile["user_id"], "people": [public(p, with_email=True) for p in everyone]}

    @router.post("/api/production/people", status_code=201)
    async def add_person(request: Request, profile: Dict[str, Any] = Depends(me)) -> Dict[str, Any]:
        from modules.auth_routes import _USERNAME_RE, _validate_password
        if not role_gte(profile.get("role", "guest"), "mod"):
            raise HTTPException(403, "Only the owner or a moderator can add crew")
        body = await _json(request)
        username = str(body.get("username") or "").strip()
        password = body.get("password")
        role = str(body.get("role") or "guest")
        if not _USERNAME_RE.fullmatch(username):
            raise HTTPException(400, "Username may use letters, numbers, dot, dash, and underscore (3 to 64)")
        if not isinstance(password, str):
            raise HTTPException(400, "A starting password is required")
        if role == "mod" and profile.get("role") != "owner":
            raise HTTPException(403, "Only the owner can add a moderator")
        _validate_password(password, username)
        try:
            user_id = await userdb.create_member(username, password, role,
                                                 str(body.get("display_name") or ""), str(body.get("email") or ""))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if user_id is None:
            raise HTTPException(409, "That username is already taken")
        created = await userdb.get_profile(user_id)
        logger.info("production notes: %s added crew account %s (%s)", profile["username"], username, role)
        return public(created, with_email=True)

    # ---------------------------------------------------------------- notes
    @router.get("/api/notes/spots")
    async def spot_catalog(profile: Dict[str, Any] = Depends(me)) -> Dict[str, Any]:
        cat = spots.catalog()
        return {"always": ALWAYS_SPOT,
                "spots": [{"id": k, "label": v.get("label", k), "always": k == ALWAYS_SPOT} for k, v in cat.items()]}

    async def names() -> Dict[str, Dict[str, Any]]:
        return {p["user_id"]: p for p in await userdb.list_profiles()}

    def who(people_by_id: Dict[str, Dict[str, Any]], uid: str) -> Dict[str, Any]:
        p = people_by_id.get(uid)
        return {"user_id": uid, "display_name": (p["display_name"] or p["username"]) if p else "Former crew member"}

    @router.get("/api/notes")
    async def list_notes(box: str = "inbox", limit: int = 200, profile: Dict[str, Any] = Depends(me)) -> Dict[str, Any]:
        if box not in {"inbox", "saved", "sent"}:
            raise HTTPException(400, "box must be inbox, saved or sent")
        limit = max(1, min(int(limit), LIST_LIMIT_MAX))
        rows = await run_in_threadpool(store.list, profile["user_id"], box, limit)
        by_id = await names()
        notes = [{
            "id": r["id"], "subject": r["subject"], "from": who(by_id, r["sender_id"]), "created_at": r["created_at"],
            "unread": not r["is_read"], "saved": bool(r["saved"]), "spots": json.loads(r["spots"] or "[]"),
            "files": r["file_count"], "reply_to": r["reply_to"], "kind": r["kind"], "project": r["project"],
        } for r in rows]
        return {"box": box, "notes": notes, "unread": sum(1 for n in notes if n["unread"])}

    @router.get("/api/notes/{note_id}")
    async def get_note(note_id: str, mark_read: bool = False, profile: Dict[str, Any] = Depends(me)) -> Dict[str, Any]:
        _check_id(note_id)
        if mark_read:
            await run_in_threadpool(store.mark, note_id, profile["user_id"], "read")
        note = await run_in_threadpool(store.get, note_id, profile["user_id"])
        if note is None:
            raise HTTPException(404, "No such note")
        by_id = await names()
        return {
            "id": note["id"], "subject": note["subject"], "body": note["body"], "created_at": note["created_at"],
            "from": who(by_id, note["sender_id"]),
            "to": [who(by_id, u) for u in note["to"]], "cc": [who(by_id, u) for u in note["cc"]],
            "bcc": [who(by_id, u) for u in note["bcc"]], "you_were_bcc": note["you_were_bcc"],
            "is_sender": note["is_sender"], "spots": note["spots"], "unread": not note["is_read"], "saved": note["saved"],
            "reply_to": note["reply_to"], "thread_id": note["thread_id"], "project": note["project"],
            "files": [dict(f, url=f"/api/notes/{note['id']}/files/{f['id']}") for f in note["files"]],
        }

    @router.post("/api/notes/{note_id}/{action}")
    async def act(note_id: str, action: str, profile: Dict[str, Any] = Depends(me)) -> Dict[str, Any]:
        _check_id(note_id)
        if action not in {"read", "save", "unsave", "trash"}:
            raise HTTPException(404, "Unknown action")
        changed = await run_in_threadpool(store.mark, note_id, profile["user_id"], action)
        if not changed and await run_in_threadpool(store.get, note_id, profile["user_id"]) is None:
            raise HTTPException(404, "No such note")
        return {"ok": True, "changed": changed}

    @router.get("/api/notes/{note_id}/files/{file_id}")
    async def get_file(note_id: str, file_id: str, profile: Dict[str, Any] = Depends(me)):
        _check_id(note_id)
        if not FILE_ID_RE.fullmatch(file_id):
            raise HTTPException(404, "No such attachment")
        found = await run_in_threadpool(store.file, note_id, file_id, profile["user_id"])
        if not found:
            raise HTTPException(404, "No such attachment")
        path, row = found
        # Always a download, never rendered by the browser: an attachment is somebody else's file.
        return FileResponse(path, media_type="application/octet-stream", filename=row["name"],
                            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})

    @router.post("/api/notes", status_code=201)
    async def send(request: Request, profile: Dict[str, Any] = Depends(me)) -> Dict[str, Any]:
        ctype = request.headers.get("content-type", "")
        uploads: List[UploadFile] = []
        if ctype.startswith("multipart/form-data"):
            form = await request.form(max_files=FILES_MAX, max_fields=8)
            try:
                body = json.loads(str(form.get("note") or "{}"))
            except ValueError as exc:
                raise HTTPException(400, "The note part is not valid JSON") from exc
            uploads = [f for f in form.getlist("files") if isinstance(f, UploadFile)]
        else:
            body = await _json(request)
        if not isinstance(body, dict):
            raise HTTPException(400, "A note is a JSON object")

        subject = _clean_text(body.get("subject"), SUBJECT_MAX, "The subject", single_line=True)
        text = _clean_text(body.get("body"), BODY_MAX, "The message", single_line=False)
        if not subject:
            raise HTTPException(400, "A note needs a subject: it is what is written on the sticky note")
        project = _clean_text(body.get("project"), PROJECT_MAX, "The project", single_line=True)
        chosen_spots = spots.clean(body.get("spots"))

        everyone = await userdb.list_profiles()
        known = {p["user_id"] for p in everyone}
        crew = [p["user_id"] for p in everyone if p["user_id"] != profile["user_id"]]
        placed: Dict[str, str] = {}
        for kind in KINDS:                                       # To beats CC beats BCC when someone is in two lists
            listed = body.get(kind) or []
            if not isinstance(listed, list) or not all(isinstance(x, str) for x in listed):
                raise HTTPException(400, f"{kind} must be a list of user IDs")
            for uid in listed:
                for target in (crew if uid == PRODUCTION else [uid]):
                    if target not in known:
                        raise HTTPException(400, "One of the people on this note is not in the production")
                    placed.setdefault(target, kind)
        if not placed:
            raise HTTPException(400, "Who is this note for? Add someone to To, CC or BCC")
        if len(placed) > RECIPIENTS_MAX:
            raise HTTPException(400, f"A note can go to at most {RECIPIENTS_MAX} people")

        reply_to = body.get("reply_to")
        if reply_to is not None:
            if not isinstance(reply_to, str):
                raise HTTPException(400, "reply_to must be a note ID")
            _check_id(reply_to)
            if await run_in_threadpool(store.get, reply_to, profile["user_id"]) is None:
                raise HTTPException(404, "The note you are replying to is not one you can see")

        files = await _receive_files(uploads, incoming)
        try:
            note_id = await run_in_threadpool(store.create, profile["user_id"], subject, text,
                                              list(placed.items()), chosen_spots, reply_to, files, project)
        except Exception:
            for f in files:
                try:
                    f["tmp"].unlink()
                except OSError:
                    pass
            raise
        logger.info("production notes: %s sent %s to %d people (%d files)", profile["username"], note_id, len(placed), len(files))
        return {"id": note_id, "recipients": len(placed), "spots": chosen_spots, "files": len(files)}

    return router


def _check_id(note_id: str) -> None:
    if not NOTE_ID_RE.fullmatch(note_id):
        raise HTTPException(404, "No such note")


async def _json(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(400, "Send JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(400, "Send a JSON object")
    return body


async def _receive_files(uploads: Iterable[UploadFile], incoming: Path) -> List[Dict[str, Any]]:
    """Copy each upload to disk, enforcing the per-file and per-note limits while reading, not after."""
    out: List[Dict[str, Any]] = []
    total = 0
    try:
        for up in uploads:
            if len(out) >= FILES_MAX:
                raise HTTPException(400, f"At most {FILES_MAX} attachments on one note")
            fid = "f_" + secrets.token_hex(10)
            tmp = incoming / fid
            digest, size = hashlib.sha256(), 0
            with open(tmp, "xb") as fh:
                out.append({"id": fid, "tmp": tmp, "name": _clean_filename(up.filename or ""),
                            "content_type": (up.content_type or "application/octet-stream")[:100], "size": 0, "sha256": ""})
                while True:
                    chunk = await up.read(256 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    total += len(chunk)
                    if size > FILE_BYTES_MAX:
                        raise HTTPException(413, f"{out[-1]['name']} is larger than {FILE_BYTES_MAX // (1024 * 1024)} MB")
                    if total > FILES_TOTAL_MAX:
                        raise HTTPException(413, f"Attachments on one note can total at most {FILES_TOTAL_MAX // (1024 * 1024)} MB")
                    digest.update(chunk)
                    fh.write(chunk)
                fh.flush()
            out[-1]["size"], out[-1]["sha256"] = size, digest.hexdigest()
        return out
    except BaseException:
        for f in out:
            try:
                f["tmp"].unlink()
            except OSError:
                pass
        raise
