"""Evidence-governed memory for PubPartner identity vessels."""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from .errors import VesselConflictError
from .models import (
    ClaimStatus,
    EvidencePolarity,
    Literalness,
    MemoryClaim,
    MemoryEvent,
    Visibility,
)
from .store import VesselStore, _decode, _json

MAX_EVENT_CONTENT = 32_768

_LITERALNESS_WEIGHT = {
    Literalness.LITERAL.value: 1.0,
    Literalness.UNCERTAIN.value: 0.35,
    Literalness.QUOTED.value: 0.25,
    Literalness.HYPOTHETICAL.value: 0.20,
    Literalness.JOKING.value: 0.10,
    Literalness.SARCASTIC.value: 0.10,
    Literalness.FICTIONAL.value: 0.05,
}

_ALWAYS_RELEVANT_TYPES = {"boundary", "identity", "workflow", "accessibility"}
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "he", "her", "hers", "him", "his", "i", "in", "is", "it",
    "its", "me", "my", "of", "on", "or", "our", "she", "that", "the", "their",
    "them", "they", "this", "to", "was", "we", "were", "with", "you", "your",
}


def _now() -> float:
    return time.time()


def _tokens(value: Any) -> Set[str]:
    return {
        token for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]{1,}", str(value or "").casefold())
        if token not in _STOP_WORDS
    }


def _normalize_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().rstrip(" .")
    if not text:
        raise ValueError("claim text is required")
    return text


def _row_event(row: sqlite3.Row) -> MemoryEvent:
    return MemoryEvent(
        event_id=str(row["event_id"]),
        observed_at=float(row["observed_at"]),
        actor_id=str(row["actor_id"]),
        subject_id=str(row["subject_id"]),
        room_id=str(row["room_id"]),
        session_id=str(row["session_id"]),
        event_type=str(row["event_type"]),
        content=str(row["content"]),
        source_kind=str(row["source_kind"]),
        literalness=str(row["literalness"]),
        visibility=str(row["visibility"]),
        sensitivity=str(row["sensitivity"]),
        source_ref=str(row["source_ref"]),
        source_hash=str(row["source_hash"]),
        metadata=_decode(row["metadata_json"], {}),
    )


def _row_claim(row: sqlite3.Row, *, support_count: int = 0, contradiction_count: int = 0) -> MemoryClaim:
    return MemoryClaim(
        claim_id=str(row["claim_id"]),
        subject_id=str(row["subject_id"]),
        predicate=str(row["predicate"]),
        value=_decode(row["object_json"], None),
        normalized_text=str(row["normalized_text"]),
        claim_type=str(row["claim_type"]),
        status=str(row["status"]),
        confidence=float(row["confidence"]),
        scope=str(row["scope"]),
        salience=float(row["salience"]),
        proactive_use=bool(row["proactive_use"]),
        visibility=str(row["visibility"]),
        sensitivity=str(row["sensitivity"]),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        last_supported_at=float(row["last_supported_at"]) if row["last_supported_at"] is not None else None,
        expires_at=float(row["expires_at"]) if row["expires_at"] is not None else None,
        version=int(row["version"]),
        support_count=support_count,
        contradiction_count=contradiction_count,
        metadata=_decode(row["metadata_json"], {}),
    )


class EvidenceMemory:
    """Memory ledger that keeps observations separate from learned claims."""

    def __init__(self, store: VesselStore) -> None:
        self.store = store
        from .search import MemorySearch
        self.search = MemorySearch(store)

    def record_event(
        self,
        *,
        actor_id: str,
        subject_id: str,
        event_type: str,
        content: str,
        source_kind: str = "conversation",
        literalness: str = Literalness.UNCERTAIN.value,
        visibility: str = Visibility.PRIVATE_RELATIONSHIP.value,
        sensitivity: str = "ordinary",
        source_ref: str = "",
        source_hash: str = "",
        room_id: str = "",
        session_id: str = "",
        observed_at: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEvent:
        actor_id = str(actor_id or "").strip()[:160]
        subject_id = str(subject_id or "").strip()[:160]
        event_type = str(event_type or "").strip()[:100]
        content = str(content or "")
        if not actor_id or not subject_id or not event_type or not content.strip():
            raise ValueError("actor_id, subject_id, event_type, and content are required")
        if len(content) > MAX_EVENT_CONTENT:
            raise ValueError(f"event content exceeds {MAX_EVENT_CONTENT} characters")
        if literalness not in {value.value for value in Literalness}:
            raise ValueError(f"unsupported literalness: {literalness}")
        if visibility not in {value.value for value in Visibility}:
            raise ValueError(f"unsupported visibility: {visibility}")
        event_id = f"event_{uuid.uuid4().hex}"
        observed = float(observed_at if observed_at is not None else _now())
        source_hash = str(source_hash or hashlib.sha256(content.encode("utf-8")).hexdigest())
        source_ref = str(source_ref or event_id)[:300]
        event = MemoryEvent(
            event_id=event_id,
            observed_at=observed,
            actor_id=actor_id,
            subject_id=subject_id,
            room_id=str(room_id or "")[:160],
            session_id=str(session_id or "")[:160],
            event_type=event_type,
            content=content,
            source_kind=str(source_kind or "conversation")[:100],
            literalness=literalness,
            visibility=visibility,
            sensitivity=str(sensitivity or "ordinary")[:80],
            source_ref=source_ref,
            source_hash=source_hash[:128],
            metadata=dict(metadata or {}),
        )
        with self.store.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM memory_events WHERE subject_id=? AND actor_id=? "
                "AND source_kind=? AND source_ref=? AND source_hash=? "
                "AND event_type=? AND room_id=? AND session_id=? AND visibility=? AND content=? "
                "AND literalness=? AND sensitivity=?",
                (subject_id, actor_id, source_kind, source_ref, source_hash,
                 event_type, event.room_id, event.session_id, visibility, content,
                 literalness, event.sensitivity),
            ).fetchone()
            if existing is not None:
                return _row_event(existing)
            connection.execute(
                """
                INSERT INTO memory_events
                    (event_id, observed_at, actor_id, subject_id, room_id, session_id,
                     event_type, content, source_kind, literalness, visibility,
                     sensitivity, source_ref, source_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id, event.observed_at, event.actor_id, event.subject_id,
                    event.room_id, event.session_id, event.event_type, event.content,
                    event.source_kind, event.literalness, event.visibility,
                    event.sensitivity, event.source_ref, event.source_hash,
                    _json(event.metadata),
                ),
            )
            self.store._seal_record_tx(
                connection, table="memory_events", record_id=event.event_id
            )
            self.store._append_audit_tx(
                connection,
                event_type="memory.event.recorded",
                record_id=event.event_id,
                payload={
                    "actor_id": actor_id,
                    "subject_id": subject_id,
                    "event_type": event_type,
                    "source_hash": event.source_hash,
                    "literalness": literalness,
                    "visibility": visibility,
                },
            )
        return event

    def propose_claim(
        self,
        *,
        event_id: str,
        subject_id: str,
        predicate: str,
        value: Any,
        normalized_text: Optional[str] = None,
        claim_type: str = "fact",
        scope: str = "global",
        salience: float = 0.5,
        proactive_use: bool = False,
        visibility: str = Visibility.PRIVATE_RELATIONSHIP.value,
        sensitivity: str = "ordinary",
        evidence_polarity: str = EvidencePolarity.SUPPORT.value,
        evidence_weight: float = 1.0,
        independence_key: str = "",
        explicit_confirmation: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryClaim:
        subject_id = str(subject_id or "").strip()[:160]
        predicate = str(predicate or "").strip()[:120]
        if not subject_id or not predicate:
            raise ValueError("subject_id and predicate are required")
        text = _normalize_text(normalized_text if normalized_text is not None else value)
        salience = max(0.0, min(1.0, float(salience)))
        if evidence_polarity not in {value.value for value in EvidencePolarity}:
            raise ValueError(f"unsupported evidence polarity: {evidence_polarity}")
        if visibility not in {value.value for value in Visibility}:
            raise ValueError(f"unsupported visibility: {visibility}")
        now = _now()
        with self.store.transaction() as connection:
            event = connection.execute(
                "SELECT * FROM memory_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if event is None:
                raise VesselConflictError(f"unknown memory event: {event_id}")
            if str(event["subject_id"]) != subject_id:
                raise VesselConflictError("claim subject does not match evidence subject")
            row = connection.execute(
                """
                SELECT * FROM memory_claims
                WHERE subject_id = ? AND predicate = ? AND normalized_text = ? AND scope = ?
                """,
                (subject_id, predicate, text, str(scope or "global")[:160]),
            ).fetchone()
            if row is None:
                claim_id = f"claim_{uuid.uuid4().hex}"
                connection.execute(
                    """
                    INSERT INTO memory_claims
                        (claim_id, subject_id, predicate, object_json, normalized_text,
                         claim_type, status, confidence, scope, salience, proactive_use,
                         visibility, sensitivity, created_at, updated_at,
                         last_supported_at, expires_at, version, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 1, ?)
                    """,
                    (
                        claim_id, subject_id, predicate, _json(value), text,
                        str(claim_type or "fact")[:80], ClaimStatus.TENTATIVE.value,
                        0.0, str(scope or "global")[:160], salience,
                        1 if proactive_use else 0, visibility,
                        str(sensitivity or "ordinary")[:80], now, now,
                        now if evidence_polarity == EvidencePolarity.SUPPORT.value else None,
                        _json(dict(metadata or {})),
                    ),
                )
            else:
                claim_id = str(row["claim_id"])
                if str(row["status"]) == ClaimStatus.REJECTED.value:
                    raise VesselConflictError("rejected claim cannot be silently reactivated")
            self._add_evidence_tx(
                connection,
                claim_id=claim_id,
                event=event,
                polarity=evidence_polarity,
                weight=evidence_weight,
                independence_key=independence_key,
                explicit_confirmation=explicit_confirmation,
                metadata=metadata,
            )
            updated = self._recalculate_claim_tx(connection, claim_id)
            self.store._append_audit_tx(
                connection,
                event_type="memory.claim.proposed",
                record_id=claim_id,
                payload={
                    "event_id": event_id,
                    "subject_id": subject_id,
                    "predicate": predicate,
                    "text_hash": hashlib.sha256(text.encode()).hexdigest(),
                    "status": updated.status,
                    "confidence": updated.confidence,
                },
            )
            return updated

    def add_evidence(
        self,
        claim_id: str,
        *,
        event_id: str,
        polarity: str = EvidencePolarity.SUPPORT.value,
        weight: float = 1.0,
        independence_key: str = "",
        explicit_confirmation: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryClaim:
        with self.store.transaction() as connection:
            claim = connection.execute(
                "SELECT * FROM memory_claims WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            event = connection.execute(
                "SELECT * FROM memory_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if claim is None or event is None:
                raise VesselConflictError("claim or evidence event does not exist")
            if str(claim["subject_id"]) != str(event["subject_id"]):
                raise VesselConflictError("claim and evidence subjects differ")
            if str(claim["status"]) == ClaimStatus.REJECTED.value:
                raise VesselConflictError("rejected claim cannot be silently reactivated")
            inserted = self._add_evidence_tx(
                connection,
                claim_id=claim_id,
                event=event,
                polarity=polarity,
                weight=weight,
                independence_key=independence_key,
                explicit_confirmation=explicit_confirmation,
                metadata=metadata,
            )
            updated = self._recalculate_claim_tx(connection, claim_id)
            self.store._append_audit_tx(
                connection,
                event_type="memory.evidence.added" if inserted else "memory.evidence.duplicate",
                record_id=claim_id,
                payload={"event_id": event_id, "polarity": polarity,
                         "independence_key": independence_key or event["source_ref"],
                         "inserted": inserted, "status": updated.status},
            )
            return updated

    def _add_evidence_tx(
        self,
        connection: sqlite3.Connection,
        *,
        claim_id: str,
        event: sqlite3.Row,
        polarity: str,
        weight: float,
        independence_key: str,
        explicit_confirmation: bool,
        metadata: Optional[Dict[str, Any]],
    ) -> bool:
        if polarity not in {value.value for value in EvidencePolarity}:
            raise ValueError(f"unsupported evidence polarity: {polarity}")
        key = str(independence_key or event["source_ref"] or event["event_id"])[:300]
        literal_multiplier = _LITERALNESS_WEIGHT.get(str(event["literalness"]), 0.20)
        effective_weight = max(0.0, min(5.0, float(weight))) * literal_multiplier
        if explicit_confirmation:
            effective_weight = max(effective_weight, 3.0)
        evidence_id = f"evidence_{uuid.uuid4().hex}"
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO memory_evidence
                (evidence_id, claim_id, event_id, polarity, independence_key,
                 weight, explicit_confirmation, observed_at, source_excerpt,
                 metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id, claim_id, event["event_id"], polarity,
                key, effective_weight, 1 if explicit_confirmation else 0,
                float(event["observed_at"]), str(event["content"])[:500],
                _json(dict(metadata or {})),
            ),
        )
        inserted = cursor.rowcount > 0
        if inserted:
            self.store._seal_record_tx(
                connection, table="memory_evidence", record_id=evidence_id
            )
        return inserted

    def _recalculate_claim_tx(
        self, connection: sqlite3.Connection, claim_id: str
    ) -> MemoryClaim:
        claim = connection.execute(
            "SELECT * FROM memory_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if claim is None:
            raise VesselConflictError(f"unknown claim: {claim_id}")
        evidence = connection.execute(
            "SELECT * FROM memory_evidence WHERE claim_id = ? ORDER BY observed_at",
            (claim_id,),
        ).fetchall()
        support = sum(float(row["weight"]) for row in evidence if row["polarity"] == "support")
        contradiction = sum(
            float(row["weight"]) for row in evidence if row["polarity"] == "contradict"
        )
        support_rows = [row for row in evidence if row["polarity"] == "support" and float(row["weight"]) >= 0.5]
        contradiction_rows = [row for row in evidence if row["polarity"] == "contradict" and float(row["weight"]) >= 0.5]
        explicit = any(bool(row["explicit_confirmation"]) for row in support_rows)
        confidence = support / (support + contradiction + 1.0)
        confidence = max(0.0, min(1.0, confidence))
        current_status = str(claim["status"])
        if current_status in {ClaimStatus.REJECTED.value, ClaimStatus.SUPERSEDED.value}:
            status = current_status
        elif explicit:
            status = ClaimStatus.CONFIRMED.value
            confidence = max(confidence, 0.95)
        elif len(support_rows) >= 3 and confidence >= 0.72 and support > contradiction:
            status = ClaimStatus.CONFIRMED.value
        elif len(support_rows) >= 2 and confidence >= 0.60 and support > contradiction:
            status = ClaimStatus.CORROBORATED.value
        else:
            status = ClaimStatus.TENTATIVE.value
        now = _now()
        last_supported = max(
            (float(row["observed_at"]) for row in evidence if row["polarity"] == "support"),
            default=None,
        )
        connection.execute(
            """
            UPDATE memory_claims
            SET status = ?, confidence = ?, updated_at = ?, last_supported_at = ?,
                version = version + 1
            WHERE claim_id = ?
            """,
            (status, confidence, now, last_supported, claim_id),
        )
        self.store._seal_record_tx(
            connection, table="memory_claims", record_id=claim_id
        )
        updated = connection.execute(
            "SELECT * FROM memory_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        return _row_claim(
            updated,
            support_count=len(support_rows),
            contradiction_count=len(contradiction_rows),
        )

    def correct_claim(
        self,
        claim_id: str,
        *,
        action: str,
        reason: str,
        replacement_text: str = "",
        event_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryClaim:
        action = str(action or "").strip().lower()
        if action not in {"reject", "confirm", "prohibit_use", "allow_use", "replace", "narrow"}:
            raise ValueError(f"unsupported correction action: {action}")
        reason = str(reason or "").strip()
        if not reason:
            raise ValueError("correction reason is required")
        now = _now()
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM memory_claims WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            if row is None:
                raise FileNotFoundError(claim_id)
            status = str(row["status"])
            confidence = float(row["confidence"])
            proactive = int(row["proactive_use"])
            normalized_text = str(row["normalized_text"])
            object_value = _decode(row["object_json"], None)
            metadata_value = _decode(row["metadata_json"], {})
            if event_id is not None:
                correction_event = connection.execute(
                    "SELECT subject_id FROM memory_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                if correction_event is None:
                    raise VesselConflictError(
                        "correction event does not exist"
                    )
                if str(correction_event["subject_id"]) != str(row["subject_id"]):
                    raise VesselConflictError(
                        "correction event subject does not match claim subject"
                    )
            if action == "reject":
                status = ClaimStatus.REJECTED.value
                confidence = 0.0
                proactive = 0
            elif action == "confirm":
                status = ClaimStatus.CONFIRMED.value
                confidence = 1.0
            elif action == "prohibit_use":
                proactive = 0
            elif action == "allow_use":
                if status == ClaimStatus.REJECTED.value:
                    raise VesselConflictError("rejected claim must be replaced or explicitly confirmed")
                proactive = 1
            elif action in {"replace", "narrow"}:
                normalized_text = _normalize_text(replacement_text)
                collision = connection.execute(
                    """
                    SELECT claim_id FROM memory_claims
                    WHERE subject_id = ? AND predicate = ? AND normalized_text = ?
                      AND scope = ? AND claim_id <> ?
                    """,
                    (
                        row["subject_id"],
                        row["predicate"],
                        normalized_text,
                        row["scope"],
                        claim_id,
                    ),
                ).fetchone()
                if collision is not None:
                    raise VesselConflictError(
                        "replacement conflicts with an existing memory claim"
                    )
                object_value = normalized_text
                metadata_value = dict(metadata_value)
                metadata_value["corrected_from"] = str(row["normalized_text"])
                metadata_value["correction_kind"] = action
                status = ClaimStatus.CONFIRMED.value
                confidence = 1.0
            correction_id = f"correction_{uuid.uuid4().hex}"
            connection.execute(
                """
                INSERT INTO memory_corrections
                    (correction_id, claim_id, action, replacement_text, reason,
                     event_id, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    correction_id, claim_id, action, str(replacement_text or ""),
                    reason[:2_000], event_id, now, _json(dict(metadata or {})),
                ),
            )
            self.store._seal_record_tx(
                connection, table="memory_corrections", record_id=correction_id
            )
            connection.execute(
                """
                UPDATE memory_claims
                SET object_json = ?, normalized_text = ?, status = ?, confidence = ?,
                    proactive_use = ?, metadata_json = ?, updated_at = ?,
                    version = version + 1
                WHERE claim_id = ?
                """,
                (
                    _json(object_value), normalized_text, status, confidence,
                    proactive, _json(metadata_value), now, claim_id,
                ),
            )
            self.store._seal_record_tx(
                connection, table="memory_claims", record_id=claim_id
            )
            self.store._append_audit_tx(
                connection,
                event_type="memory.claim.corrected",
                record_id=claim_id,
                payload={"correction_id": correction_id, "action": action,
                         "reason_hash": hashlib.sha256(reason.encode()).hexdigest()},
            )
            updated = connection.execute(
                "SELECT * FROM memory_claims WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            counts = self._evidence_counts_tx(connection, claim_id)
            return _row_claim(updated, **counts)

    @staticmethod
    def _evidence_counts_tx(connection: sqlite3.Connection, claim_id: str) -> Dict[str, int]:
        rows = connection.execute(
            "SELECT polarity, COUNT(*) AS n FROM memory_evidence "
            "WHERE claim_id = ? AND weight >= 0.5 GROUP BY polarity",
            (claim_id,),
        ).fetchall()
        counts = {str(row["polarity"]): int(row["n"]) for row in rows}
        return {
            "support_count": counts.get("support", 0),
            "contradiction_count": counts.get("contradict", 0),
        }

    def claim(self, claim_id: str) -> MemoryClaim:
        with self.store.reader() as connection:
            row = connection.execute(
                "SELECT * FROM memory_claims WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            if row is None:
                raise FileNotFoundError(claim_id)
            counts = self._evidence_counts_tx(connection, claim_id)
            return _row_claim(row, **counts)

    def event(self, event_id: str) -> MemoryEvent:
        with self.store.reader() as connection:
            row = connection.execute(
                "SELECT * FROM memory_events WHERE event_id = ?", (event_id,)
            ).fetchone()
        if row is None:
            raise FileNotFoundError(event_id)
        return _row_event(row)

    def list_claims(
        self,
        *,
        subject_id: str,
        status: str = "all",
        limit: int = 200,
    ) -> List[MemoryClaim]:
        sql = "SELECT * FROM memory_claims WHERE subject_id = ?"
        params: List[Any] = [subject_id]
        if status != "all":
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(2_000, int(limit))))
        with self.store.reader() as connection:
            rows = connection.execute(sql, tuple(params)).fetchall()
            return [
                _row_claim(row, **self._evidence_counts_tx(connection, str(row["claim_id"])))
                for row in rows
            ]

    def retrieve_claims(
        self,
        *,
        subject_id: str,
        viewer_id: str,
        query: str,
        room_id: str = "",
        project_id: str = "",
        session_id: str = "",
        audience: str = "private",
        limit: Optional[int] = 10,
        include_nonproactive: bool = False,
    ) -> List[Dict[str, Any]]:
        if limit is not None and int(limit) <= 0:
            self.search.status['claims'] = {'status': 'not_requested', 'complete': False, 'selected': 0}
            return []
        now = _now()
        query_tokens = _tokens(query)
        with self.store.reader() as connection:
            rows = self.search.candidates(
                connection, kind="claims", subject_id=subject_id,
                tokens=query_tokens, always_types=_ALWAYS_RELEVANT_TYPES,
                viewer_id=viewer_id, audience=audience, room_id=room_id,
                project_id=project_id, session_id=session_id,
                include_nonproactive=include_nonproactive,
            )
            scored: List[Tuple[float, sqlite3.Row, Dict[str, int], float]] = []
            for row in rows:
                if row["status"] not in {ClaimStatus.CONFIRMED.value, ClaimStatus.CORROBORATED.value}:
                    continue
                if row["expires_at"] is not None and float(row["expires_at"]) <= now:
                    continue
                if not include_nonproactive and not bool(row["proactive_use"]):
                    continue
                if not self._visible(
                    visibility=str(row["visibility"]),
                    scope=str(row["scope"]),
                    subject_id=subject_id,
                    viewer_id=viewer_id,
                    room_id=room_id,
                    project_id=project_id,
                    session_id=session_id,
                    audience=audience,
                ):
                    continue
                claim_tokens = _tokens(row["normalized_text"]) | _tokens(row["predicate"])
                claim_type = str(row["claim_type"])
                always_relevant = claim_type in _ALWAYS_RELEVANT_TYPES and str(row["scope"]) == "global"
                overlap = len(query_tokens & claim_tokens)
                relevance = (
                    1.0 if always_relevant else
                    (overlap / max(1, min(len(query_tokens), len(claim_tokens)))) if overlap else 0.0
                )
                if relevance <= 0:
                    continue
                age_days = max(0.0, (now - float(row["updated_at"])) / 86_400.0)
                recency = math.exp(-age_days / 365.0)
                score = (
                    0.55 * relevance
                    + 0.25 * float(row["confidence"])
                    + 0.10 * float(row["salience"])
                    + 0.10 * recency
                )
                counts = self._evidence_counts_tx(connection, str(row["claim_id"]))
                scored.append((score, row, counts, relevance))
        scored.sort(key=lambda item: (-item[0], -float(item[1]["confidence"]), str(item[1]["claim_id"])))
        per_predicate: Dict[str, int] = defaultdict(int)
        selected: List[Dict[str, Any]] = []
        for score, row, counts, relevance in scored:
            predicate = str(row["predicate"])
            if per_predicate[predicate] >= 2:
                continue
            claim = _row_claim(row, **counts).to_dict()
            claim["retrieval_score"] = round(score, 6)
            claim["relevance"] = round(relevance, 6)
            selected.append(claim)
            per_predicate[predicate] += 1
            if len(selected) >= max(1, min(100, int(limit if limit is not None else 40))):
                break
        status = self.search.status["claims"]
        status["selected"] = len(selected)
        if len(selected) < len(scored):
            status.update(status="bounded", complete=False)
        return selected

    def retrieve_events(
        self,
        *,
        subject_id: str,
        viewer_id: str,
        query: str,
        room_id: str = "",
        project_id: str = "",
        session_id: str = "",
        audience: str = "private",
        limit: Optional[int] = 6,
    ) -> List[Dict[str, Any]]:
        if limit is not None and int(limit) <= 0:
            self.search.status['events'] = {'status': 'not_requested', 'complete': False, 'selected': 0}
            return []
        query_tokens = _tokens(query)
        with self.store.reader() as connection:
            rows = self.search.candidates(
                connection, kind="events", subject_id=subject_id, tokens=query_tokens,
                viewer_id=viewer_id, audience=audience, room_id=room_id,
                project_id=project_id, session_id=session_id,
            )
        selected: List[Tuple[float, MemoryEvent]] = []
        now = _now()
        for row in rows:
            event = _row_event(row)
            if not self._visible(
                visibility=event.visibility,
                scope=f"room:{event.room_id}" if event.visibility == Visibility.ROOM_SCOPED.value else "global",
                subject_id=subject_id,
                viewer_id=viewer_id,
                room_id=room_id,
                project_id=project_id,
                session_id=session_id,
                audience=audience,
            ):
                continue
            overlap = len(query_tokens & _tokens(event.content))
            if overlap <= 0:
                continue
            age_days = max(0.0, (now - event.observed_at) / 86_400.0)
            score = overlap + math.exp(-age_days / 90.0)
            selected.append((score, event))
        selected.sort(key=lambda item: (-item[0], -item[1].observed_at))
        result_limit = max(0, min(100, int(limit if limit is not None else 20)))
        status = self.search.status["events"]
        status["selected"] = min(len(selected), result_limit)
        if len(selected) > result_limit:
            status.update(status="bounded", complete=False)
        return [
            {
                **event.to_dict(),
                "content": event.content,
                "retrieval_score": round(score, 6),
            }
            for score, event in selected[:result_limit]
        ]

    @staticmethod
    def _visible(
        *,
        visibility: str,
        scope: str,
        subject_id: str,
        viewer_id: str,
        room_id: str,
        project_id: str = "",
        session_id: str = "",
        audience: str = "private",
    ) -> bool:
        if visibility == Visibility.PUBLIC.value:
            permitted = True
        elif visibility in {
            Visibility.PRIVATE_OWNER.value,
            Visibility.PRIVATE_RELATIONSHIP.value,
        }:
            permitted = (
                str(audience or "private") == "private"
                and bool(viewer_id)
                and viewer_id == subject_id
            )
        elif visibility == Visibility.ROOM_SCOPED.value:
            expected_room = scope.split(":", 1)[1] if scope.startswith("room:") else ""
            permitted = bool(room_id) and bool(expected_room) and room_id == expected_room
        else:
            permitted = False
        if not permitted:
            return False
        if scope.startswith("room:"):
            return bool(room_id) and room_id == scope.split(":", 1)[1]
        if scope.startswith("project:"):
            return bool(project_id) and project_id == scope.split(":", 1)[1]
        if scope.startswith("session:"):
            return bool(session_id) and session_id == scope.split(":", 1)[1]
        return scope == "global" or not scope


__all__ = ["EvidenceMemory"]
