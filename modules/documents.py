"""Local document and message storage for the PubCast typewriter workspace."""
from __future__ import annotations

import time
import uuid
import os
import threading
import re
from contextlib import contextmanager
from functools import wraps
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from .persistence import read_json, write_json


SYSTEM_FOLDERS = [
    {"folder_id": "drafts", "name": "Drafts", "kind": "document", "system": True},
    {"folder_id": "scripts", "name": "Scripts", "kind": "document", "system": True},
    {"folder_id": "notes", "name": "Notes", "kind": "document", "system": True},
    {"folder_id": "inbox", "name": "Inbox", "kind": "message", "system": True},
    {"folder_id": "sent", "name": "Sent", "kind": "message", "system": True},
]



# Serialize each owner's entire read/modify/write transaction. Atomic file
# replacement alone cannot prevent lost updates from concurrent requests.
_owner_locks_guard = threading.Lock()
_owner_locks: dict[str, threading.RLock] = {}
_owner_lock_depth = threading.local()


@contextmanager
def _owner_transaction(data_dir: Path, user_id: str):
    state_path = _state_path(data_dir, user_id)
    key = str(state_path.resolve())
    with _owner_locks_guard:
        lock = _owner_locks.setdefault(key, threading.RLock())
    with lock:
        depths = getattr(_owner_lock_depth, "depths", None)
        if depths is None:
            depths = {}
            _owner_lock_depth.depths = depths
        if depths.get(key, 0):
            depths[key] += 1
            try:
                yield
            finally:
                depths[key] -= 1
            return
        state_path.parent.mkdir(parents=True, exist_ok=True)
        # A stable lock file survives atomic replacement of the JSON state.
        with open(str(state_path) + ".lock", "a+b") as handle:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                if not handle.read(1):
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            depths[key] = 1
            try:
                yield
            finally:
                depths.pop(key, None)
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _serialized(fn):
    @wraps(fn)
    def wrapped(data_dir, user_id, *args, **kwargs):
        with _owner_transaction(data_dir, user_id):
            return fn(data_dir, user_id, *args, **kwargs)
    return wrapped


def _now() -> float:
    return time.time()


def _doc_id() -> str:
    return f"doc_{uuid.uuid4().hex[:10]}"


def _msg_id() -> str:
    return f"msg_{uuid.uuid4().hex[:10]}"


def _state_path(data_dir: Path, user_id: str) -> Path:
    # User identities are supplied by the session layer, but storage must not
    # permit them to escape the document directory if an upstream contract
    # changes. Keep existing safe filenames stable for backward compatibility.
    if not isinstance(user_id, str) or not user_id or user_id in {".", ".."} or any(
        ch in user_id for ch in ("/", "\\", "\x00")
    ):
        raise ValueError("invalid document owner identity")
    # Windows forbids these characters in filenames; trailing dots/spaces and
    # reserved device names also alias or invalidate otherwise distinct owners.
    if any(ch in user_id for ch in '<>:"|?*') or any(ord(ch) < 32 for ch in user_id):
        raise ValueError("invalid document owner identity")
    if user_id.rstrip(" .") != user_id or user_id.split(".", 1)[0].upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        raise ValueError("invalid document owner identity")
    return Path(data_dir) / "documents" / f"{user_id}.json"


def _seed_state(user_id: str) -> Dict[str, Any]:
    ts = _now()
    welcome_doc = {
        "doc_id": _doc_id(),
        "title": "Welcome to PubCast",
        "folder_id": "notes",
        "doc_type": "creative",
        "content": (
            "Welcome to your dressing room workspace.\n\n"
            "Use Creative Writing for notes and freeform ideas.\n"
            "Use Script Writing for screenplay-style drafting.\n"
            "Use Email / Messages for production communication."
        ),
        "created_at": ts,
        "updated_at": ts,
        "metadata": {"seed": True},
    }
    script_doc = {
        "doc_id": _doc_id(),
        "title": "Cold Open",
        "folder_id": "scripts",
        "doc_type": "script",
        "content": (
            "INT. PUBCAST STUDIO - NIGHT\n\n"
            "The lights rise on a velvet set.\n\n"
            "HOST\n"
            "Welcome back to the show."
        ),
        "created_at": ts,
        "updated_at": ts,
        "metadata": {"seed": True},
    }
    inbox_message = {
        "message_id": _msg_id(),
        "folder_id": "inbox",
        "subject": "Call Time Confirmed",
        "body": (
            "You are booked for rehearsal in Studio A.\n"
            "Check the green room board for the latest call sheet."
        ),
        "sender": "Production Office",
        "recipients": [user_id],
        "created_at": ts,
        "read": False,
        "transport": "local",
    }
    return {
        "version": 1,
        "folders": deepcopy(SYSTEM_FOLDERS),
        "documents": [welcome_doc, script_doc],
        "messages": [inbox_message],
        "provider": {
            "mode": "local",
            "configured": False,
            "status": "local_only",
            "note": "Local document store is active; no external document provider is configured.",
        },
    }


@_serialized
def load_state(data_dir: Path, user_id: str) -> Dict[str, Any]:
    path = _state_path(data_dir, user_id)
    if not path.exists():
        state = _seed_state(user_id)
        write_json(path, state)
        return state

    state = read_json(path)
    if not isinstance(state, dict) or not state:
        # Existing state must never be silently replaced with welcome data.
        raise ValueError(f"document state is empty or invalid: {path}")

    # Validate persisted collections before touching them. A truncated or
    # structurally damaged state must not be silently 'repaired' into data loss.
    for field in ("folders", "documents", "messages"):
        if field in state and (
            not isinstance(state[field], list)
            or any(not isinstance(item, dict) for item in state[field])
        ):
            raise ValueError(f"invalid document state collection: {field}")
    if "provider" in state and not isinstance(state["provider"], dict):
        raise ValueError("invalid document provider state")
    if "folders" in state and any(
        not isinstance(folder.get("folder_id"), str) for folder in state["folders"]
    ):
        raise ValueError("invalid document folder identity")
    changed = False
    state.setdefault("version", 1)
    state.setdefault("folders", deepcopy(SYSTEM_FOLDERS))
    state.setdefault("documents", [])
    state.setdefault("messages", [])
    state.setdefault(
        "provider",
        {
            "mode": "local",
            "configured": False,
            "status": "local_only",
            "note": "Local document store is active; no external document provider is configured.",
        },
    )

    existing_ids = {folder["folder_id"] for folder in state["folders"]}
    for folder in SYSTEM_FOLDERS:
        if folder["folder_id"] not in existing_ids:
            state["folders"].append(deepcopy(folder))
            changed = True

    if changed:
        write_json(path, state)
    return state


@_serialized
def save_state(data_dir: Path, user_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    path = _state_path(data_dir, user_id)
    write_json(path, state)
    return state


@_serialized
def create_folder(data_dir: Path, user_id: str, name: str, kind: str = "document") -> Dict[str, Any]:
    state = load_state(data_dir, user_id)
    folder = {
        "folder_id": f"fld_{uuid.uuid4().hex[:10]}",
        "name": name.strip() or "Untitled Folder",
        "kind": kind if kind in {"document", "message"} else "document",
        "system": False,
    }
    state["folders"].append(folder)
    save_state(data_dir, user_id, state)
    return folder


@_serialized
def list_documents(data_dir: Path, user_id: str) -> List[Dict[str, Any]]:
    state = load_state(data_dir, user_id)
    docs = state.get("documents", [])
    return sorted(docs, key=lambda item: item.get("updated_at", 0), reverse=True)


@_serialized
def get_document(data_dir: Path, user_id: str, doc_id: str) -> Dict[str, Any]:
    state = load_state(data_dir, user_id)
    for doc in state.get("documents", []):
        if doc.get("doc_id") == doc_id:
            return doc
    raise KeyError(doc_id)


@_serialized
def upsert_document(data_dir: Path, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    state = load_state(data_dir, user_id)
    docs = state["documents"]
    now = _now()
    doc_id = str(payload.get("doc_id") or _doc_id())

    for doc in docs:
        if doc.get("doc_id") == doc_id:
            doc.update(
                {
                    "title": str(payload.get("title") or doc.get("title") or "Untitled"),
                    "folder_id": str(payload.get("folder_id") or doc.get("folder_id") or "drafts"),
                    "doc_type": str(payload.get("doc_type") or doc.get("doc_type") or "creative"),
                    "content": str(payload.get("content") or ""),
                    "updated_at": now,
                    "metadata": {**doc.get("metadata", {}), **dict(payload.get("metadata") or {})},
                }
            )
            save_state(data_dir, user_id, state)
            return doc

    doc = {
        "doc_id": doc_id,
        "title": str(payload.get("title") or "Untitled"),
        "folder_id": str(payload.get("folder_id") or "drafts"),
        "doc_type": str(payload.get("doc_type") or "creative"),
        "content": str(payload.get("content") or ""),
        "created_at": now,
        "updated_at": now,
        "metadata": dict(payload.get("metadata") or {}),
    }
    docs.append(doc)
    save_state(data_dir, user_id, state)
    return doc


@_serialized
def import_document(data_dir: Path, user_id: str, filename: str, content: str) -> Dict[str, Any]:
    title = Path(filename).stem or "Imported Document"
    return upsert_document(
        data_dir,
        user_id,
        {
            "title": title,
            "folder_id": "drafts",
            "doc_type": "creative",
            "content": content,
            "metadata": {"imported_from": filename},
        },
    )


@_serialized
def export_document(data_dir: Path, user_id: str, doc_id: str) -> Dict[str, Any]:
    doc = get_document(data_dir, user_id, doc_id)
    safe_title = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in doc["title"]).strip("_") or "document"
    return {
        "filename": f"{safe_title}.txt",
        "content": doc.get("content", ""),
        "title": doc.get("title", "Untitled"),
    }


@_serialized
def list_messages(data_dir: Path, user_id: str) -> List[Dict[str, Any]]:
    state = load_state(data_dir, user_id)
    msgs = state.get("messages", [])
    return sorted(msgs, key=lambda item: item.get("created_at", 0), reverse=True)


@_serialized
def send_message(data_dir: Path, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    state = load_state(data_dir, user_id)
    now = _now()
    outgoing = {
        "message_id": _msg_id(),
        "folder_id": "sent",
        "subject": str(payload.get("subject") or "(No Subject)"),
        "body": str(payload.get("body") or ""),
        "sender": str(payload.get("sender") or "You"),
        "recipients": list(payload.get("recipients") or ["Production Office"]),
        "created_at": now,
        "read": True,
        "transport": "local",
    }
    ack = {
        "message_id": _msg_id(),
        "folder_id": "inbox",
        "subject": f"Re: {outgoing['subject']}",
        "body": "Message queued in local transport. External delivery provider not configured yet.",
        "sender": "PubCast Mailroom",
        "recipients": [user_id],
        "created_at": now + 0.001,
        "read": False,
        "transport": "local",
    }
    state["messages"].extend([outgoing, ack])
    save_state(data_dir, user_id, state)
    return outgoing

