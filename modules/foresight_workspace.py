"""Portable local workspace files: ordinary disk files, no browser-vendor API.

Paths are relative to the authenticated user's PubCast workspace. Atomic writes
and content-hash revisions prevent silent replacement of concurrent edits.
"""

from __future__ import annotations
import base64
import binascii
import hashlib
import os
from pathlib import Path, PurePosixPath
import tempfile
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .route_security import current_identity

MAX_FILE = 32 * 1024 * 1024


class SaveFile(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    data: str = Field(max_length=MAX_FILE * 4 // 3 + 8)
    expected_revision: str | None = None


class CheckPython(BaseModel):
    text: str = Field(max_length=5 * 1024 * 1024)
    name: str = Field(default="script.py", max_length=255)


def create_workspace_router(data_dir):
    router = APIRouter(prefix="/api/foresight/workspace", tags=["Local workspace"])
    lock = threading.RLock()

    def root(identity):
        key = hashlib.sha256(identity["user_id"].encode()).hexdigest()[:32]
        path = Path(data_dir) / "workspace" / "files" / key
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def target(identity, name):
        relative = PurePosixPath(name.replace("\\", "/"))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or any(":" in p or p.startswith(".") or "\0" in p for p in relative.parts)
        ):
            raise HTTPException(
                422, "Choose a relative workspace path, for example Scripts/example.py"
            )
        reserved = {"CON", "PRN", "AUX", "NUL"} | {
            f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
        }
        if any(
            part.rstrip(" .") != part
            or part.split(".")[0].upper() in reserved
            or any(ord(c) < 32 for c in part)
            for part in relative.parts
        ):
            raise HTTPException(
                422, "Filename is not portable across supported operating systems"
            )
        base = root(identity)
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or path == base:
            raise HTTPException(422, "Path must stay inside your PubCast workspace")
        return path, base

    def revision(raw):
        return hashlib.sha256(raw).hexdigest()

    @router.get("/files")
    def list_files(identity=Depends(current_identity)):
        base = root(identity)
        files = []
        with lock:
            for p in base.rglob("*"):
                if (
                    p.is_file()
                    and not p.is_symlink()
                    and p.resolve().is_relative_to(base)
                    and not any(
                        part.startswith(".") for part in p.relative_to(base).parts
                    )
                ):
                    files.append(
                        {
                            "path": p.relative_to(base).as_posix(),
                            "size": p.stat().st_size,
                        }
                    )
        return {"files": sorted(files, key=lambda f: f["path"])}

    @router.get("/file")
    def read_file(path: str, identity=Depends(current_identity)):
        p, _ = target(identity, path)
        with lock:
            if not p.is_file():
                raise HTTPException(404, "Workspace file not found")
            if p.stat().st_size > MAX_FILE:
                raise HTTPException(413, "File exceeds 32 MB workspace transfer limit")
            raw = p.read_bytes()
        return {
            "path": path,
            "data": base64.b64encode(raw).decode(),
            "revision": revision(raw),
        }

    @router.post("/file")
    def save_file(body: SaveFile, identity=Depends(current_identity)):
        p, base = target(identity, body.path)
        try:
            raw = base64.b64decode(body.data, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(422, "Invalid file bytes") from exc
        if len(raw) > MAX_FILE:
            raise HTTPException(413, "File exceeds 32 MB workspace transfer limit")
        with lock:
            if p.exists():
                if not p.is_file():
                    raise HTTPException(409, "Destination is not a file")
                current = revision(p.read_bytes())
                if current != body.expected_revision:
                    raise HTTPException(
                        409,
                        "File changed or already exists. Open it before replacing it, or choose another name.",
                    )
            elif body.expected_revision is not None:
                raise HTTPException(
                    409,
                    "The previously saved file was removed. Choose a new destination.",
                )
            p.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=p.parent, delete=False) as f:
                    temporary = Path(f.name)
                    f.write(raw)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary, p)
                from .persistence import _fsync_directory

                _fsync_directory(p.parent)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
        return {
            "path": p.relative_to(base).as_posix(),
            "revision": revision(raw),
            "size": len(raw),
        }

    @router.post("/check-python")
    def check_python(body: CheckPython, identity=Depends(current_identity)):
        try:
            compile(body.text, body.name, "exec")
        except (SyntaxError, ValueError) as exc:
            return {
                "ok": False,
                "message": str(exc),
                "line": getattr(exc, "lineno", None),
                "column": getattr(exc, "offset", None),
            }
        return {"ok": True, "message": "Python syntax is valid; code was not executed."}

    return router
