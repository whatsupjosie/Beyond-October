"""Transactional single-file storage for PubPartner identity vessels."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import stat
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional

from .errors import (
    VesselConflictError,
    VesselFormatError,
    VesselIntegrityError,
    VesselReadOnlyError,
)
from .schema import APPLICATION_ID, CURRENT_SCHEMA_VERSION, MIGRATIONS

MAX_ASSET_BYTES = 256 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024
_RECORD_TABLES = {
    "vessel_manifest": ("singleton",),
    "identity_records": ("key",),
    "entities": ("entity_id",),
    "relationships": ("relationship_id",),
    "memory_events": ("event_id",),
    "memory_claims": ("claim_id",),
    "memory_evidence": ("evidence_id",),
    "memory_corrections": ("correction_id",),
    "assets": ("sha256",),
    "asset_bindings": ("binding_id",),
}


def _now() -> float:
    return time.time()


def _json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError(f"JSON payload exceeds {MAX_JSON_BYTES} bytes")
    return encoded


def _decode(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _canonical_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_json(dict(value)).encode("utf-8")).hexdigest()


def _bounded_text(value: Any, field: str, *, maximum: int = 8_192, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{field} is required")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    return text


class VesselStore:
    """A validated mount of one `.pubpartner` SQLite vessel.

    Connections are intentionally short-lived. Every write uses
    ``BEGIN IMMEDIATE`` with full synchronous durability. DELETE journaling
    keeps the authoritative vessel as one file after a cleanly completed
    transaction.
    """

    def __init__(self, path: Path | str, *, read_only: bool = False) -> None:
        supplied = Path(path).expanduser()
        if supplied.is_symlink():
            raise VesselFormatError("a vessel cannot be mounted through a symlink")
        self.path = supplied.absolute()
        self.read_only = bool(read_only)

    @classmethod
    def create(
        cls,
        path: Path | str,
        *,
        display_name: str,
        vessel_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "VesselStore":
        store = cls(path)
        if store.path.exists() or store.path.is_symlink():
            raise VesselConflictError(f"vessel already exists: {store.path}")
        parent = store.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        if parent.is_symlink():
            raise VesselFormatError("vessel parent directory cannot be a symlink")

        vessel_id = _bounded_text(vessel_id or f"ppv_{uuid.uuid4().hex}", "vessel_id", maximum=160)
        display_name = _bounded_text(display_name, "display_name", maximum=160)
        created_at = _now()
        # Claim the exact pathname before SQLite opens it. Without O_EXCL, two
        # creators could both pass the existence check and initialize the same
        # identity vessel.
        try:
            descriptor = os.open(
                store.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
        except FileExistsError as exc:
            raise VesselConflictError(f"vessel already exists: {store.path}") from exc
        os.close(descriptor)
        connection: Optional[sqlite3.Connection] = None
        try:
            connection = sqlite3.connect(
                str(store.path), timeout=10.0, isolation_level=None
            )
            store._configure_connection(connection, writable=True)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            for version in range(1, CURRENT_SCHEMA_VERSION + 1):
                connection.executescript(MIGRATIONS[version])
                connection.execute(f"PRAGMA user_version = {version}")
            connection.execute(
                """
                INSERT INTO vessel_manifest
                    (singleton, vessel_id, schema_version, display_name, status,
                     created_at, updated_at, metadata_json)
                VALUES (1, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    vessel_id,
                    CURRENT_SCHEMA_VERSION,
                    display_name,
                    created_at,
                    created_at,
                    _json(dict(metadata or {})),
                ),
            )
            store._append_audit_tx(
                connection,
                event_type="vessel.created",
                record_id=vessel_id,
                payload={"display_name": display_name, "schema_version": CURRENT_SCHEMA_VERSION},
            )
            store._seal_record_tx(
                connection, table="vessel_manifest", record_id="1"
            )
            connection.commit()
        except Exception:
            if connection is not None:
                connection.rollback()
                connection.close()
            try:
                store.path.unlink()
            except FileNotFoundError:
                pass
            raise
        else:
            if connection is not None:
                connection.close()

        store._validate_file_identity()
        store.validate()
        return store

    @classmethod
    def open(cls, path: Path | str, *, read_only: bool = False) -> "VesselStore":
        store = cls(path, read_only=read_only)
        store._validate_file_identity()
        store.validate()
        return store

    def _validate_file_identity(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        if self.path.is_symlink():
            raise VesselFormatError("a vessel cannot be mounted through a symlink")
        info = self.path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise VesselFormatError("a vessel must be one regular file")
        if info.st_nlink != 1:
            raise VesselFormatError("hard-linked vessels are not accepted")

    @staticmethod
    def _configure_connection(connection: sqlite3.Connection, *, writable: bool) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        if writable:
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
        else:
            connection.execute("PRAGMA query_only = ON")

    def _connect(self, *, writable: bool = False) -> sqlite3.Connection:
        if writable and self.read_only:
            raise VesselReadOnlyError("vessel is mounted read-only")
        self._validate_file_identity()
        if self.read_only or not writable:
            uri = f"{self.path.as_uri()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=10.0, isolation_level=None)
            self._configure_connection(connection, writable=False)
            return connection
        connection = sqlite3.connect(str(self.path), timeout=10.0, isolation_level=None)
        self._configure_connection(connection, writable=True)
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect(writable=True)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def reader(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect(writable=False)
        try:
            yield connection
        finally:
            connection.close()

    def validate(self) -> Dict[str, Any]:
        with self.reader() as connection:
            application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if application_id != APPLICATION_ID:
                raise VesselFormatError("file is not a PubPartner vessel")
            if user_version <= 0 or user_version > CURRENT_SCHEMA_VERSION:
                raise VesselFormatError(
                    f"unsupported vessel schema {user_version}; runtime supports {CURRENT_SCHEMA_VERSION}"
                )
            row = connection.execute("SELECT * FROM vessel_manifest WHERE singleton = 1").fetchone()
            if row is None:
                raise VesselFormatError("vessel manifest is missing")
            if int(row["schema_version"]) != user_version:
                raise VesselFormatError("manifest and SQLite schema versions disagree")
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            foreign_keys = list(connection.execute("PRAGMA foreign_key_check").fetchall())
            if integrity != "ok" or foreign_keys:
                raise VesselIntegrityError(
                    f"vessel integrity failed: integrity={integrity!r}, foreign_key_errors={len(foreign_keys)}"
                )
            audit = self._verify_audit_tx(connection)
            if not audit["ok"]:
                raise VesselIntegrityError(str(audit["error"]))
            state_integrity = self._verify_records_tx(connection)
            if not state_integrity["ok"]:
                raise VesselIntegrityError(str(state_integrity["error"]))
            return {
                "ok": True,
                "vessel_id": str(row["vessel_id"]),
                "display_name": str(row["display_name"]),
                "status": str(row["status"]),
                "schema_version": user_version,
                "integrity": integrity,
                "audit": audit,
                "state_integrity": state_integrity,
                "size_bytes": self.path.stat().st_size,
                "read_only": self.read_only,
            }

    def manifest(self) -> Dict[str, Any]:
        with self.reader() as connection:
            row = connection.execute("SELECT * FROM vessel_manifest WHERE singleton = 1").fetchone()
            if row is None:
                raise VesselFormatError("vessel manifest is missing")
            return {
                "vessel_id": row["vessel_id"],
                "schema_version": int(row["schema_version"]),
                "display_name": row["display_name"],
                "status": row["status"],
                "created_at": float(row["created_at"]),
                "updated_at": float(row["updated_at"]),
                "metadata": _decode(row["metadata_json"], {}),
            }

    def set_identity(self, key: str, value: Any, *, authority: str = "owner") -> Dict[str, Any]:
        key = _bounded_text(key, "identity key", maximum=120)
        authority = _bounded_text(authority, "authority", maximum=80)
        now = _now()
        encoded = _json(value)
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT version, created_at FROM identity_records WHERE key = ?", (key,)
            ).fetchone()
            version = int(existing["version"]) + 1 if existing else 1
            created_at = float(existing["created_at"]) if existing else now
            connection.execute(
                """
                INSERT INTO identity_records
                    (key, value_json, authority, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    authority = excluded.authority,
                    version = excluded.version,
                    updated_at = excluded.updated_at
                """,
                (key, encoded, authority, version, created_at, now),
            )
            connection.execute(
                "UPDATE vessel_manifest SET updated_at = ? WHERE singleton = 1", (now,)
            )
            self._seal_record_tx(
                connection, table="identity_records", record_id=key
            )
            self._seal_record_tx(
                connection, table="vessel_manifest", record_id="1"
            )
            self._append_audit_tx(
                connection,
                event_type="identity.updated",
                record_id=key,
                payload={"key": key, "value_hash": hashlib.sha256(encoded.encode()).hexdigest(),
                         "authority": authority, "version": version},
            )
        return {"key": key, "value": value, "authority": authority, "version": version,
                "created_at": created_at, "updated_at": now}

    def identity(self) -> Dict[str, Any]:
        with self.reader() as connection:
            rows = connection.execute(
                "SELECT key, value_json, authority, version, created_at, updated_at "
                "FROM identity_records ORDER BY key"
            ).fetchall()
        return {
            str(row["key"]): {
                "value": _decode(row["value_json"], None),
                "authority": row["authority"],
                "version": int(row["version"]),
                "created_at": float(row["created_at"]),
                "updated_at": float(row["updated_at"]),
            }
            for row in rows
        }

    def identity_values(self) -> Dict[str, Any]:
        return {key: row["value"] for key, row in self.identity().items()}

    def upsert_entity(
        self,
        entity_id: str,
        *,
        entity_type: str,
        display_name: str,
        aliases: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entity_id = _bounded_text(entity_id, "entity_id", maximum=160)
        entity_type = _bounded_text(entity_type, "entity_type", maximum=60)
        display_name = _bounded_text(display_name, "display_name", maximum=160)
        aliases = [str(value)[:160] for value in (aliases or []) if str(value).strip()][:40]
        now = _now()
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT created_at FROM entities WHERE entity_id = ?", (entity_id,)
            ).fetchone()
            created_at = float(existing["created_at"]) if existing else now
            connection.execute(
                """
                INSERT INTO entities
                    (entity_id, entity_type, display_name, aliases_json, metadata_json,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    display_name = excluded.display_name,
                    aliases_json = excluded.aliases_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (entity_id, entity_type, display_name, _json(aliases),
                _json(dict(metadata or {})), created_at, now),
            )
            self._seal_record_tx(connection, table="entities", record_id=entity_id)
            self._append_audit_tx(
                connection,
                event_type="entity.upserted",
                record_id=entity_id,
                payload={"entity_type": entity_type, "display_name": display_name},
            )
        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "display_name": display_name,
            "aliases": aliases,
            "metadata": dict(metadata or {}),
            "created_at": created_at,
            "updated_at": now,
        }

    def upsert_relationship(
        self,
        entity_id: str,
        *,
        relationship_type: str = "primary_user",
        status: str = "active",
        visibility: str = "private_relationship",
        state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entity_id = _bounded_text(entity_id, "entity_id", maximum=160)
        relationship_type = _bounded_text(relationship_type, "relationship_type", maximum=80)
        relationship_id = f"relationship:{entity_id}:{relationship_type}"
        now = _now()
        with self.transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM entities WHERE entity_id = ?", (entity_id,)
            ).fetchone() is None:
                raise VesselConflictError(f"unknown relationship entity: {entity_id}")
            existing = connection.execute(
                "SELECT created_at FROM relationships WHERE relationship_id = ?",
                (relationship_id,),
            ).fetchone()
            created_at = float(existing["created_at"]) if existing else now
            connection.execute(
                """
                INSERT INTO relationships
                    (relationship_id, entity_id, relationship_type, status, visibility,
                     state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(relationship_id) DO UPDATE SET
                    status = excluded.status,
                    visibility = excluded.visibility,
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (relationship_id, entity_id, relationship_type, str(status)[:40],
                 str(visibility)[:60], _json(dict(state or {})), created_at, now),
            )
            self._seal_record_tx(
                connection, table="relationships", record_id=relationship_id
            )
            self._append_audit_tx(
                connection,
                event_type="relationship.upserted",
                record_id=relationship_id,
                payload={"entity_id": entity_id, "type": relationship_type,
                         "status": status, "visibility": visibility},
            )
        return {
            "relationship_id": relationship_id,
            "entity_id": entity_id,
            "relationship_type": relationship_type,
            "status": status,
            "visibility": visibility,
            "state": dict(state or {}),
            "created_at": created_at,
            "updated_at": now,
        }

    def relationship(self, entity_id: str) -> Dict[str, Any]:
        with self.reader() as connection:
            entity = connection.execute(
                "SELECT * FROM entities WHERE entity_id = ?", (entity_id,)
            ).fetchone()
            relationships = connection.execute(
                "SELECT * FROM relationships WHERE entity_id = ? ORDER BY updated_at DESC",
                (entity_id,),
            ).fetchall()
        if entity is None:
            return {}
        return {
            "entity": {
                "entity_id": entity["entity_id"],
                "entity_type": entity["entity_type"],
                "display_name": entity["display_name"],
                "aliases": _decode(entity["aliases_json"], []),
                "metadata": _decode(entity["metadata_json"], {}),
            },
            "relationships": [
                {
                    "relationship_id": row["relationship_id"],
                    "relationship_type": row["relationship_type"],
                    "status": row["status"],
                    "visibility": row["visibility"],
                    "state": _decode(row["state_json"], {}),
                    "created_at": float(row["created_at"]),
                    "updated_at": float(row["updated_at"]),
                }
                for row in relationships
            ],
        }

    def put_asset(
        self,
        content: bytes,
        *,
        media_type: str,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(content, (bytes, bytearray, memoryview)):
            raise TypeError("asset content must be bytes")
        raw = bytes(content)
        if len(raw) > MAX_ASSET_BYTES:
            raise ValueError(f"asset exceeds {MAX_ASSET_BYTES} bytes")
        media_type = _bounded_text(media_type, "media_type", maximum=160)
        digest = hashlib.sha256(raw).hexdigest()
        created_at = _now()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO assets
                    (sha256, media_type, byte_length, content, provenance_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (digest, media_type, len(raw), raw, _json(dict(provenance or {})), created_at),
            )
            self._seal_record_tx(connection, table="assets", record_id=digest)
            self._append_audit_tx(
                connection,
                event_type="asset.stored",
                record_id=digest,
                payload={"media_type": media_type, "byte_length": len(raw)},
            )
        return {"sha256": digest, "media_type": media_type, "byte_length": len(raw)}

    def get_asset(self, sha256: str) -> Dict[str, Any]:
        digest = _bounded_text(sha256, "sha256", maximum=64)
        with self.reader() as connection:
            row = connection.execute("SELECT * FROM assets WHERE sha256 = ?", (digest,)).fetchone()
        if row is None:
            raise FileNotFoundError(digest)
        content = bytes(row["content"])
        if hashlib.sha256(content).hexdigest() != digest or len(content) != int(row["byte_length"]):
            raise VesselIntegrityError(f"asset integrity failed: {digest}")
        return {
            "sha256": digest,
            "media_type": row["media_type"],
            "byte_length": int(row["byte_length"]),
            "content": content,
            "provenance": _decode(row["provenance_json"], {}),
            "created_at": float(row["created_at"]),
        }

    def bind_asset(
        self,
        role: str,
        asset_sha256: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        role = _bounded_text(role, "asset role", maximum=160)
        asset_sha256 = _bounded_text(asset_sha256, "asset_sha256", maximum=64)
        now = _now()
        binding_id = f"binding:{role}"
        with self.transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM assets WHERE sha256 = ?", (asset_sha256,)
            ).fetchone() is None:
                raise VesselConflictError(f"unknown asset: {asset_sha256}")
            existing = connection.execute(
                "SELECT created_at FROM asset_bindings WHERE role = ?", (role,)
            ).fetchone()
            created_at = float(existing["created_at"]) if existing else now
            connection.execute(
                """
                INSERT INTO asset_bindings
                    (binding_id, role, asset_sha256, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(role) DO UPDATE SET
                    asset_sha256 = excluded.asset_sha256,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (binding_id, role, asset_sha256, _json(dict(metadata or {})),
                 created_at, now),
            )
            self._seal_record_tx(
                connection, table="asset_bindings", record_id=binding_id
            )
            self._append_audit_tx(
                connection,
                event_type="asset.bound",
                record_id=binding_id,
                payload={"role": role, "asset_sha256": asset_sha256},
            )
        return {"binding_id": binding_id, "role": role, "asset_sha256": asset_sha256,
                "metadata": dict(metadata or {})}

    def _append_audit_tx(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        record_id: str,
        payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        row = connection.execute(
            "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        prev_hash = str(row["event_hash"]) if row else "GENESIS"
        created_at = _now()
        payload_hash = _canonical_hash(dict(payload))
        body = {
            "event_type": str(event_type),
            "record_id": str(record_id),
            "payload_hash": payload_hash,
            "prev_hash": prev_hash,
            "created_at": created_at,
        }
        event_hash = _canonical_hash(body)
        cursor = connection.execute(
            """
            INSERT INTO audit_events
                (event_type, record_id, payload_hash, prev_hash, event_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (body["event_type"], body["record_id"], payload_hash, prev_hash,
             event_hash, created_at),
        )
        return {"sequence": int(cursor.lastrowid), **body, "event_hash": event_hash}

    def append_audit(
        self,
        *,
        event_type: str,
        record_id: str,
        payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        with self.transaction() as connection:
            return self._append_audit_tx(
                connection, event_type=event_type, record_id=record_id, payload=payload
            )

    @staticmethod
    def _verify_audit_tx(connection: sqlite3.Connection) -> Dict[str, Any]:
        prev_hash = "GENESIS"
        count = 0
        for row in connection.execute("SELECT * FROM audit_events ORDER BY sequence"):
            if str(row["prev_hash"]) != prev_hash:
                return {"ok": False, "entries": count,
                        "error": f"audit chain break at sequence {row['sequence']}"}
            body = {
                "event_type": str(row["event_type"]),
                "record_id": str(row["record_id"]),
                "payload_hash": str(row["payload_hash"]),
                "prev_hash": str(row["prev_hash"]),
                "created_at": float(row["created_at"]),
            }
            expected = _canonical_hash(body)
            if str(row["event_hash"]) != expected:
                return {"ok": False, "entries": count,
                        "error": f"audit hash mismatch at sequence {row['sequence']}"}
            prev_hash = expected
            count += 1
        return {"ok": True, "entries": count, "last_hash": prev_hash}

    def verify_audit(self) -> Dict[str, Any]:
        with self.reader() as connection:
            return self._verify_audit_tx(connection)

    @staticmethod
    def _record_hash_tx(
        connection: sqlite3.Connection, *, table: str, record_id: str
    ) -> str:
        key_columns = _RECORD_TABLES.get(table)
        if key_columns is None or len(key_columns) != 1:
            raise VesselFormatError(f"unsupported integrity table: {table}")
        key = key_columns[0]
        row = connection.execute(
            f'SELECT * FROM "{table}" WHERE "{key}" = ?', (record_id,)
        ).fetchone()
        if row is None:
            raise VesselIntegrityError(f"cannot seal missing {table} record: {record_id}")
        values: List[Any] = []
        for name in row.keys():
            value = row[name]
            if isinstance(value, (bytes, bytearray, memoryview)):
                raw = bytes(value)
                value = {
                    "blob_sha256": hashlib.sha256(raw).hexdigest(),
                    "byte_length": len(raw),
                }
            values.append([name, value])
        encoded = json.dumps(
            values,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _seal_record_tx(
        self, connection: sqlite3.Connection, *, table: str, record_id: str
    ) -> str:
        record_hash = self._record_hash_tx(
            connection, table=table, record_id=str(record_id)
        )
        connection.execute(
            """
            INSERT INTO record_integrity
                (table_name, record_id, record_hash, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(table_name, record_id) DO UPDATE SET
                record_hash = excluded.record_hash,
                updated_at = excluded.updated_at
            """,
            (table, str(record_id), record_hash, _now()),
        )
        return record_hash

    def _verify_records_tx(self, connection: sqlite3.Connection) -> Dict[str, Any]:
        seals = {
            (str(row["table_name"]), str(row["record_id"])): str(row["record_hash"])
            for row in connection.execute(
                "SELECT table_name, record_id, record_hash FROM record_integrity"
            )
        }
        expected_keys: set[tuple[str, str]] = set()
        root = hashlib.sha256()
        verified = 0
        for table, key_columns in _RECORD_TABLES.items():
            key = key_columns[0]
            for row in connection.execute(
                f'SELECT "{key}" AS record_id FROM "{table}" ORDER BY "{key}"'
            ):
                record_id = str(row["record_id"])
                identity = (table, record_id)
                expected_keys.add(identity)
                expected = seals.get(identity)
                if expected is None:
                    return {
                        "ok": False,
                        "error": f"integrity seal is missing for {table}:{record_id}",
                    }
                actual = self._record_hash_tx(
                    connection, table=table, record_id=record_id
                )
                if not hmac.compare_digest(expected, actual):
                    return {
                        "ok": False,
                        "error": f"integrity seal mismatch for {table}:{record_id}",
                        "expected": expected,
                        "actual": actual,
                    }
                root.update(
                    f"{table}\0{record_id}\0{actual}\n".encode("utf-8")
                )
                verified += 1
        extras = sorted(set(seals) - expected_keys)
        if extras:
            table, record_id = extras[0]
            return {
                "ok": False,
                "error": f"orphan integrity seal for {table}:{record_id}",
            }
        return {
            "ok": True,
            "state_hash": root.hexdigest(),
            "verified_records": verified,
        }

    def backup_to(self, destination: Path | str) -> Dict[str, Any]:
        """Create and validate a transaction-consistent portable vessel copy."""
        target = Path(destination).expanduser().absolute()
        if target.exists() or target.is_symlink():
            raise VesselConflictError(f"backup destination already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.parent.is_symlink():
            raise VesselFormatError("backup parent directory cannot be a symlink")
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        os.close(descriptor)
        destination_connection: Optional[sqlite3.Connection] = None
        try:
            with self.reader() as source:
                destination_connection = sqlite3.connect(
                    str(temporary), timeout=10.0, isolation_level=None
                )
                self._configure_connection(destination_connection, writable=True)
                source.backup(destination_connection)
                destination_connection.close()
                destination_connection = None
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            parent_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            validation = VesselStore.open(target, read_only=True).validate()
            return {
                "ok": True,
                "path": str(target),
                "vessel_id": validation["vessel_id"],
                "state_hash": validation["state_integrity"]["state_hash"],
                "size_bytes": validation["size_bytes"],
            }
        except Exception:
            if destination_connection is not None:
                destination_connection.close()
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            raise


__all__ = ["VesselStore", "MAX_ASSET_BYTES"]
