"""Offline, byte-preserving host-data checkpoints, independent of the app runtime.

The caller must stop every writer before capture. File inventory, identity and
hash rechecks detect observed changes; they are not a live multi-store lock.
No network, database migration, key rotation or application import occurs here.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import stat
import tempfile
import unicodedata
import zipfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator

FORMAT = "PubCastDataCheckpoint.v1"
MANIFEST = "PUBCAST_CHECKPOINT.json"
CHUNK = 1024 * 1024
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_DEVICE = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])$", re.I)


class CheckpointError(ValueError):
    """The checkpoint could not be safely created, verified or restored."""


@dataclass(frozen=True)
class Limits:
    max_files: int = 100_000
    max_bytes: int = 100 * 1024**3
    max_manifest_bytes: int = 16 * 1024**2

    def __post_init__(self) -> None:
        for value in (self.max_files, self.max_bytes, self.max_manifest_bytes):
            if type(value) is not int or value < 1:
                raise CheckpointError("Limits must be positive integers")


def _path(value: object) -> str:
    """Require one unambiguous relative name, portable to Windows and POSIX."""
    try:
        valid = isinstance(value, str) and bool(value) and len(value.encode("utf-8")) <= 4096
    except UnicodeError:
        valid = False
    if not valid:
        raise CheckpointError("Invalid checkpoint path")
    for part in value.split("/"):
        if (not part or part in (".", "..") or part[-1] in " ."
                or any(ord(c) < 32 or c in '<>:"\\|?*' for c in part)
                or _DEVICE.fullmatch(part.split(".")[0])):
            raise CheckpointError(f"Nonportable or unsafe path: {value!r}")
    return value


def _names(directories: list[str], files: list[str]) -> None:
    seen: set[str] = set()
    directory_set = set(directories)
    for name in directories + files:
        _path(name)
        folded = unicodedata.normalize("NFC", name).casefold()
        if folded in seen:
            raise CheckpointError(f"Duplicate or case/Unicode-colliding path: {name!r}")
        seen.add(folded)
        parent = name.rpartition("/")[0]
        if parent and parent not in directory_set:
            raise CheckpointError(f"Missing parent directory: {parent!r}")


def _signature(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _ordinary(info: os.stat_result, *, directory: bool) -> bool:
    reparse = getattr(info, "st_file_attributes", 0) & 0x400
    return not reparse and (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))


def _scan(root: Path, limits: Limits) -> tuple[list[str], dict[str, tuple[int, ...]]]:
    if not _ordinary(root.lstat(), directory=True):
        raise CheckpointError("Data root must be an ordinary directory, not a link")
    directories: list[str] = []
    files: dict[str, tuple[int, ...]] = {}
    total = 0

    def failed(error: OSError) -> None:
        raise error

    for current, child_dirs, child_files in os.walk(root, followlinks=False, onerror=failed):
        for name, is_directory in [(x, True) for x in child_dirs] + [(x, False) for x in child_files]:
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            if not _ordinary(info, directory=is_directory):
                raise CheckpointError(f"Links and special files cannot be checkpointed: {relative!r}")
            if is_directory:
                directories.append(relative)
            else:
                files[relative] = _signature(info)
                total += info.st_size
            if len(files) + len(directories) > limits.max_files or total > limits.max_bytes:
                raise CheckpointError("Data tree exceeds configured file/byte limits")
    directories.sort()
    files = dict(sorted(files.items()))
    _names(directories, list(files))
    return directories, files


@contextlib.contextmanager
def _reader(path: Path, expected: tuple[int, ...] | None = None) -> Iterator[BinaryIO]:
    before = path.lstat()
    if not _ordinary(before, directory=False):
        raise CheckpointError(f"Not an ordinary file: {path.name!r}")
    if expected is not None and _signature(before) != expected:
        raise CheckpointError(f"Source changed: {path.name!r}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        if _signature(os.fstat(stream.fileno())) != _signature(before):
            raise CheckpointError(f"File changed while opening: {path.name!r}")
        yield stream
        if (_signature(os.fstat(stream.fileno())) != _signature(before)
                or _signature(path.lstat()) != _signature(before)):
            raise CheckpointError(f"File changed while reading: {path.name!r}")


def _transfer(source: BinaryIO, destination: BinaryIO | None, *, size: int) -> str:
    digest = hashlib.sha256()
    count = 0
    while True:
        block = source.read(min(CHUNK, size - count + 1))
        if not block:
            break
        count += len(block)
        if count > size:
            raise CheckpointError("File exceeds its declared size")
        digest.update(block)
        if destination is not None:
            destination.write(block)
    if count != size:
        raise CheckpointError("File is shorter than its declared size")
    return digest.hexdigest()


def _sync_directory(path: Path) -> None:
    # Windows does not support opening directories through os.open. File fsync
    # still runs there. Do not claim power-loss durability on every filesystem.
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise CheckpointError(f"Duplicate manifest field: {key!r}")
        result[key] = value
    return result


def _validate_manifest(value: object, limits: Limits) -> dict:
    if not isinstance(value, dict) or value.get("format") != FORMAT:
        raise CheckpointError("Unsupported checkpoint format")
    if value.get("offline") is not True or value.get("private_runtime_data") is not True:
        raise CheckpointError("Missing offline/private-data declaration")
    rows, directories = value.get("files"), value.get("directories")
    if not isinstance(rows, list) or not isinstance(directories, list):
        raise CheckpointError("Missing checkpoint inventory")
    if len(rows) + len(directories) > limits.max_files:
        raise CheckpointError("Checkpoint exceeds file limit")
    names: list[str] = []
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            raise CheckpointError("Invalid file inventory entry")
        names.append(_path(row.get("path")))
        size, modified = row.get("size"), row.get("mtime_ns")
        if type(size) is not int or size < 0 or type(modified) is not int or modified < 0:
            raise CheckpointError("Invalid file size or modification time")
        if not isinstance(row.get("sha256"), str) or not _DIGEST.fullmatch(row["sha256"]):
            raise CheckpointError("Invalid SHA-256 in manifest")
        total += size
        if total > limits.max_bytes:
            raise CheckpointError("Checkpoint exceeds byte limit")
    _names([_path(x) for x in directories], names)
    return value


def _verify_zip(archive: zipfile.ZipFile, limits: Limits) -> dict:
    members = archive.infolist()
    if len(members) > limits.max_files + 1:
        raise CheckpointError("Archive exceeds member limit")
    member_names = [member.filename for member in members]
    if len(set(member_names)) != len(member_names):
        raise CheckpointError("Duplicate ZIP member")
    for member in members:
        mode = member.external_attr >> 16
        if (member.is_dir() or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))
                or member.flag_bits & 1
                or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
            raise CheckpointError("Unsupported ZIP member type or encoding")
    if MANIFEST not in member_names:
        raise CheckpointError("Checkpoint manifest is missing")
    info = archive.getinfo(MANIFEST)
    if info.file_size > limits.max_manifest_bytes:
        raise CheckpointError("Manifest exceeds size limit")
    with archive.open(info) as stream:
        encoded = stream.read(limits.max_manifest_bytes + 1)
    if len(encoded) > limits.max_manifest_bytes:
        raise CheckpointError("Manifest exceeds size limit")
    try:
        value = json.loads(encoded, object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise CheckpointError("Invalid checkpoint manifest JSON") from error
    manifest = _validate_manifest(value, limits)
    expected = {MANIFEST, *("data/" + row["path"] for row in manifest["files"])}
    if set(member_names) != expected:
        raise CheckpointError("ZIP members do not match the complete manifest")
    for row in manifest["files"]:
        info = archive.getinfo("data/" + row["path"])
        if info.file_size != row["size"]:
            raise CheckpointError(f"Size mismatch: {row['path']!r}")
        with archive.open(info) as stream:
            digest = _transfer(stream, None, size=row["size"])
        if digest != row["sha256"]:
            raise CheckpointError(f"SHA-256 mismatch: {row['path']!r}")
    return manifest


@contextlib.contextmanager
def _verified_archive(path: Path, limits: Limits, expected_sha256: str | None) -> Iterator[tuple[zipfile.ZipFile, dict, str]]:
    if expected_sha256 is not None and not _DIGEST.fullmatch(expected_sha256):
        raise CheckpointError("Expected SHA-256 must be 64 lowercase hexadecimal characters")
    try:
        with _reader(path) as stream:
            digest = _transfer(stream, None, size=os.fstat(stream.fileno()).st_size)
            if expected_sha256 is not None and digest != expected_sha256:
                raise CheckpointError("Archive SHA-256 does not match the trusted digest")
            stream.seek(0)
            with zipfile.ZipFile(stream) as archive:
                manifest = _verify_zip(archive, limits)
                yield archive, manifest, digest
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, NotImplementedError, zlib.error) as error:
        raise CheckpointError(f"Unreadable checkpoint archive: {error}") from error


def _summary(manifest: dict, digest: str) -> dict:
    return {"ok": True, "format": FORMAT, "sha256": digest,
            "file_count": len(manifest["files"]),
            "bytes": sum(row["size"] for row in manifest["files"]),
            "private_runtime_data": True,
            "source_revision": manifest.get("source_revision", "")}


def verify_checkpoint(archive: Path | str, *, expected_sha256: str | None = None,
                      limits: Limits | None = None) -> dict:
    """Stream and check every byte; optionally bind to an external trusted hash."""
    with _verified_archive(Path(archive), limits or Limits(), expected_sha256) as (_, manifest, digest):
        result = _summary(manifest, digest)
    return result


def create_checkpoint(data_dir: Path | str, output: Path | str, *, offline: bool = False,
                      source_revision: str = "", limits: Limits | None = None) -> dict:
    """Capture the entire stopped host-data tree, including keys and SQLite WALs.

    Refuse a moving tree, links, nonportable names and output inside the source.
    Only a fully verified archive is published, atomically, without replacement.
    """
    if offline is not True:
        raise CheckpointError("Stop every PubCast writer, then explicitly pass --offline")
    limits = limits or Limits()
    source = Path(data_dir).expanduser().absolute()
    if not source.is_dir() or not _ordinary(source.lstat(), directory=True):
        raise CheckpointError("Data root must be an existing ordinary directory")
    source = source.resolve()
    target = Path(output).expanduser().absolute()
    if target.parent.resolve().is_relative_to(source):
        raise CheckpointError("Checkpoint output must be outside the data directory")
    if os.path.lexists(target):
        raise CheckpointError("Checkpoint output already exists; choose a new filename")
    directories, files = _scan(source, limits)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".pubcast-checkpoint-", suffix=".pending", dir=target.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        rows: list[dict] = []
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for relative, signature in files.items():
                info = zipfile.ZipInfo("data/" + relative)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                with _reader(source / relative, signature) as stream, archive.open(info, "w", force_zip64=True) as member:
                    digest = _transfer(stream, member, size=signature[3])
                rows.append({"path": relative, "size": signature[3], "mtime_ns": signature[4], "sha256": digest})
            manifest = {"format": FORMAT, "created_at": datetime.now(timezone.utc).isoformat(),
                        "offline": True, "private_runtime_data": True,
                        "source_revision": str(source_revision), "directories": directories, "files": rows}
            encoded = _json_bytes(manifest)
            if len(encoded) > limits.max_manifest_bytes:
                raise CheckpointError("Manifest exceeds size limit")
            archive.writestr(MANIFEST, encoded)
        if _scan(source, limits) != (directories, files):
            raise CheckpointError("Source changed during checkpoint; stop all writers and retry")
        for row in rows:
            with _reader(source / row["path"], files[row["path"]]) as stream:
                if _transfer(stream, None, size=row["size"]) != row["sha256"]:
                    raise CheckpointError(f"Source changed: {row['path']!r}")
        if _scan(source, limits) != (directories, files):
            raise CheckpointError("Source changed during verification")
        result = verify_checkpoint(temporary, limits=limits)
        if _scan(source, limits) != (directories, files):
            raise CheckpointError("Source changed while the archive was being verified")
        with temporary.open("rb+") as stream:
            os.fsync(stream.fileno())
        # Atomic no-replace publication: unlike rename/replace, a hard link never
        # overwrites an existing target. Unsupported filesystems fail explicitly.
        os.link(temporary, target)
        _sync_directory(target.parent)
        result["archive"] = str(target)
        return result
    finally:
        temporary.unlink(missing_ok=True)


def restore_checkpoint(archive_path: Path | str, destination: Path | str, *,
                       expected_sha256: str | None = None, limits: Limits | None = None) -> dict:
    """Restore into a NEW container's data/ directory; never merge into live data.

    Verify the entire archive before staging. Hash the bytes again as they are
    extracted. Reserve the new container with mkdir (exclusive), then publish
    the complete data subtree. A final receipt records successful publication.
    """
    limits = limits or Limits()
    target = Path(destination).expanduser().absolute()
    if os.path.lexists(target):
        raise CheckpointError("Restore destination already exists; choose a new directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    with _verified_archive(Path(archive_path), limits, expected_sha256) as (archive, manifest, digest):
        with tempfile.TemporaryDirectory(prefix=".pubcast-restore-", dir=target.parent) as staging:
            data = Path(staging) / "data"
            data.mkdir(mode=0o700)
            for relative in sorted(manifest["directories"], key=lambda x: (x.count("/"), x)):
                (data / relative).mkdir(mode=0o700)
            for row in manifest["files"]:
                path = data / row["path"]
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
                with os.fdopen(descriptor, "wb") as output, archive.open("data/" + row["path"]) as source:
                    actual = _transfer(source, output, size=row["size"])
                    if actual != row["sha256"]:
                        raise CheckpointError(f"Restored hash mismatch: {row['path']!r}")
                    output.flush()
                    os.fsync(output.fileno())
                os.utime(path, ns=(row["mtime_ns"], row["mtime_ns"]))
            for directory in sorted([data, *(data / name for name in manifest["directories"])],
                                    key=lambda x: len(x.parts), reverse=True):
                _sync_directory(directory)
            # Exclusive mkdir is the publication reservation. Even two restores
            # racing for an empty destination cannot overwrite each other.
            target.mkdir(mode=0o700)
            pending = target / ".restore-pending.json"
            receipt = {**_summary(manifest, digest), "restored_at": datetime.now(timezone.utc).isoformat(),
                       "data_directory": "data", "original_created_at": manifest.get("created_at")}
            with pending.open("xb") as stream:
                os.chmod(pending, 0o600)
                stream.write(_json_bytes(receipt))
                stream.flush()
                os.fsync(stream.fileno())
            _sync_directory(target)
            os.rename(data, target / "data")
            os.replace(pending, target / "PUBCAST_RESTORE.json")
            _sync_directory(target)
            _sync_directory(target.parent)
    result = _summary(manifest, digest)
    result.update({"destination": str(target), "data_dir": str(target / "data"),
                   "receipt": str(target / "PUBCAST_RESTORE.json")})
    return result
