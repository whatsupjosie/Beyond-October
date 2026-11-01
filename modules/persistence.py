# PubCast AI — persistence.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""
modules/persistence.py — PubCast I/O helpers
=============================================
Sync and async JSON persistence, filename sanitisation, upload validation.
All async functions use aiofiles; the dependency is declared in requirements.txt.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# aiofiles is a runtime dependency.  Import lazily so unit tests that stub
# the filesystem can patch at module level without triggering the import.
try:
    import aiofiles
    _AIOFILES = True
except ImportError:  # pragma: no cover
    _AIOFILES = False

ALLOWED_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webm", ".mp4",
    ".pdf", ".txt", ".md", ".csv", ".ppt", ".pptx",
    ".wav", ".mov", ".zip",
}


# ── Directory setup ───────────────────────────────────────────────────────────

def ensure_dirs(data_dir: Path, assets_dir: Path) -> None:
    """Create standard PubCast data and asset directories."""
    for sub in ("users", "logs", "global", "avatars", "bots", "recordings",
                "exports", "imports", "projects", "security"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)
    for sub in ("vod", "uploads", "models", "textures"):
        (assets_dir / sub).mkdir(parents=True, exist_ok=True)


# ── Sync JSON helpers ─────────────────────────────────────────────────────────

def read_json(path: Path) -> Dict[str, Any]:
    """Read a JSON file; return {} if the file does not exist."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fsync_directory(directory: Path) -> None:
    """Best-effort directory sync after atomic replacement (POSIX only)."""
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except (AttributeError, OSError):
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    """Durably and atomically write *data* to *path*.

    A unique sibling temp file prevents concurrent writers from clobbering one
    another. The file is flushed and synced before ``os.replace``; the parent
    directory is synced where supported. The previous file remains intact if
    serialization or writing fails.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    """Append one JSON object as a line to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# ── Async JSON helpers ────────────────────────────────────────────────────────

async def read_json_async(path: Path) -> Dict[str, Any]:
    """Async equivalent of read_json.  Falls back to sync if aiofiles is absent."""
    if not path.exists():
        return {}
    if _AIOFILES:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            raw = await f.read()
        return json.loads(raw)
    # Fallback (should not happen in production but keeps tests simple)
    return read_json(path)


async def write_json_async(path: Path, data: Dict[str, Any]) -> None:
    """Async wrapper around the same durable atomic write implementation."""
    await asyncio.to_thread(write_json, path, data)


# ── Filename helpers ──────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """Strip path traversal components and dangerous characters."""
    name = name.strip().replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name or "_"


def storage_key(value: Any, *, maximum: int = 120) -> str:
    """Map an external identifier to one collision-resistant filename stem.

    Already-safe identifiers remain unchanged for backward compatibility.
    Unsafe identifiers receive a readable prefix plus a digest so values such
    as ``"a/b"`` and ``"a\\b"`` cannot collapse onto another user's file.
    """
    maximum = int(maximum)
    if maximum < 24:
        raise ValueError("storage key maximum must be at least 24 characters")
    raw = str(value or "").strip()
    if (
        len(raw) <= maximum
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", raw)
        and raw not in {".", ".."}
    ):
        return raw
    prefix = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-") or "identity"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    prefix_limit = max(1, maximum - len(digest) - 2)
    return f"{prefix[:prefix_limit]}--{digest}"




def unique_child_path(directory: Path, name: str) -> Path:
    """Return a non-clobbering child path inside *directory* for *name*."""
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / sanitize_filename(name)
    stem = candidate.stem or "upload"
    suffix = candidate.suffix
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate

def allowed_upload_extension(name: str) -> bool:
    """Return True if the file extension is on the allowlist."""
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    return ext in ALLOWED_EXTS


def build_autosave_filename(
    prefix: str,
    suffix: str,
    *,
    when: float | None = None,
) -> str:
    """
    Build a timestamped autosave filename.

    Example::

        build_autosave_filename("autosave", ".json")
        # → "autosave_20260216T045201Z.json"

        build_autosave_filename("autosave", ".json", when=1765701240.0)
        # → "autosave_20251214T083400Z.json"
    """
    ts = when if when is not None else time.time()
    stamp = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}{suffix}"
