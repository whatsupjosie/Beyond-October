"""Resumable original encoded Program takes, owned by RecordingService.

Completed browser blobs are split without re-encoding. Disk-synced numbered
pieces survive an app restart; only a validated assembled stream is an artifact.
SQLite is used solely as a portable interprocess mutex, not a second catalog.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from starlette.requests import ClientDisconnect

from .auth import role_gte
from .persistence import _fsync_directory
from .recording import RecordingService
from .route_security import current_identity

CHUNK_BYTES = 256 * 1024
MAX_TAKE_BYTES = 2 * 1024 ** 3
FREE_RESERVE = 64 * 1024 ** 2
CHAIN_SEED = hashlib.sha256(b"pubcast-encoded-take/1").hexdigest()


def extend_chain(previous: str, digest: str, size: int) -> str:
    return hashlib.sha256(bytes.fromhex(previous) + bytes.fromhex(digest) + size.to_bytes(8, "big")).hexdigest()


class TakeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    take_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")
    production_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")
    source_id: str = Field(pattern=r"^p25d_[A-Za-z0-9_]{1,110}$")
    mime: str = Field(pattern=r"^(video|audio)/(webm|mp4)(;[A-Za-z0-9=, ._-]{1,100})?$")
    bytes: int = Field(ge=1, le=MAX_TAKE_BYTES)
    chain: str = Field(pattern=r"^[a-f0-9]{64}$")
    width: int = Field(ge=0, le=7680)
    height: int = Field(ge=0, le=4320)
    duration_ms: int = Field(ge=1, le=24 * 3600 * 1000)
    capture_incomplete: bool = False
    manifest: dict

    @model_validator(mode='after')
    def dimensions_match_kind(self):
        if self.mime.startswith('audio/'):
            if self.width or self.height:
                raise ValueError('Independent audio must declare zero video dimensions')
        elif not self.width or not self.height:
            raise ValueError('Video requires positive dimensions')
        return self


async def read_body(request: Request, limit: int, seconds: int = 15) -> bytes:
    async def receive():
        data = bytearray()
        async for piece in request.stream():
            if len(piece) > limit - len(data):
                raise HTTPException(413, "Upload request exceeds its byte limit")
            data.extend(piece)
        return bytes(data)
    try:
        return await asyncio.wait_for(receive(), seconds)
    except asyncio.TimeoutError:
        raise HTTPException(408, "Upload request timed out") from None
    except ClientDisconnect:
        raise HTTPException(400, "Upload connection ended before its chunk was committed") from None


async def read_spec(request: Request) -> TakeSpec:
    def reject(value):
        raise ValueError(value)
    try:
        value = json.loads(await read_body(request, 128 * 1024, 5), parse_constant=reject)
        pending = [(value, 0)]
        visited = 0
        while pending:
            item, depth = pending.pop(); visited += 1
            if depth > 12 or visited > 12000:
                raise ValueError("JSON complexity")
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Non-finite number")
            if isinstance(item, dict):
                pending.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                pending.extend((v, depth + 1) for v in item)
        return TakeSpec.model_validate(value)
    except (ValueError, RecursionError, ValidationError):
        raise HTTPException(422, "Expected bounded, finite take metadata matching the upload schema") from None


@contextmanager
def disk_lock(path: Path):
    """Serialize commit/recovery across threads and processes sharing a take."""
    connection = None
    try:
        connection = sqlite3.connect(str(path), timeout=2)
        connection.execute("CREATE TABLE IF NOT EXISTS mutex (id INTEGER PRIMARY KEY)")
        connection.execute("BEGIN IMMEDIATE")
        yield
        connection.commit()
    except sqlite3.OperationalError as error:
        if (getattr(error, "sqlite_errorcode", 0) & 255) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            raise HTTPException(503, "Take is busy; retry the same request") from None
        raise HTTPException(507, "Server storage lock is unavailable; keep the local take") from None
    finally:
        if connection is not None:
            connection.close()


class EncodedTakeIngest:
    _decoders = threading.BoundedSemaphore(2)
    def __init__(self, recording: RecordingService):
        self.recording = recording

    def _load(self, take: str, owner: str):
        if not take.startswith("enc_") or len(take) != 44 or any(c not in "0123456789abcdef" for c in take[4:]):
            raise HTTPException(404, "Take not found")
        directory = self.recording.recordings_dir / take
        try:
            metadata = directory / (take + ".json")
            if directory.is_symlink() or metadata.stat().st_size > 256 * 1024:
                raise ValueError()
            session = self.recording._session_from_dict(json.loads(metadata.read_text()))
        except (OSError, ValueError, KeyError, TypeError):
            raise HTTPException(404, "Take not found") from None
        if not session.ingest or session.operator != owner:
            raise HTTPException(404, "Take not found")
        return session

    def _commit(self, session):
        session.updated_at = time.time()
        self.recording._write_metadata(session)
        self.recording._sessions[session.session_id] = session

    @staticmethod
    def _status(session):
        data = session.ingest
        return {"id": session.session_id, "owner": session.operator,
                "state": data["state"], "take_id": data["spec"]["take_id"],
                "production_id": data["spec"]["production_id"],
                "received_bytes": data["received_bytes"], "expected_bytes": data["spec"]["bytes"],
                "next_index": data["next_index"], "chain": data["chain"],
                "chunk_bytes": CHUNK_BYTES, "sha256": data.get("sha256"),
                "capture_incomplete": data["spec"]["capture_incomplete"],
                "capture_started_at": session.started_at if data.get("capture_timing") != "unknown" else None,
                "capture_ended_at": session.ended_at if data.get("capture_timing") != "unknown" else None,
                "capture_timing": data.get("capture_timing"),
                "upload_started_at": data.get("upload_started_at"),
                "upload_completed_at": data.get("upload_completed_at"),
                "media": data.get("media"), "updated_at": session.updated_at}

    def create(self, owner: str, spec: TakeSpec, can_create: bool = True):
        take = "enc_" + hashlib.sha256((owner + "\0" + spec.take_id).encode()).hexdigest()[:40]
        directory = self.recording.recordings_dir / take
        with disk_lock(self.recording.recordings_dir / ".encoded-creation.sqlite"):
            if directory.exists():
                session = self._load(take, owner)
                if session.ingest["spec"] != spec.model_dump():
                    raise HTTPException(409, "This take ID already has different content or metadata")
                (directory / "pieces").mkdir(exist_ok=True)
                return self._status(session)
            if not can_create:
                raise HTTPException(403, "A studio operator role is required to create a new take")
            if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
                raise HTTPException(503, "Media validation is unavailable; keep the local take")
            if shutil.disk_usage(self.recording.recordings_dir).free < spec.bytes * 2 + FREE_RESERVE:
                raise HTTPException(507, "Not enough server space to preserve and validate this take")
            # Bound abandoned reservations without deleting anyone's source bytes.
            pending = []
            for path in self.recording.recordings_dir.glob("enc_*/enc_*.json"):
                if path.stat().st_size > 256 * 1024:
                    continue
                try:
                    item = json.loads(path.read_text())
                    if item.get("ingest", {}).get("state") == "uploading":
                        pending.append(item)
                except (ValueError, OSError, AttributeError):
                    continue
            if sum(s.get("operator") == owner for s in pending) >= 8 or len(pending) >= 64:
                raise HTTPException(429, "Finish existing take uploads before creating another")
            try:
                session = self.recording.create_encoded_take(take, source=spec.source_id, operator=owner,
                    ingest={"schema": "pubcast-encoded-take/1", "state": "uploading", "spec": spec.model_dump(),
                            "received_bytes": 0, "next_index": 0, "chain": CHAIN_SEED})
            except (ValueError, PermissionError):
                raise HTTPException(409, "Studio source is unavailable or recording is disallowed") from None
            (directory / "pieces").mkdir()
            return self._status(session)

    def status(self, take, owner):
        session = self._load(take, owner)
        return self._status(session)

    def listing(self, owner):
        # Discover fresh metadata, including takes committed by another process.
        output = []
        for path in self.recording.recordings_dir.glob("enc_*"):
            try:
                output.append(self.status(path.name, owner))
            except HTTPException:
                continue
        return sorted(output, key=lambda d: d["updated_at"], reverse=True)

    def append(self, take, owner, index, content, digest):
        session = self._load(take, owner)  # Authorization before creating a lock file.
        directory = self.recording.recordings_dir / take
        with disk_lock(directory / ".encoded-mutex.sqlite"):
            session = self._load(take, owner)
            data = session.ingest
            if data["state"] == "abandoned":
                raise HTTPException(409, "Upload was ended; its original pieces are retained")
            if hashlib.sha256(content).hexdigest() != digest:
                raise HTTPException(422, "Chunk checksum mismatch")
            expected = min(CHUNK_BYTES, data["spec"]["bytes"] - index * CHUNK_BYTES)
            if index < 0 or expected <= 0 or len(content) != expected:
                raise HTTPException(422, "Chunk size or index does not match this take")
            if index > data["next_index"]:
                raise HTTPException(409, "Send the next chunk in order")
            piece = directory / "pieces" / f"{index:08d}.part"
            if piece.exists():
                if piece.is_symlink() or piece.read_bytes() != content:
                    raise HTTPException(409, "A different chunk already occupies this index")
                if index < data["next_index"]:
                    return self._status(session)  # Lost ACK: do not append twice.
            elif data["state"] == "complete" or index < data["next_index"]:
                raise HTTPException(409, "Committed source pieces are unavailable")
            else:
                if shutil.disk_usage(directory).free < len(content) + FREE_RESERVE:
                    raise HTTPException(507, "Server storage is full; local take is retained")
                fd, name = tempfile.mkstemp(prefix=".pending-", dir=piece.parent)
                try:
                    with os.fdopen(fd, "wb") as output:
                        output.write(content); output.flush(); os.fsync(output.fileno())
                    os.replace(name, piece); _fsync_directory(piece.parent)
                finally:
                    Path(name).unlink(missing_ok=True)
            # If a crash occurred after publishing the piece, this same request
            # repairs the metadata commit and advances exactly once.
            data["chain"] = extend_chain(data["chain"], digest, len(content))
            data["next_index"] += 1; data["received_bytes"] += len(content)
            self._commit(session)
            return self._status(session)

    @staticmethod
    def probe(path: Path, spec: dict):
        try:
            result = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error",
                "-protocol_whitelist", "file,pipe", "-show_entries",
                "stream=codec_type,codec_name,width,height,sample_rate,channels:format=format_name,duration",
                "-of", "json", str(path)], capture_output=True, timeout=20, check=True)
            info = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.SubprocessError):
            raise HTTPException(422, "Uploaded bytes are not a readable encoded video; source pieces retained") from None
        streams = info.get("streams", [])
        video = [s for s in streams if s.get("codec_type") == "video"]
        fmt = info.get("format", {}).get("format_name", "")
        audio_only = spec['mime'].startswith('audio/')
        audio = [s for s in streams if s.get('codec_type') == 'audio']
        if audio_only and (video or len(audio) != 1 or len(streams) != 1):
            raise HTTPException(422, 'Independent voice source must contain exactly one audio stream and no video')
        if not audio_only and (len(streams) > 8 or len(video) != 1 or video[0].get("width") != spec["width"] or video[0].get("height") != spec["height"]):
            raise HTTPException(422, "Encoded video does not match the declared camera dimensions")
        if ("webm" in spec["mime"] and "webm" not in fmt) or ("mp4" in spec["mime"] and "mp4" not in fmt):
            raise HTTPException(422, "Encoded container does not match the declared media type")
        if not EncodedTakeIngest._decoders.acquire(blocking=False):
            raise HTTPException(503, "Media validator is busy; retry completion")
        try:
            subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-xerror", "-nostdin",
                "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:a:0" if audio_only else "0:v:0",
                *( ["-t", "0.1"] if audio_only else ["-frames:v", "1"] ), "-threads", "1", "-f", "null", "-"],
                capture_output=True, timeout=20, check=True)
        except (OSError, subprocess.SubprocessError):
            raise HTTPException(422, "Uploaded video has no decodable first frame; source pieces retained") from None
        finally:
            EncodedTakeIngest._decoders.release()
        return info

    def finish(self, take, owner):
        self._load(take, owner)
        directory = self.recording.recordings_dir / take
        with disk_lock(directory / ".encoded-mutex.sqlite"):
            session = self._load(take, owner); data = session.ingest; spec = data["spec"]
            if data["state"] == "abandoned":
                raise HTTPException(409, "Upload was ended; its original pieces are retained")
            if data["state"] == "complete":
                self.media(take, owner)
                return self._status(session)
            if data["received_bytes"] != spec["bytes"] or data["chain"] != spec["chain"]:
                raise HTTPException(409, "Take is incomplete or its chunk manifest does not match")
            if shutil.disk_usage(directory).free < spec["bytes"] + FREE_RESERVE:
                raise HTTPException(507, "Not enough server space to assemble the take")
            suffix = ".webm" if "webm" in spec["mime"] else ".mp4"
            target = directory / ("program-original" + suffix)
            pending = directory / (".assembling" + suffix)
            digest = hashlib.sha256(); chain = CHAIN_SEED; size = 0
            try:
                with pending.open("wb") as output:
                    for index in range(data["next_index"]):
                        piece = directory / "pieces" / f"{index:08d}.part"
                        if piece.is_symlink():
                            raise HTTPException(409, "Source piece is invalid")
                        content = piece.read_bytes()
                        chain = extend_chain(chain, hashlib.sha256(content).hexdigest(), len(content))
                        output.write(content); digest.update(content); size += len(content)
                    output.flush(); os.fsync(output.fileno())
                if size != spec["bytes"] or chain != spec["chain"]:
                    raise HTTPException(409, "Stored source integrity check failed")
                info = self.probe(pending, spec)
                if target.exists():
                    if self.recording._file_digest(target) != digest.hexdigest():
                        raise HTTPException(409, "An existing original has different bytes; no overwrite allowed")
                else:
                    os.replace(pending, target); _fsync_directory(directory)
                self.recording.commit_encoded_take(session, target, digest.hexdigest(), info)
                return self._status(session)
            finally:
                pending.unlink(missing_ok=True)

    def media(self, take, owner):
        session = self._load(take, owner); data = session.ingest
        if data["state"] != "complete" or not session.artifacts:
            raise HTTPException(409, "No validated completed take is available")
        path = session.artifacts[0].file_path
        if path.is_symlink() or not path.is_file() or path.stat().st_size != data["spec"]["bytes"] or self.recording._file_digest(path) != data["sha256"]:
            raise HTTPException(409, "Saved source failed its integrity check")
        return path, data["spec"]["mime"].split(";")[0], data["sha256"]

    def abandon(self, take, owner):
        self._load(take, owner)
        with disk_lock(self.recording.recordings_dir / take / ".encoded-mutex.sqlite"):
            session = self._load(take, owner)
            if session.ingest["state"] == "complete":
                raise HTTPException(409, "Completed originals are immutable")
            session.ingest["state"] = "abandoned"; self._commit(session)
            return self._status(session)

    def bundle(self, take, owner):
        self.media(take, owner)
        return self.recording.export_session(take, container=self.recording.get_session(take).artifacts[0].format)


def create_studio25d_recording_router(recording: RecordingService):
    router = APIRouter(prefix="/api/studio25d/recordings", tags=["Encoded studio takes"])
    ingest = EncodedTakeIngest(recording)

    async def owner(identity=Depends(current_identity)):
        if not identity.get("authenticated"):
            raise HTTPException(403, "Authenticated owner required")
        return str(identity["user_id"])

    async def io(action, *args):
        try:
            return await asyncio.to_thread(action, *args)
        except OSError:
            raise HTTPException(507, "Server storage operation failed; keep the local take and retry") from None

    @router.post("")
    async def create(request: Request, actor=Depends(owner), identity=Depends(current_identity)):
        return await io(ingest.create, actor, await read_spec(request), role_gte(identity.get("role", "guest"), "mod"))

    @router.get("")
    async def listing(actor=Depends(owner)):
        return {"takes": await io(ingest.listing, actor)}

    @router.get("/{take_id}")
    async def status(take_id: str, actor=Depends(owner)):
        return await io(ingest.status, take_id, actor)

    @router.put("/{take_id}/chunks/{index}")
    async def append(take_id: str, index: int, request: Request, actor=Depends(owner)):
        await io(ingest.status, take_id, actor)
        digest = request.headers.get("X-Chunk-SHA256", "")
        if len(digest) != 64 or any(c not in "abcdef0123456789" for c in digest):
            raise HTTPException(400, "Chunk SHA-256 required")
        if request.headers.get("content-type") != "application/octet-stream":
            raise HTTPException(415, "Binary encoded-media chunk required")
        return await io(ingest.append, take_id, actor, index, await read_body(request, CHUNK_BYTES), digest)

    @router.post("/{take_id}/complete")
    async def finish(take_id: str, actor=Depends(owner)):
        return await io(ingest.finish, take_id, actor)

    @router.get("/{take_id}/media")
    async def media(take_id: str, actor=Depends(owner)):
        path, mime, digest = await io(ingest.media, take_id, actor)
        return FileResponse(path, media_type=mime, filename=path.name,
                            headers={"Cache-Control": "private, no-store", "X-Source-SHA256": digest})

    @router.post("/{take_id}/abandon")
    async def abandon(take_id: str, actor=Depends(owner)):
        return await io(ingest.abandon, take_id, actor)

    @router.post("/{take_id}/bundle")
    async def bundle(take_id: str, actor=Depends(owner)):
        path = await io(ingest.bundle, take_id, actor)
        return FileResponse(path, media_type="application/zip", filename=path.name,
                            headers={"Cache-Control": "private, no-store"})

    return router
