"""Versioned, lossless portable container for 2i rich-document working copies.

This is a persistence boundary, not a DOCX renderer. `original` is immutable
source evidence; `working_docx` is produced by the licensed free editor core.
Both are retained byte-for-byte. Legacy JSON .2i v4 is read-only here and may
never be silently reinterpreted as this ZIP-based v5 representation.

The archive uses three fixed member names; external archive member names are
never mapped to filesystem paths. Parsing is bounded before decompression and
all extracted bytes are verified against their manifest digests.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zlib
import uuid
import zipfile
from dataclasses import dataclass, field
from typing import Any

FORMAT = "pubcast-2i-rich"
VERSION = 5
MAX_CONTAINER = 32 * 1024 * 1024  # Same disk workspace transfer ceiling.
MAX_PART = 24 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 48 * 1024 * 1024 + 256 * 1024
MAX_MANIFEST = 256 * 1024
MANIFEST = "manifest.json"
ORIGINAL = "source/original.bin"
WORKING = "working/document.docx"
ENTRIES = (MANIFEST, ORIGINAL, WORKING)
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class RichDocumentError(ValueError):
    """Safe client-facing validation failure: no user state was modified."""


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out = {}
    for key, value in pairs:
        if key in out:
            raise RichDocumentError(f"Duplicate JSON field: {key}")
        out[key] = value
    return out


def _json_dumps(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError) as e:
        raise RichDocumentError("Invalid rich-document metadata") from e


def _json_loads(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               RichDocumentError("Non-finite JSON number")))
    except (UnicodeError, ValueError, TypeError, RecursionError) as e:
        raise RichDocumentError("Invalid rich-document manifest") from e
    if not isinstance(value, dict):
        raise RichDocumentError("Manifest must be a JSON object")
    return value


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not (1 <= len(name) <= 255):
        raise RichDocumentError("Original filename must be 1–255 characters")
    if name in {".", ".."} or "/" in name or "\\" in name or _CONTROL.search(name):
        raise RichDocumentError("Original filename must not contain a path or control characters")
    if name != name.strip():
        raise RichDocumentError("Original filename must not have leading or trailing spaces")


def _validate_docx(raw: bytes) -> None:
    """Confirm DOCX structural markers without editing or reserializing it."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_PART:
        raise RichDocumentError("Working DOCX is missing or exceeds 24 MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = z.namelist()
            parts = z.infolist()
            if len(names) != len(set(names)):
                raise RichDocumentError("Working DOCX has duplicate package members")
            if len(parts) > 10000 or sum(x.file_size for x in parts) > 128 * 1024 * 1024:
                raise RichDocumentError("Working DOCX package exceeds structural limits")
            if any(x.flag_bits & 1 or x.file_size < 0 or x.compress_type not in
                   {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED} for x in parts):
                raise RichDocumentError("Encrypted or unsupported DOCX members")
            if any((x.external_attr >> 16) & 0o170000 == 0o120000 for x in parts):
                raise RichDocumentError("Working DOCX cannot contain symlinks")
            if any(name.startswith("/") or "\\" in name or
                   any(part == ".." for part in name.split("/")) or
                   _CONTROL.search(name) for name in names):
                raise RichDocumentError("Unsafe DOCX member path")
            if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                raise RichDocumentError("Working payload is not a DOCX document")
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
        raise RichDocumentError("Working payload is not a valid DOCX ZIP") from e


def _validate_id(document_id: str) -> None:
    try:
        parsed = uuid.UUID(document_id)
    except (ValueError, TypeError, AttributeError) as e:
        raise RichDocumentError("Document identity must be a UUID") from e
    if str(parsed) != document_id:
        raise RichDocumentError("Document identity must be a canonical lowercase UUID")


@dataclass(frozen=True)
class RichDocument:
    document_id: str
    original_name: str
    original_mime: str
    original: bytes
    working_docx: bytes
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _validate_id(self.document_id)
        _validate_name(self.original_name)
        if not isinstance(self.original_mime, str) or not 1 <= len(self.original_mime) <= 255 or _CONTROL.search(self.original_mime):
            raise RichDocumentError("Invalid original MIME type")
        if not isinstance(self.original, bytes) or len(self.original) > MAX_PART:
            raise RichDocumentError("Original exceeds 24 MiB")
        if not isinstance(self.metadata, dict):
            raise RichDocumentError("Metadata must be a JSON object")
        if len(_json_dumps(self.metadata)) > MAX_MANIFEST // 2:
            raise RichDocumentError("Metadata exceeds the portable document limit")
        _validate_docx(self.working_docx)


def manifest_for(doc: RichDocument) -> dict[str, Any]:
    doc.validate()
    return {
        "format": FORMAT,
        "version": VERSION,
        "document_id": doc.document_id,
        "original": {
            "path": ORIGINAL, "name": doc.original_name,
            "mime": doc.original_mime, "size": len(doc.original), "sha256": _hash(doc.original),
        },
        "working": {
            "path": WORKING,
            "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "size": len(doc.working_docx), "sha256": _hash(doc.working_docx),
        },
        "metadata": doc.metadata,
    }


def pack(doc: RichDocument) -> bytes:
    """Create a deterministic, bounded ZIP; never overwrite the supplied source."""
    manifest = _json_dumps(manifest_for(doc))
    if len(manifest) > MAX_MANIFEST:
        raise RichDocumentError("Manifest exceeds 256 KiB")
    data = {MANIFEST: manifest, ORIGINAL: doc.original, WORKING: doc.working_docx}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=False) as z:
        for name in ENTRIES:
            info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100600 << 16
            z.writestr(info, data[name], compress_type=zipfile.ZIP_DEFLATED,
                       compresslevel=6)
    packed = out.getvalue()
    if len(packed) > MAX_CONTAINER:
        raise RichDocumentError("Rich 2i archive exceeds 32 MiB workspace limit")
    return packed


def _expect_blob(z: zipfile.ZipFile, name: str, entry: Any) -> bytes:
    expected_fields = {"path", "mime", "size", "sha256"}
    if name == ORIGINAL:
        expected_fields.add("name")
    if not isinstance(entry, dict) or set(entry) != expected_fields:
        raise RichDocumentError(f"Invalid manifest descriptor: {name}")
    if entry["path"] != name or not isinstance(entry["size"], int) or isinstance(entry["size"], bool):
        raise RichDocumentError(f"Invalid payload descriptor: {name}")
    if not 0 <= entry["size"] <= MAX_PART:
        raise RichDocumentError("Payload exceeds 24 MiB")
    if not isinstance(entry["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
        raise RichDocumentError("Invalid payload checksum")
    if not isinstance(entry["mime"], str) or not 1 <= len(entry["mime"]) <= 255:
        raise RichDocumentError("Invalid payload MIME type")
    member = z.getinfo(name)
    if member.file_size != entry["size"]:
        raise RichDocumentError(f"Payload integrity failed (size conflicts with archive index): {name}")
    data = z.read(name)
    if len(data) != entry["size"] or _hash(data) != entry["sha256"]:
        raise RichDocumentError(f"Payload integrity verification failed: {name}")
    return data


def unpack(raw: bytes) -> RichDocument:
    """Verify strict v5 membership, digest, format, identity and size constraints."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_CONTAINER:
        raise RichDocumentError("Rich 2i archive is missing or exceeds 32 MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as z:
            members = z.infolist()
            if len(members) != len(ENTRIES) or {x.filename for x in members} != set(ENTRIES):
                raise RichDocumentError("Rich 2i archive contains missing or unexpected members")
            if any(x.flag_bits & 1 or x.is_dir() or x.file_size < 0 or
                   x.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                   for x in members):
                raise RichDocumentError("Encrypted or directory members are not supported")
            if any((x.external_attr >> 16) & 0o170000 == 0o120000 for x in members):
                raise RichDocumentError("Symbolic links are forbidden in 2i archives")
            if sum(x.file_size for x in members) > MAX_TOTAL_UNCOMPRESSED:
                raise RichDocumentError("Archive expands beyond the 2i safety budget")
            if z.getinfo(MANIFEST).file_size > MAX_MANIFEST:
                raise RichDocumentError("Manifest exceeds 256 KiB")
            manifest = _json_loads(z.read(MANIFEST))
            if set(manifest) != {"format", "version", "document_id", "original", "working", "metadata"}:
                raise RichDocumentError("Unrecognized rich-document manifest fields")
            if manifest["format"] != FORMAT or manifest["version"] != VERSION:
                raise RichDocumentError("Unsupported rich 2i format or version; original preserved")
            original = _expect_blob(z, ORIGINAL, manifest["original"])
            working = _expect_blob(z, WORKING, manifest["working"])
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError,
            OSError, EOFError, zlib.error) as e:
        raise RichDocumentError("Invalid or damaged rich 2i archive") from e
    doc = RichDocument(document_id=manifest["document_id"],
                       original_name=manifest["original"]["name"],
                       original_mime=manifest["original"]["mime"],
                       original=original, working_docx=working,
                       metadata=manifest["metadata"])
    doc.validate()
    if manifest_for(doc) != manifest:
        raise RichDocumentError("Manifest failed canonical integrity checks")
    return doc


def identify(raw: bytes) -> str:
    """Classify without modifying; a v4 JSON file is never auto-migrated."""
    if not isinstance(raw, bytes):
        raise RichDocumentError("2i content must be bytes")
    if raw.startswith(b"PK"):
        unpack(raw)  # Detection must not bless an unverified ZIP.
        return "rich-v5"
    if len(raw) > MAX_CONTAINER:
        raise RichDocumentError("Legacy manuscript exceeds the import limit")
    legacy = _json_loads(raw)
    if legacy.get("format") == "2i-document" and legacy.get("version") == 4 and isinstance(legacy.get("state"), dict):
        return "manuscript-v4"
    raise RichDocumentError("Unsupported 2i format/version; original bytes unchanged")
