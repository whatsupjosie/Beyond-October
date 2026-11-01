"""User-owned relationship learning for PubPartner.

This module turns *explicit* user corrections and preferences into reviewable,
portable relationship lessons. It deliberately does not guess motives, diagnose
the user, or silently promote weak behavioral inferences.

Design laws
-----------
- Encounters are evidence; lessons are derived records.
- Exact user text remains in the VerbatimVault. Encounter rows store references
  and bounded excerpts, never replace the source record.
- Explicit instructions may become active immediately, but remain editable,
  rejectable, scoped, versioned, and attributable to evidence.
- Inferred patterns remain provisional until reviewed.
- The provider never owns relationship state.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

SCHEMA_VERSION = "PubPartnerRelationship.v1"
MAX_LESSON_TEXT = 600
MAX_EXCERPT = 700
VALID_STATUS = {"provisional", "confirmed", "rejected", "superseded"}
VALID_SCOPE = {"global", "project", "session", "creative", "technical", "emotional", "temporary"}
VALID_KIND = {"preference", "boundary", "workflow", "relationship", "identity", "shared_history"}


def _now() -> float:
    return time.time()


def _safe(value: str, fallback: str = "anon") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or fallback)).strip("._-")
    return (cleaned or fallback)[:120]


def _hash_payload(payload: Dict[str, Any]) -> str:
    core = dict(payload)
    core.pop("encounter_hash", None)
    return hashlib.sha256(
        json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _clip(text: Any, limit: int = MAX_EXCERPT) -> str:
    value = str(text or "")
    return value if len(value) <= limit else value[: max(0, limit - 1)] + "…"


def _tokens(value: Any) -> set[str]:
    stop = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "i", "in", "is", "it", "me", "my", "of", "on", "or", "that",
        "the", "this", "to", "we", "with", "you", "your",
    }
    return {
        token
        for token in re.findall(
            r"[A-Za-z0-9][A-Za-z0-9'_-]{1,}", str(value or "").casefold()
        )
        if token not in stop
    }


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


@dataclass
class RelationshipLesson:
    lesson_id: str
    user_id: str
    friend_id: str
    text: str
    kind: str = "preference"
    scope: str = "global"
    project_id: str = "*"
    session_id: str = "*"
    status: str = "provisional"
    confidence: float = 0.5
    source: str = "explicit_user_signal"
    evidence_ids: List[str] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RelationshipEngine:
    """Persistent encounter ledger plus reviewable relationship lessons."""

    def __init__(self, data_dir: Path | str) -> None:
        self.root = Path(data_dir) / "pubpartner" / "relationship"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ── paths ──────────────────────────────────────────────────────────────
    def _pair_dir(self, user_id: str, friend_id: str) -> Path:
        path = self.root / _safe(user_id) / _safe(friend_id, "friend")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _lessons_path(self, user_id: str, friend_id: str) -> Path:
        return self._pair_dir(user_id, friend_id) / "lessons.json"

    def _encounters_path(self, user_id: str, friend_id: str) -> Path:
        return self._pair_dir(user_id, friend_id) / "encounters.jsonl"

    # ── lessons ────────────────────────────────────────────────────────────
    def _read_lessons(self, user_id: str, friend_id: str) -> List[Dict[str, Any]]:
        path = self._lessons_path(user_id, friend_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("lessons", []) if isinstance(payload, dict) else []
            return [row for row in rows if isinstance(row, dict)]
        except Exception:
            return []

    def _write_lessons(self, user_id: str, friend_id: str, rows: Sequence[Dict[str, Any]]) -> None:
        _atomic_json(
            self._lessons_path(user_id, friend_id),
            {
                "schema_version": SCHEMA_VERSION,
                "user_id": user_id,
                "friend_id": friend_id,
                "updated_at": _now(),
                "lessons": list(rows),
            },
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip().rstrip(" .")

    def add_lesson(
        self,
        *,
        user_id: str,
        friend_id: str,
        text: str,
        kind: str = "preference",
        scope: str = "global",
        project_id: str = "*",
        session_id: str = "*",
        status: str = "provisional",
        confidence: float = 0.5,
        source: str = "manual",
        evidence_ids: Optional[Iterable[str]] = None,
        exceptions: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        text = self._normalize_text(text)
        if not text:
            raise ValueError("lesson text is required")
        if len(text) > MAX_LESSON_TEXT:
            raise ValueError(f"lesson text must be <= {MAX_LESSON_TEXT} characters")
        kind = kind if kind in VALID_KIND else "preference"
        scope = scope if scope in VALID_SCOPE else "global"
        status = status if status in VALID_STATUS else "provisional"
        confidence = max(0.0, min(1.0, float(confidence)))
        user_id = str(user_id or "anon")[:120]
        friend_id = str(friend_id or "friend")[:120]

        with self._lock:
            rows = self._read_lessons(user_id, friend_id)
            key = (text.casefold(), kind, scope, str(project_id or "*"), str(session_id or "*"))
            for row in rows:
                existing = (
                    str(row.get("text", "")).casefold(),
                    row.get("kind"), row.get("scope"),
                    str(row.get("project_id", "*")), str(row.get("session_id", "*")),
                )
                if existing == key and row.get("status") != "rejected":
                    evidence = list(dict.fromkeys([*(row.get("evidence_ids") or []), *(evidence_ids or [])]))[-50:]
                    row["evidence_ids"] = evidence
                    row["confidence"] = max(float(row.get("confidence", 0.0)), confidence)
                    if status == "confirmed":
                        row["status"] = "confirmed"
                    row["updated_at"] = _now()
                    row["version"] = int(row.get("version", 1)) + 1
                    self._write_lessons(user_id, friend_id, rows)
                    return {"ok": True, "created": False, "lesson": row}

            lesson = RelationshipLesson(
                lesson_id=f"rel_{int(_now() * 1000)}_{uuid.uuid4().hex[:10]}",
                user_id=user_id,
                friend_id=friend_id,
                text=text,
                kind=kind,
                scope=scope,
                project_id=str(project_id or "*")[:120],
                session_id=str(session_id or "*")[:120],
                status=status,
                confidence=confidence,
                source=str(source or "manual")[:80],
                evidence_ids=list(dict.fromkeys(str(v)[:160] for v in (evidence_ids or []) if str(v).strip()))[-50:],
                exceptions=[str(v)[:240] for v in (exceptions or []) if str(v).strip()][:20],
                metadata=dict(metadata or {}),
            ).to_dict()
            rows.append(lesson)
            self._write_lessons(user_id, friend_id, rows)
            return {"ok": True, "created": True, "lesson": lesson}

    def list_lessons(
        self,
        *,
        user_id: str,
        friend_id: str,
        status: str = "all",
        project_id: str = "*",
        session_id: str = "*",
        limit: int = 200,
    ) -> Dict[str, Any]:
        rows = self._read_lessons(user_id, friend_id)
        out: List[Dict[str, Any]] = []
        for row in rows:
            if status != "all" and row.get("status") != status:
                continue
            row_project = str(row.get("project_id") or "*")
            row_session = str(row.get("session_id") or "*")
            if project_id != "*" and row_project not in {"*", project_id}:
                continue
            if session_id != "*" and row_session not in {"*", session_id}:
                continue
            out.append(row)
        out.sort(key=lambda row: (row.get("status") != "confirmed", -float(row.get("confidence", 0)), -float(row.get("updated_at", 0))))
        return {"ok": True, "schema_version": SCHEMA_VERSION, "lessons": out[: max(1, min(1000, int(limit)))]}

    def update_lesson(
        self,
        *,
        user_id: str,
        friend_id: str,
        lesson_id: str,
        patch: Dict[str, Any],
    ) -> Dict[str, Any]:
        allowed = {"text", "kind", "scope", "project_id", "session_id", "status", "confidence", "exceptions", "metadata"}
        with self._lock:
            rows = self._read_lessons(user_id, friend_id)
            for row in rows:
                if row.get("lesson_id") != lesson_id:
                    continue
                for key, value in patch.items():
                    if key not in allowed:
                        continue
                    if key == "text":
                        value = self._normalize_text(str(value or ""))
                        if not value or len(value) > MAX_LESSON_TEXT:
                            raise ValueError("invalid lesson text")
                    elif key == "kind":
                        value = value if value in VALID_KIND else row.get("kind", "preference")
                    elif key == "scope":
                        value = value if value in VALID_SCOPE else row.get("scope", "global")
                    elif key == "status":
                        value = value if value in VALID_STATUS else row.get("status", "provisional")
                    elif key == "confidence":
                        value = max(0.0, min(1.0, float(value)))
                    elif key == "exceptions":
                        value = [str(v)[:240] for v in (value or []) if str(v).strip()][:20]
                    elif key == "metadata":
                        value = dict(value or {}) if isinstance(value, dict) else row.get("metadata", {})
                    else:
                        value = str(value or "*")[:120]
                    row[key] = value
                row["updated_at"] = _now()
                row["version"] = int(row.get("version", 1)) + 1
                self._write_lessons(user_id, friend_id, rows)
                return {"ok": True, "lesson": row}
        raise FileNotFoundError(lesson_id)

    def compact(
        self,
        *,
        user_id: str,
        friend_id: str,
        project_id: str = "*",
        session_id: str = "*",
        query: str = "",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        rows = self.list_lessons(
            user_id=user_id,
            friend_id=friend_id,
            status="confirmed",
            project_id=project_id,
            session_id=session_id,
            limit=limit * 3,
        )["lessons"]
        query_tokens = _tokens(query)
        response_style = {
            "answer", "answers", "brief", "bullets", "cadence", "concise",
            "detail", "detailed", "direct", "explain", "format", "formal",
            "paragraph", "paragraphs", "response", "responses", "short",
            "style", "tone", "verbose",
        }
        compacted = []
        for row in rows:
            kind = str(row.get("kind") or "")
            lesson_tokens = _tokens(row.get("text"))
            globally_applicable = kind in {"boundary", "workflow", "identity"}
            if kind == "preference" and lesson_tokens & response_style:
                globally_applicable = True
            # With no query, preserve the inspection/API behavior. During a turn,
            # topical preferences and shared-history lessons must earn relevance.
            if query_tokens and not globally_applicable and not (query_tokens & lesson_tokens):
                continue
            compacted.append({
                "id": row.get("lesson_id"),
                "kind": kind,
                "scope": row.get("scope"),
                "text": _clip(row.get("text"), 280),
                "confidence": round(float(row.get("confidence", 0.0)), 3),
                "source": "relationship",
            })
            if len(compacted) >= limit:
                break
        return compacted

    # ── encounter ledger ───────────────────────────────────────────────────
    def _last_encounter_hash(self, user_id: str, friend_id: str) -> str:
        path = self._encounters_path(user_id, friend_id)
        if not path.exists():
            return "GENESIS"
        last = "GENESIS"
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    last = str(json.loads(line).get("encounter_hash") or last)
        except Exception:
            return "UNREADABLE"
        return last

    def record_encounter(
        self,
        *,
        user_id: str,
        friend_id: str,
        session_id: str,
        project_id: str,
        source_id: str,
        source_sha256: str,
        user_excerpt: str,
        raw_response: str,
        friend_response: str,
        provider: str,
        model: str,
        receipt_id: str = "",
        guidance_count: int = 0,
        relationship_lesson_ids: Optional[Sequence[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        encounter_id = f"enc_{int(_now() * 1000)}_{uuid.uuid4().hex[:10]}"
        with self._lock:
            row = {
                "schema_version": SCHEMA_VERSION,
                "encounter_id": encounter_id,
                "ts": _now(),
                "user_id": str(user_id or "anon")[:120],
                "friend_id": str(friend_id or "friend")[:120],
                "session_id": str(session_id or "default")[:120],
                "project_id": str(project_id or "default")[:120],
                "source_id": str(source_id or "")[:180],
                "source_sha256": str(source_sha256 or "")[:128],
                "user_excerpt": _clip(user_excerpt),
                "raw_response_sha256": hashlib.sha256(str(raw_response or "").encode("utf-8")).hexdigest(),
                "friend_response_sha256": hashlib.sha256(str(friend_response or "").encode("utf-8")).hexdigest(),
                "provider": str(provider or "unknown")[:80],
                "model": str(model or "unknown")[:160],
                "receipt_id": str(receipt_id or "")[:180],
                "guidance_count": max(0, int(guidance_count or 0)),
                "relationship_lesson_ids": [str(v)[:180] for v in (relationship_lesson_ids or [])][:40],
                "metadata": dict(metadata or {}),
                "prev_encounter_hash": self._last_encounter_hash(user_id, friend_id),
            }
            row["encounter_hash"] = _hash_payload(row)
            path = self._encounters_path(user_id, friend_id)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        return row

    def list_encounters(self, *, user_id: str, friend_id: str, limit: int = 100) -> Dict[str, Any]:
        path = self._encounters_path(user_id, friend_id)
        rows: List[Dict[str, Any]] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
                except Exception:
                    rows.append({"error": "invalid encounter row"})
        return {"ok": True, "encounters": rows[-max(1, min(1000, int(limit))):], "verify": self.verify_encounters(user_id=user_id, friend_id=friend_id)}

    def verify_encounters(self, *, user_id: str, friend_id: str) -> Dict[str, Any]:
        path = self._encounters_path(user_id, friend_id)
        if not path.exists():
            return {"ok": True, "entries": 0, "last_hash": "GENESIS"}
        prev = "GENESIS"
        count = 0
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception as exc:
                return {"ok": False, "line": line_no, "error": f"invalid json: {exc}"}
            if row.get("prev_encounter_hash") != prev:
                return {"ok": False, "line": line_no, "error": "encounter chain break"}
            expected = _hash_payload(row)
            if row.get("encounter_hash") != expected:
                return {"ok": False, "line": line_no, "error": "encounter hash mismatch"}
            prev = str(row.get("encounter_hash"))
            count += 1
        return {"ok": True, "entries": count, "last_hash": prev}

    # ── signal extraction ──────────────────────────────────────────────────
    @staticmethod
    def _sentences(text: str) -> List[str]:
        chunks = re.split(r"(?<=[.!?])\s+|\n+", str(text or ""))
        return [re.sub(r"\s+", " ", chunk).strip() for chunk in chunks if chunk.strip()]

    def extract_explicit_lessons(
        self,
        *,
        user_id: str,
        friend_id: str,
        text: str,
        encounter_id: str,
        project_id: str = "*",
        session_id: str = "*",
    ) -> List[Dict[str, Any]]:
        """Extract only high-confidence, explicit user instructions.

        We intentionally avoid interpreting silence, topic changes, profanity,
        or emotional intensity as preferences. Those require review or repeated
        evidence in later versions.
        """
        proposals: List[Dict[str, Any]] = []
        candidates: List[Dict[str, Any]] = []
        patterns = [
            (re.compile(r"^(?:please\s+)?(?:do not|don't|never)\s+(.+)$", re.I), "boundary", 0.98),
            (re.compile(r"^i\s+(?:really\s+)?(?:like|love|prefer)\s+(?:it\s+)?when\s+you\s+(.+)$", re.I), "preference", 0.95),
            (re.compile(r"^i\s+(?:really\s+)?prefer\s+(.+)$", re.I), "preference", 0.93),
            (re.compile(r"^(?:please\s+)?always\s+(.+)$", re.I), "workflow", 0.97),
            (re.compile(r"^when\s+(.+?),\s*(?:please\s+)?(.+)$", re.I), "workflow", 0.90),
            (re.compile(r"^(?:call|refer to)\s+me\s+(?:as\s+)?(.+)$", re.I), "identity", 0.99),
            (re.compile(r"^remember\s+(?:that\s+)?(.+)$", re.I), "shared_history", 0.88),
        ]
        # Mask full quoted spans *before* splitting sentences. Checking only
        # each sentence's first character admits later sentences in a quote.
        unquoted = re.sub(r'"[^"]*(?:"|$)|“[^”]*(?:”|$)|‘[^’]*(?:’|$)',
                          '. ', text, flags=re.DOTALL)
        unquoted = re.sub(r"(?<!\w)'[^']*'(?!\w)", '. ', unquoted)
        for sentence in self._sentences(unquoted):
            clean = sentence.strip()
            # Quoted speech is evidence, not an instruction from this user.
            if clean.startswith(('"', '“', "'", "‘", ">")):
                continue
            for regex, kind, confidence in patterns:
                match = regex.match(clean)
                if not match:
                    continue
                if kind == "boundary":
                    lesson_text = "Do not " + match.group(1).strip().rstrip(".!?")
                elif kind == "identity":
                    lesson_text = "Address the user as " + match.group(1).strip().rstrip(".!?")
                elif kind == "workflow" and len(match.groups()) == 2:
                    lesson_text = f"When {match.group(1).strip()}, {match.group(2).strip().rstrip('.!?')}"
                else:
                    lesson_text = match.group(1).strip().rstrip(".!?")
                if len(lesson_text) < 4:
                    continue
                if len(self._normalize_text(lesson_text)) > MAX_LESSON_TEXT:
                    raise ValueError(f"lesson text must be <= {MAX_LESSON_TEXT} characters")
                candidates.append(dict(
                    user_id=user_id,
                    friend_id=friend_id,
                    text=lesson_text,
                    kind=kind,
                    scope="project" if project_id not in {"", "*", "default"} else "global",
                    project_id=project_id or "*",
                    session_id="*",
                    status="confirmed",
                    confidence=confidence,
                    source="explicit_user_signal",
                    evidence_ids=[encounter_id],
                    metadata={"extracted_from": "user_message", "original_sentence": _clip(clean, 300)},
                ))
                break
        for candidate in candidates:
            proposals.append(self.add_lesson(**candidate)["lesson"])
        return proposals

    def summary(self, *, user_id: str, friend_id: str, project_id: str = "*", session_id: str = "*") -> Dict[str, Any]:
        rows = self.list_lessons(user_id=user_id, friend_id=friend_id, project_id=project_id, session_id=session_id, limit=1000)["lessons"]
        counts = {status: sum(1 for row in rows if row.get("status") == status) for status in VALID_STATUS}
        encounters = self.list_encounters(user_id=user_id, friend_id=friend_id, limit=1)
        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "user_id": user_id,
            "friend_id": friend_id,
            "counts": counts,
            "active": [row for row in rows if row.get("status") == "confirmed"][:20],
            "emerging": [row for row in rows if row.get("status") == "provisional"][:20],
            "encounter_chain": encounters.get("verify"),
        }


__all__ = ["RelationshipEngine", "RelationshipLesson", "SCHEMA_VERSION"]
