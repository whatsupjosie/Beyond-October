"""User-owned project work notes for PubPartner.

The work notes are the user's running record of what was decided, worked on,
left open, and discussed in each project. They belong to the user and the
project, never to a character cartridge, so any model the user talks to can be
given the same saved notes.

Design laws
-----------
- The chat itself is saved by the VerbatimVault and the turn log as each
  exchange happens. Work notes never replace it; every detected note points
  back to the exact turn and character span it was quoted from.
- A note's words are never rewritten. Detected notes are exact sentences
  copied from the source; the database refuses any change to a note's text,
  kind, project, origin, or source pointer. A fix is a new note that replaces
  the old one, and the old one stays on record marked as replaced.
- Detected notes start as drafts in one autosave per (project, session). The
  autosave keeps updating while the user works. Save commits drafts for good.
- Drafts that are never saved are kept for AUTOSAVE_RETENTION_SECONDS (one
  week), across at most MAX_AUTOSAVES autosaves; beyond either limit the
  unsaved drafts are deleted. Saved notes are never deleted by the system.
  Nothing is lost when a draft expires because the chat it quoted is kept.
- Only saved notes are given to a model. Drafts are never presented as fact.
- Every change is recorded in a hash-chained audit trail inside the same
  SQLite file and the same transaction as the change.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

SCHEMA_VERSION = "PubPartnerWorkNotes.v1"
AUTOSAVE_RETENTION_SECONDS = 7 * 24 * 60 * 60
MAX_AUTOSAVES = 50
MAX_NOTE_CHARS = 4000
MAX_ID_CHARS = 120
CONTEXT_NOTE_LIMIT = 40
CONTEXT_CHAR_BUDGET = 12000

KINDS: Tuple[str, ...] = ("decided", "worked_on", "open", "discussed")
KIND_LABELS = {
    "decided": "Decided",
    "worked_on": "Worked on",
    "open": "Still open",
    "discussed": "Discussed",
}
STATUSES: Tuple[str, ...] = ("draft", "saved", "replaced", "withdrawn")
ORIGINS: Tuple[str, ...] = ("user_message", "assistant_reply", "user_entry")
_GENESIS = "0" * 64


class WorkNotesError(ValueError):
    """Raised when a work-notes request cannot be honoured as asked."""


class WorkNoteNotFound(WorkNotesError):
    """Raised when a note id does not exist for this user."""


def _now() -> float:
    return time.time()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(text: str) -> str:
    """Comparison key for duplicate detection only; never stored as the note."""
    return re.sub(r"\s+", " ", str(text or "")).strip().rstrip(" .!?").casefold()


def _clean_id(value: Any, field: str, *, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    if not text:
        raise WorkNotesError(f"{field} is required")
    if len(text) > MAX_ID_CHARS:
        raise WorkNotesError(f"{field} must be at most {MAX_ID_CHARS} characters")
    if any(ord(ch) < 32 for ch in text):
        raise WorkNotesError(f"{field} must not contain control characters")
    return text


def _user_file_stem(user_id: str) -> str:
    # The readable part may collide after cleaning ("a.b" vs "a_b"); the hash
    # suffix keeps every user in their own file.
    readable = re.sub(r"[^A-Za-z0-9_-]+", "_", user_id).strip("_")[:60] or "user"
    return f"{readable}-{_sha256(user_id)[:16]}"


# ── Detection ────────────────────────────────────────────────────────────────

_LEAD = r"(?:(?:ok(?:ay)?|so|alright|all\s+right|yeah|yes|right|cool)[,.!]?\s+)?"
_DECIDED_PATTERNS = tuple(re.compile(p, re.I) for p in (
    _LEAD + r"(?:we|i)(?:'ve|’ve|\s+have)?\s+(?:just\s+)?(?:decided|agreed|settled\s+on|chose|chosen|picked)\b",
    _LEAD + r"(?:we(?:'re|’re|\s+are)|i(?:'m|’m|\s+am))\s+going\s+(?:with|to\s+go\s+with)\b",
    _LEAD + r"(?:we(?:'ll|’ll|\s+will)|i(?:'ll|’ll|\s+will))\s+go\s+with\b",
    _LEAD + r"let(?:'s|’s|\s+us)\s+go\s+with\b",
    r"(?:decision|decided|final\s+call)\s*:",
))
_OPEN_PATTERNS = tuple(re.compile(p, re.I) for p in (
    r"(?:todo|to-do|to\s+do|open\s+question|still\s+open|unresolved)\s*:",
    _LEAD + r"(?:we|i)\s+still\s+(?:need|have|want)\s+to\b",
    _LEAD + r"(?:we|i)\s+(?:haven't|haven’t|have\s+not)\s+(?:decided|figured\s+out|settled|worked\s+out)\b",
    _LEAD + r"still\s+need\s+to\b",
    _LEAD + r"(?:we|i)\s+need\s+to\s+(?:figure\s+out|decide|work\s+out)\b",
))
_FILE_EXTENSIONS = (
    "py|pyw|js|mjs|cjs|ts|tsx|jsx|json|jsonl|md|txt|html|htm|css|scss|ps1|psm1|psd1|bat|cmd|sh|"
    "yaml|yml|toml|ini|cfg|sql|sqlite|sqlite3|db|cs|cpp|cc|c|h|hpp|java|kt|go|rs|rb|php|swift|"
    "lua|glsl|hlsl|wgsl|shader|blend|fbx|glb|gltf|obj|png|jpg|jpeg|webp|svg|wav|mp3|ogg|flac|"
    "mp4|docx|doc|pdf|xlsx|csv|pptx|zip|pubpartner|cartridge"
)
_FILE_RE = re.compile(
    r"(?<![\w./\\:-])(?:[\w.-]+[/\\])*[\w-][\w.-]*\.(?:" + _FILE_EXTENSIONS + r")(?![\w-])",
    re.I,
)
_VERSION_RE = re.compile(
    r"(?<![\w.])v\d+(?:\.\d+)*(?![\w.])|(?<![\w.])\d+\.\d+\.\d+(?![\w.])|\bversion\s+\d+(?:\.\d+)*\b",
    re.I,
)
_URL_RE = re.compile(r"\b(?:https?|ftp)://\S+|\bwww\.\S+", re.I)
_FENCE_RE = re.compile(r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)", re.S)
_QUOTE_RE = re.compile(r'"[^"\n]*(?:"|$)|“[^”]*(?:”|$)|‘[^’]*(?:’|$)', re.M)
_SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)|\n")


def _protected_ranges(text: str) -> List[Tuple[int, int]]:
    ranges = [m.span() for m in _FENCE_RE.finditer(text)]
    ranges += [m.span() for m in _QUOTE_RE.finditer(text)]
    return ranges


def _sentence_spans(text: str) -> Iterator[Tuple[int, int]]:
    """Yield exact (start, end) spans of sentences; text[start:end] is untouched."""
    start = 0
    for match in _SENTENCE_END.finditer(text):
        end = match.end() if match.group() != "\n" else match.start()
        yield from _trimmed(text, start, end)
        start = match.end()
    yield from _trimmed(text, start, len(text))


def _trimmed(text: str, start: int, end: int) -> Iterator[Tuple[int, int]]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if end > start:
        yield start, end


def _references(sentence: str) -> List[str]:
    scrubbed = _URL_RE.sub(lambda m: " " * len(m.group()), sentence)
    found = [m.group() for m in _FILE_RE.finditer(scrubbed)]
    found += [m.group() for m in _VERSION_RE.finditer(scrubbed)]
    return found


def detect_notes(text: str, *, origin: str) -> List[Dict[str, Any]]:
    """Find candidate notes as exact sentences of ``text``.

    Decisions and open items are taken only from the user's own words. File
    and version mentions are taken from either side. Quoted speech and fenced
    blocks are never treated as notes. Each candidate carries the exact span,
    so ``text[span_start:span_end] == candidate["text"]`` always holds.
    """
    if origin not in {"user_message", "assistant_reply"}:
        raise WorkNotesError("detection origin must be user_message or assistant_reply")
    value = str(text or "")
    protected = _protected_ranges(value)
    seen_refs: set[str] = set()
    found: List[Dict[str, Any]] = []
    for start, end in _sentence_spans(value):
        if any(lo <= start < hi for lo, hi in protected):
            continue
        sentence = value[start:end]
        if sentence[:1] in {">", '"', "“", "‘", "'"}:
            continue
        if end - start > MAX_NOTE_CHARS:
            continue
        kind = ""
        if origin == "user_message":
            if any(p.match(sentence) for p in _DECIDED_PATTERNS):
                kind = "decided"
            elif any(p.match(sentence) for p in _OPEN_PATTERNS):
                kind = "open"
        refs = _references(sentence)
        if not kind and refs:
            new_refs = {r.casefold() for r in refs} - seen_refs
            if not new_refs:
                continue
            kind = "worked_on"
        if not kind:
            continue
        seen_refs.update(r.casefold() for r in refs)
        found.append({
            "kind": kind,
            "text": sentence,
            "span_start": start,
            "span_end": end,
            "references": refs,
        })
    return found


# ── Store ────────────────────────────────────────────────────────────────────

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS autosaves (
        autosave_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        UNIQUE(project_id, session_id)
    )""",
    f"""CREATE TABLE IF NOT EXISTS notes (
        note_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ({','.join(repr(k) for k in KINDS)})),
        text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND {MAX_NOTE_CHARS}),
        text_sha256 TEXT NOT NULL,
        normalized TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ({','.join(repr(s) for s in STATUSES)})),
        origin TEXT NOT NULL CHECK (origin IN ({','.join(repr(o) for o in ORIGINS)})),
        autosave_id TEXT,
        session_id TEXT,
        turn_id TEXT,
        source_id TEXT,
        source_sha256 TEXT,
        span_start INTEGER,
        span_end INTEGER,
        replaces TEXT,
        replaced_by TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        saved_at REAL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_notes_project_status ON notes(project_id, status, kind)",
    "CREATE INDEX IF NOT EXISTS idx_notes_autosave ON notes(autosave_id, status)",
    """CREATE TABLE IF NOT EXISTS audit (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        at REAL NOT NULL,
        action TEXT NOT NULL,
        note_id TEXT,
        detail TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        hash TEXT NOT NULL
    )""",
    # A note's words and provenance can never change after it is written.
    """CREATE TRIGGER IF NOT EXISTS notes_words_are_immutable
        BEFORE UPDATE OF note_id, project_id, kind, text, text_sha256, normalized, origin,
                         session_id, turn_id, source_id, source_sha256, span_start, span_end,
                         replaces, created_at ON notes
        BEGIN SELECT RAISE(ABORT, 'work note words and provenance are immutable'); END""",
    # Only unsaved drafts may ever be deleted.
    """CREATE TRIGGER IF NOT EXISTS notes_only_drafts_are_deleted
        BEFORE DELETE ON notes WHEN old.status <> 'draft'
        BEGIN SELECT RAISE(ABORT, 'only unsaved drafts can be deleted'); END""",
    # A saved, replaced, or withdrawn note never goes back to being a draft.
    """CREATE TRIGGER IF NOT EXISTS notes_saved_never_revert
        BEFORE UPDATE OF status ON notes WHEN old.status <> 'draft' AND new.status = 'draft'
        BEGIN SELECT RAISE(ABORT, 'a saved note cannot become a draft again'); END""",
    """CREATE TRIGGER IF NOT EXISTS audit_is_append_only_update
        BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS audit_is_append_only_delete
        BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END""",
)

_NOTE_FIELDS = (
    "note_id", "project_id", "kind", "text", "text_sha256", "status", "origin",
    "autosave_id", "session_id", "turn_id", "source_id", "source_sha256",
    "span_start", "span_end", "replaces", "replaced_by", "created_at",
    "updated_at", "saved_at",
)


class WorkNotesStore:
    """One SQLite file per user under ``<data_dir>/pubpartner/work_notes``."""

    def __init__(
        self,
        data_dir: Path | str,
        *,
        retention_seconds: int = AUTOSAVE_RETENTION_SECONDS,
        max_autosaves: int = MAX_AUTOSAVES,
        clock: Any = None,
    ) -> None:
        if int(retention_seconds) <= 0 or int(max_autosaves) <= 0:
            raise WorkNotesError("retention_seconds and max_autosaves must be positive")
        self.root = Path(data_dir) / "pubpartner" / "work_notes"
        self.retention_seconds = int(retention_seconds)
        self.max_autosaves = int(max_autosaves)
        self._clock = clock or _now
        self._locks: Dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()
        self._ready: set[str] = set()

    # ── connection plumbing ──────────────────────────────────────────────
    def path_for(self, user_id: str) -> Path:
        user = _clean_id(user_id, "user_id")
        return self.root / f"{_user_file_stem(user)}.sqlite3"

    def _lock(self, path: Path) -> threading.RLock:
        key = str(path)
        with self._locks_guard:
            return self._locks.setdefault(key, threading.RLock())

    def _connect(self, path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(str(path), timeout=15.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    def _ensure(self, connection: sqlite3.Connection, path: Path, user_id: str) -> None:
        if str(path) in self._ready:
            return
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in _SCHEMA:
                connection.execute(statement)
            rows = dict(connection.execute("SELECT key, value FROM meta").fetchall())
            if not rows:
                connection.executemany(
                    "INSERT INTO meta(key, value) VALUES (?, ?)",
                    [("schema_version", SCHEMA_VERSION), ("user_id", user_id),
                     ("created_at", repr(self._clock()))],
                )
            else:
                if rows.get("schema_version") != SCHEMA_VERSION:
                    raise WorkNotesError(
                        f"unsupported work notes schema {rows.get('schema_version')!r} in {path.name}")
                if rows.get("user_id") != user_id:
                    raise WorkNotesError("work notes file belongs to a different user")
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        self._ready.add(str(path))

    @contextmanager
    def _transaction(self, user_id: str) -> Iterator[sqlite3.Connection]:
        user = _clean_id(user_id, "user_id")
        path = self.path_for(user)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock(path):
            with closing(self._connect(path)) as connection:
                self._ensure(connection, path, user)
                connection.execute("BEGIN IMMEDIATE")
                try:
                    yield connection
                    connection.execute("COMMIT")
                except BaseException:
                    connection.execute("ROLLBACK")
                    raise

    @contextmanager
    def _reader(self, user_id: str) -> Iterator[Optional[sqlite3.Connection]]:
        user = _clean_id(user_id, "user_id")
        path = self.path_for(user)
        if not path.exists():
            yield None
            return
        with self._lock(path):
            with closing(self._connect(path)) as connection:
                self._ensure(connection, path, user)
                yield connection

    # ── audit chain ──────────────────────────────────────────────────────
    @staticmethod
    def _audit_hash(prev_hash: str, at: float, action: str, note_id: str, detail: str) -> str:
        payload = json.dumps([prev_hash, repr(at), action, note_id, detail],
                             ensure_ascii=False, separators=(",", ":"))
        return _sha256(payload)

    def _audit(self, connection: sqlite3.Connection, action: str, note_id: str,
               detail: Dict[str, Any]) -> None:
        row = connection.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = row["hash"] if row else _GENESIS
        at = self._clock()
        body = json.dumps(detail, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        connection.execute(
            "INSERT INTO audit(at, action, note_id, detail, prev_hash, hash) VALUES (?,?,?,?,?,?)",
            (at, action, note_id or "", body, prev_hash,
             self._audit_hash(prev_hash, at, action, note_id or "", body)),
        )

    def verify(self, *, user_id: str) -> Dict[str, Any]:
        """Walk the audit chain and check every saved note's text hash."""
        with self._reader(user_id) as connection:
            if connection is None:
                return {"ok": True, "entries": 0, "notes_checked": 0, "problems": []}
            problems: List[str] = []
            prev_hash = _GENESIS
            entries = 0
            for row in connection.execute("SELECT * FROM audit ORDER BY seq"):
                entries += 1
                expected = self._audit_hash(prev_hash, row["at"], row["action"], row["note_id"], row["detail"])
                if row["prev_hash"] != prev_hash or row["hash"] != expected:
                    problems.append(f"audit entry {row['seq']} does not match the chain")
                prev_hash = row["hash"]
            checked = 0
            for row in connection.execute("SELECT note_id, text, text_sha256 FROM notes"):
                checked += 1
                if _sha256(row["text"]) != row["text_sha256"]:
                    problems.append(f"note {row['note_id']} text does not match its hash")
            return {"ok": not problems, "entries": entries, "notes_checked": checked, "problems": problems}

    # ── helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def _row(row: sqlite3.Row) -> Dict[str, Any]:
        return {name: row[name] for name in _NOTE_FIELDS}

    def _note(self, connection: sqlite3.Connection, note_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM notes WHERE note_id = ?", (note_id,)).fetchone()
        if row is None:
            raise WorkNoteNotFound(f"work note {note_id} not found")
        return row

    def _autosave_id(self, connection: sqlite3.Connection, project_id: str, session_id: str) -> str:
        now = self._clock()
        row = connection.execute(
            "SELECT autosave_id FROM autosaves WHERE project_id = ? AND session_id = ?",
            (project_id, session_id),
        ).fetchone()
        if row is not None:
            connection.execute("UPDATE autosaves SET updated_at = ? WHERE autosave_id = ?",
                               (now, row["autosave_id"]))
            return str(row["autosave_id"])
        autosave_id = "autosave_" + uuid.uuid4().hex
        connection.execute(
            "INSERT INTO autosaves(autosave_id, project_id, session_id, created_at, updated_at) VALUES (?,?,?,?,?)",
            (autosave_id, project_id, session_id, now, now),
        )
        return autosave_id

    @staticmethod
    def _duplicate(connection: sqlite3.Connection, project_id: str, kind: str, normalized: str) -> Optional[str]:
        row = connection.execute(
            "SELECT note_id FROM notes WHERE project_id = ? AND kind = ? AND normalized = ? "
            "AND status IN ('draft', 'saved') LIMIT 1",
            (project_id, kind, normalized),
        ).fetchone()
        return str(row["note_id"]) if row else None

    def _insert(self, connection: sqlite3.Connection, *, project_id: str, kind: str, text: str,
                status: str, origin: str, autosave_id: Optional[str], session_id: Optional[str],
                turn_id: Optional[str], source_id: Optional[str], source_sha256: Optional[str],
                span_start: Optional[int], span_end: Optional[int], replaces: Optional[str]) -> Dict[str, Any]:
        now = self._clock()
        note_id = "note_" + uuid.uuid4().hex
        connection.execute(
            "INSERT INTO notes(note_id, project_id, kind, text, text_sha256, normalized, status, origin, "
            "autosave_id, session_id, turn_id, source_id, source_sha256, span_start, span_end, replaces, "
            "replaced_by, created_at, updated_at, saved_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (note_id, project_id, kind, text, _sha256(text), _normalize(text), status, origin,
             autosave_id, session_id, turn_id, source_id, source_sha256, span_start, span_end, replaces,
             None, now, now, now if status == "saved" else None),
        )
        self._audit(connection, "add", note_id, {
            "project_id": project_id, "kind": kind, "status": status, "origin": origin,
            "text_sha256": _sha256(text), "turn_id": turn_id, "source_id": source_id,
            "span": [span_start, span_end], "replaces": replaces,
        })
        return self._row(self._note(connection, note_id))

    @staticmethod
    def _validate_text(text: Any) -> str:
        if not isinstance(text, str) or not text.strip():
            raise WorkNotesError("note text is required")
        if len(text) > MAX_NOTE_CHARS:
            raise WorkNotesError(f"note text must be at most {MAX_NOTE_CHARS} characters")
        try:
            text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise WorkNotesError("note text contains invalid Unicode") from exc
        return text

    @staticmethod
    def _validate_kind(kind: Any) -> str:
        value = str(kind or "").strip()
        if value not in KINDS:
            raise WorkNotesError(f"kind must be one of {', '.join(KINDS)}")
        return value

    # ── expiry ───────────────────────────────────────────────────────────
    def _expire(self, connection: sqlite3.Connection) -> int:
        """Delete unsaved drafts past the retention window or the autosave limit."""
        cutoff = self._clock() - self.retention_seconds
        holders = connection.execute(
            "SELECT a.autosave_id, a.updated_at FROM autosaves a "
            "WHERE EXISTS (SELECT 1 FROM notes n WHERE n.autosave_id = a.autosave_id AND n.status = 'draft') "
            "ORDER BY a.updated_at DESC, a.autosave_id DESC"
        ).fetchall()
        expired = [row["autosave_id"] for index, row in enumerate(holders)
                   if index >= self.max_autosaves or row["updated_at"] < cutoff]
        removed = 0
        for autosave_id in expired:
            drafts = connection.execute(
                "SELECT note_id, text_sha256, updated_at FROM notes WHERE autosave_id = ? AND status = 'draft'",
                (autosave_id,),
            ).fetchall()
            for draft in drafts:
                self._audit(connection, "expire", draft["note_id"], {
                    "autosave_id": autosave_id, "text_sha256": draft["text_sha256"],
                    "reason": "older than retention" if draft["updated_at"] < cutoff else "over autosave limit",
                })
            connection.execute("DELETE FROM notes WHERE autosave_id = ? AND status = 'draft'", (autosave_id,))
            removed += len(drafts)
            still_used = connection.execute(
                "SELECT 1 FROM notes WHERE autosave_id = ? LIMIT 1", (autosave_id,)).fetchone()
            if still_used is None:
                connection.execute("DELETE FROM autosaves WHERE autosave_id = ?", (autosave_id,))
        return removed

    def expire(self, *, user_id: str) -> Dict[str, Any]:
        with self._transaction(user_id) as connection:
            return {"ok": True, "expired_drafts": self._expire(connection)}

    # ── recording ────────────────────────────────────────────────────────
    def record_turn(
        self,
        *,
        user_id: str,
        project_id: str,
        session_id: str,
        turn_id: str,
        user_text: str,
        source_id: str,
        source_sha256: str,
        reply_text: str = "",
        detect_user: bool = True,
        detect_reply: bool = True,
    ) -> Dict[str, Any]:
        """Add draft notes detected in one exchange to the session's autosave."""
        project = _clean_id(project_id, "project_id")
        session = _clean_id(session_id, "session_id")
        turn = _clean_id(turn_id, "turn_id")
        candidates: List[Tuple[str, Dict[str, Any], str, str]] = []
        if detect_user and user_text:
            for item in detect_notes(user_text, origin="user_message"):
                candidates.append(("user_message", item, source_id, source_sha256))
        if detect_reply and reply_text:
            reply_hash = _sha256(reply_text)
            for item in detect_notes(reply_text, origin="assistant_reply"):
                candidates.append(("assistant_reply", item, "", reply_hash))
        with self._transaction(user_id) as connection:
            expired = self._expire(connection)
            added: List[Dict[str, Any]] = []
            skipped = 0
            autosave_id = ""
            for origin, item, item_source, item_hash in candidates:
                if self._duplicate(connection, project, item["kind"], _normalize(item["text"])):
                    skipped += 1
                    continue
                if not autosave_id:
                    autosave_id = self._autosave_id(connection, project, session)
                added.append(self._insert(
                    connection, project_id=project, kind=item["kind"], text=item["text"],
                    status="draft", origin=origin, autosave_id=autosave_id, session_id=session,
                    turn_id=turn, source_id=item_source or None, source_sha256=item_hash or None,
                    span_start=item["span_start"], span_end=item["span_end"], replaces=None,
                ))
            counts = self._draft_counts(connection, project, session)
        return {"ok": True, "added": added, "duplicates_skipped": skipped,
                "expired_drafts": expired, "autosave_id": autosave_id or None, **counts}

    def add_note(
        self,
        *,
        user_id: str,
        project_id: str,
        kind: str,
        text: str,
        session_id: str = "",
        save: bool = False,
    ) -> Dict[str, Any]:
        """Add a note the user wrote themselves, exactly as written."""
        project = _clean_id(project_id, "project_id")
        value = self._validate_text(text)
        note_kind = self._validate_kind(kind)
        session = _clean_id(session_id, "session_id") if session_id else ""
        if not save and not session:
            raise WorkNotesError("an unsaved note needs a session_id for its autosave")
        with self._transaction(user_id) as connection:
            self._expire(connection)
            duplicate = self._duplicate(connection, project, note_kind, _normalize(value))
            if duplicate:
                existing = self._row(self._note(connection, duplicate))
                return {"ok": True, "note": existing, "duplicate": True}
            autosave_id = None if save else self._autosave_id(connection, project, session)
            note = self._insert(
                connection, project_id=project, kind=note_kind, text=value,
                status="saved" if save else "draft", origin="user_entry", autosave_id=autosave_id,
                session_id=session or None, turn_id=None, source_id=None, source_sha256=None,
                span_start=None, span_end=None, replaces=None,
            )
        return {"ok": True, "note": note, "duplicate": False}

    # ── review actions ───────────────────────────────────────────────────
    def save(
        self,
        *,
        user_id: str,
        project_id: str,
        session_id: str = "",
        note_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Commit drafts for good: chosen ids, one session's autosave, or the whole project."""
        project = _clean_id(project_id, "project_id")
        with self._transaction(user_id) as connection:
            self._expire(connection)
            if note_ids:
                ids = [_clean_id(n, "note_id") for n in note_ids]
                rows = []
                for note_id in ids:
                    row = self._note(connection, note_id)
                    if row["project_id"] != project:
                        raise WorkNotesError(f"note {note_id} belongs to another project")
                    if row["status"] != "draft":
                        raise WorkNotesError(f"note {note_id} is not an unsaved draft")
                    rows.append(row)
            elif session_id:
                session = _clean_id(session_id, "session_id")
                rows = connection.execute(
                    "SELECT * FROM notes WHERE project_id = ? AND session_id = ? AND status = 'draft' "
                    "ORDER BY created_at", (project, session)).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM notes WHERE project_id = ? AND status = 'draft' ORDER BY created_at",
                    (project,)).fetchall()
            now = self._clock()
            saved = []
            for row in rows:
                connection.execute(
                    "UPDATE notes SET status = 'saved', saved_at = ?, updated_at = ? WHERE note_id = ?",
                    (now, now, row["note_id"]))
                self._audit(connection, "save", row["note_id"], {"text_sha256": row["text_sha256"]})
                saved.append(self._row(self._note(connection, row["note_id"])))
        return {"ok": True, "saved": saved, "count": len(saved)}

    def drop(self, *, user_id: str, note_id: str) -> Dict[str, Any]:
        """Delete one unsaved draft at the user's request."""
        with self._transaction(user_id) as connection:
            row = self._note(connection, _clean_id(note_id, "note_id"))
            if row["status"] != "draft":
                raise WorkNotesError("only an unsaved draft can be dropped; withdraw a saved note instead")
            self._audit(connection, "drop", row["note_id"], {"text_sha256": row["text_sha256"]})
            connection.execute("DELETE FROM notes WHERE note_id = ?", (row["note_id"],))
        return {"ok": True, "dropped": row["note_id"]}

    def withdraw(self, *, user_id: str, note_id: str) -> Dict[str, Any]:
        """Stop using a saved note. It stays on record and is never deleted."""
        with self._transaction(user_id) as connection:
            row = self._note(connection, _clean_id(note_id, "note_id"))
            if row["status"] != "saved":
                raise WorkNotesError("only a saved note can be withdrawn")
            now = self._clock()
            connection.execute("UPDATE notes SET status = 'withdrawn', updated_at = ? WHERE note_id = ?",
                               (now, row["note_id"]))
            self._audit(connection, "withdraw", row["note_id"], {"text_sha256": row["text_sha256"]})
            note = self._row(self._note(connection, row["note_id"]))
        return {"ok": True, "note": note}

    def replace(
        self,
        *,
        user_id: str,
        note_id: str,
        text: str,
        kind: str = "",
    ) -> Dict[str, Any]:
        """Correct a note by adding a new one. The old words are never edited.

        Replacing a saved note keeps the old note on record, marked replaced,
        and saves the user's new wording. Replacing an unsaved draft drops the
        draft and leaves the new wording as a draft in the same autosave.
        """
        value = self._validate_text(text)
        with self._transaction(user_id) as connection:
            old = self._note(connection, _clean_id(note_id, "note_id"))
            if old["status"] not in {"draft", "saved"}:
                raise WorkNotesError("this note was already replaced or withdrawn")
            new_kind = self._validate_kind(kind) if kind else str(old["kind"])
            was_saved = old["status"] == "saved"
            if was_saved:
                # The old note leaves the duplicate check before the new one is added.
                connection.execute("UPDATE notes SET status = 'replaced', updated_at = ? WHERE note_id = ?",
                                   (self._clock(), old["note_id"]))
            else:
                self._audit(connection, "drop", old["note_id"],
                            {"text_sha256": old["text_sha256"], "reason": "replaced by user"})
                connection.execute("DELETE FROM notes WHERE note_id = ?", (old["note_id"],))
            autosave_id = None
            if not was_saved:
                autosave_id = self._autosave_id(connection, str(old["project_id"]), str(old["session_id"]))
            new = self._insert(
                connection, project_id=str(old["project_id"]), kind=new_kind, text=value,
                status="saved" if was_saved else "draft", origin="user_entry",
                autosave_id=autosave_id, session_id=old["session_id"], turn_id=None,
                source_id=None, source_sha256=None, span_start=None, span_end=None,
                replaces=old["note_id"] if was_saved else None,
            )
            if was_saved:
                connection.execute("UPDATE notes SET replaced_by = ? WHERE note_id = ?",
                                   (new["note_id"], old["note_id"]))
                self._audit(connection, "replace", old["note_id"],
                            {"text_sha256": old["text_sha256"], "replaced_by": new["note_id"]})
                replaced = self._row(self._note(connection, old["note_id"]))
            else:
                replaced = {**self._row(old), "status": "dropped"}
        return {"ok": True, "note": new, "replaced": replaced}

    # ── reading ──────────────────────────────────────────────────────────
    def _draft_counts(self, connection: sqlite3.Connection, project_id: str, session_id: str) -> Dict[str, int]:
        here = connection.execute(
            "SELECT COUNT(*) FROM notes WHERE project_id = ? AND session_id = ? AND status = 'draft'",
            (project_id, session_id)).fetchone()[0]
        total = connection.execute(
            "SELECT COUNT(*) FROM notes WHERE project_id = ? AND status = 'draft'", (project_id,)).fetchone()[0]
        return {"drafts_this_session": int(here), "drafts_from_earlier_sessions": int(total - here)}

    def list_notes(
        self,
        *,
        user_id: str,
        project_id: str,
        status: str = "saved",
        session_id: str = "",
        limit: int = 500,
    ) -> Dict[str, Any]:
        project = _clean_id(project_id, "project_id")
        statuses = list(STATUSES) if status == "all" else [status]
        if any(s not in STATUSES for s in statuses):
            raise WorkNotesError(f"status must be all or one of {', '.join(STATUSES)}")
        bounded = max(1, min(5000, int(limit)))
        with self._reader(user_id) as connection:
            if connection is None:
                return {"ok": True, "project_id": project, "notes": [], "count": 0}
            marks = ",".join("?" for _ in statuses)
            query = f"SELECT * FROM notes WHERE project_id = ? AND status IN ({marks})"
            args: List[Any] = [project, *statuses]
            if session_id:
                query += " AND session_id = ?"
                args.append(_clean_id(session_id, "session_id"))
            query += " ORDER BY created_at, note_id LIMIT ?"
            args.append(bounded)
            rows = [self._row(row) for row in connection.execute(query, args)]
        return {"ok": True, "project_id": project, "notes": rows, "count": len(rows)}

    def drafts(self, *, user_id: str, project_id: str, session_id: str = "") -> Dict[str, Any]:
        """Unsaved drafts, split into this session's and earlier sessions' autosaves."""
        project = _clean_id(project_id, "project_id")
        session = _clean_id(session_id, "session_id") if session_id else ""
        with self._transaction(user_id) as connection:
            expired = self._expire(connection)
            rows = connection.execute(
                "SELECT n.*, a.updated_at AS autosave_updated_at FROM notes n "
                "LEFT JOIN autosaves a ON a.autosave_id = n.autosave_id "
                "WHERE n.project_id = ? AND n.status = 'draft' ORDER BY n.created_at, n.note_id",
                (project,)).fetchall()
        groups: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = str(row["autosave_id"] or "")
            group = groups.setdefault(key, {
                "autosave_id": key or None,
                "session_id": row["session_id"],
                "updated_at": row["autosave_updated_at"],
                "expires_at": (row["autosave_updated_at"] or row["updated_at"]) + self.retention_seconds,
                "notes": [],
            })
            group["notes"].append(self._row(row))
        this_session = [g for g in groups.values() if session and g["session_id"] == session]
        earlier = sorted((g for g in groups.values() if not session or g["session_id"] != session),
                         key=lambda g: g["updated_at"] or 0, reverse=True)
        return {
            "ok": True,
            "project_id": project,
            "this_session": this_session[0] if this_session else None,
            "earlier_sessions": earlier,
            "expired_drafts": expired,
            "retention_days": self.retention_seconds / 86400,
            "max_autosaves": self.max_autosaves,
        }

    def context_for_model(
        self,
        *,
        user_id: str,
        project_id: str,
        limit: int = CONTEXT_NOTE_LIMIT,
        char_budget: int = CONTEXT_CHAR_BUDGET,
    ) -> Dict[str, Any]:
        """Saved notes only, whole and unclipped, newest first within the budget.

        A note either fits whole or is left out and counted; a model is never
        shown part of the user's sentence.
        """
        project = _clean_id(project_id, "project_id")
        with self._reader(user_id) as connection:
            if connection is None:
                return {"notes": [], "saved_total": 0, "not_shown": 0}
            rows = connection.execute(
                "SELECT * FROM notes WHERE project_id = ? AND status = 'saved' "
                "ORDER BY saved_at DESC, created_at DESC, note_id DESC", (project,)).fetchall()
        chosen: List[Dict[str, Any]] = []
        used = 0
        for row in rows:
            if len(chosen) >= limit:
                break
            size = len(row["text"])
            if used + size > char_budget:
                continue
            used += size
            chosen.append({
                "id": row["note_id"],
                "kind": row["kind"],
                "text": row["text"],
                "from": {"user_message": "user", "assistant_reply": "assistant",
                         "user_entry": "user"}[row["origin"]],
                "saved_at": row["saved_at"],
            })
        return {"notes": chosen, "saved_total": len(rows), "not_shown": len(rows) - len(chosen)}

    def export_text(self, *, user_id: str, project_id: str, include_drafts: bool = False) -> str:
        """Plain-text page of the project's notes, grouped by kind, oldest first."""
        project = _clean_id(project_id, "project_id")
        saved = self.list_notes(user_id=user_id, project_id=project, status="saved", limit=5000)["notes"]
        drafts = (self.list_notes(user_id=user_id, project_id=project, status="draft", limit=5000)["notes"]
                  if include_drafts else [])
        lines = [f"Project notes: {project}", ""]
        if not saved and not drafts:
            lines.append("No saved notes yet.")
        for kind in ("decided", "worked_on", "open", "discussed"):
            rows = [r for r in saved if r["kind"] == kind]
            if not rows:
                continue
            lines.append(KIND_LABELS[kind])
            for row in rows:
                when = time.strftime("%Y-%m-%d", time.localtime(row["saved_at"] or row["created_at"]))
                who = " (said by the model)" if row["origin"] == "assistant_reply" else ""
                lines.append(f"- {row['text']}  [{when}]{who}")
            lines.append("")
        if drafts:
            lines.append("Unsaved drafts")
            for row in drafts:
                lines.append(f"- {KIND_LABELS[row['kind']]}: {row['text']}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def note(self, *, user_id: str, note_id: str) -> Dict[str, Any]:
        with self._reader(user_id) as connection:
            if connection is None:
                raise WorkNoteNotFound(f"work note {note_id} not found")
            return self._row(self._note(connection, _clean_id(note_id, "note_id")))


__all__ = [
    "AUTOSAVE_RETENTION_SECONDS",
    "CONTEXT_CHAR_BUDGET",
    "CONTEXT_NOTE_LIMIT",
    "KINDS",
    "MAX_AUTOSAVES",
    "WorkNoteNotFound",
    "WorkNotesError",
    "WorkNotesStore",
    "detect_notes",
]
