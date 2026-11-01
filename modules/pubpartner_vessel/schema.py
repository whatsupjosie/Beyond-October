"""SQLite schema and migrations for `.pubpartner` vessels."""

from __future__ import annotations

CURRENT_SCHEMA_VERSION = 1
APPLICATION_ID = 0x50505631  # ASCII-ish "PPV1"


SCHEMA_V1 = """
CREATE TABLE vessel_manifest (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    vessel_id TEXT NOT NULL UNIQUE,
    schema_version INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE TABLE identity_records (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    authority TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    aliases_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE relationships (
    relationship_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE RESTRICT,
    relationship_type TEXT NOT NULL,
    status TEXT NOT NULL,
    visibility TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(entity_id, relationship_type)
);

CREATE TABLE memory_events (
    event_id TEXT PRIMARY KEY,
    observed_at REAL NOT NULL,
    actor_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    room_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    literalness TEXT NOT NULL,
    visibility TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE INDEX idx_memory_events_subject_time
    ON memory_events(subject_id, observed_at DESC);
CREATE INDEX idx_memory_events_room_time
    ON memory_events(room_id, observed_at DESC);
CREATE INDEX idx_memory_events_session_time
    ON memory_events(session_id, observed_at DESC);

CREATE TABLE memory_claims (
    claim_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_json TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    scope TEXT NOT NULL,
    salience REAL NOT NULL CHECK (salience >= 0 AND salience <= 1),
    proactive_use INTEGER NOT NULL CHECK (proactive_use IN (0, 1)),
    visibility TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_supported_at REAL,
    expires_at REAL,
    version INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    UNIQUE(subject_id, predicate, normalized_text, scope)
);

CREATE INDEX idx_memory_claims_subject_status
    ON memory_claims(subject_id, status, updated_at DESC);

CREATE TABLE memory_evidence (
    evidence_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES memory_claims(claim_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES memory_events(event_id) ON DELETE RESTRICT,
    polarity TEXT NOT NULL,
    independence_key TEXT NOT NULL,
    weight REAL NOT NULL CHECK (weight >= 0 AND weight <= 5),
    explicit_confirmation INTEGER NOT NULL CHECK (explicit_confirmation IN (0, 1)),
    observed_at REAL NOT NULL,
    source_excerpt TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    UNIQUE(claim_id, polarity, independence_key)
);

CREATE INDEX idx_memory_evidence_claim
    ON memory_evidence(claim_id, polarity, observed_at DESC);

CREATE TABLE memory_corrections (
    correction_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES memory_claims(claim_id) ON DELETE RESTRICT,
    action TEXT NOT NULL,
    replacement_text TEXT NOT NULL,
    reason TEXT NOT NULL,
    event_id TEXT REFERENCES memory_events(event_id) ON DELETE RESTRICT,
    created_at REAL NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE TABLE assets (
    sha256 TEXT PRIMARY KEY,
    media_type TEXT NOT NULL,
    byte_length INTEGER NOT NULL CHECK (byte_length >= 0),
    content BLOB NOT NULL,
    provenance_json TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE asset_bindings (
    binding_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    asset_sha256 TEXT NOT NULL REFERENCES assets(sha256) ON DELETE RESTRICT,
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(role)
);

CREATE TABLE audit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE record_integrity (
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (table_name, record_id)
);
"""


MIGRATIONS = {
    1: SCHEMA_V1,
}
