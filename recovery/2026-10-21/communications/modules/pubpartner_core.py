"""PubPartner core spine for friend-preserving LLM sessions.

This module is deliberately small and dependency-light. It does not call an LLM.
It prepares the packet that should be sent to the chosen engine and preserves the
user's original text before any compacting, summarizing, translating, or voice
normalization happens.

Core laws implemented here:
- The raw LLM is an engine, not the friend.
- The user message is immutable source material, not prompt clay.
- Compact packets may reference exact text, but may not replace it.
- Alex supplies care/tone state; Jeremy supplies continuity/memory routing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:  # optional; code still works without Jeremy being present
    from .jeremy_cricket import CricketKeeper, MemoryType as JeremyMemoryType
except Exception:  # pragma: no cover - guarded import for partial builds
    CricketKeeper = Any  # type: ignore
    JeremyMemoryType = None  # type: ignore

try:  # optional; code still works without Alex/Jeremy bridge being present
    from .alex_jeremy_bridge import AlexJeremyBridge
except Exception:  # pragma: no cover
    AlexJeremyBridge = Any  # type: ignore

try:  # optional for partial and legacy builds
    from .pubpartner_vessel import PubPartnerVesselRuntime
except Exception:  # pragma: no cover
    PubPartnerVesselRuntime = Any  # type: ignore


from .turn_serialization import serialized_turn
from .pubpartner_provider import PubPartnerProviderDispatcher
from .pubpartner_voice import AlexPersonalizationEngine
from .pubpartner_profiles import PubPartnerProfileStore
from .pubpartner_guidance import PubPartnerGuidanceStore
from .pubpartner_tokens import PubPartnerTokenCounter
from .pubpartner_receipts import PubPartnerReceiptStore
from .pubpartner_relationship import RelationshipEngine
from .pubpartner_knowledge import PubPartnerKnowledgeBroker

FCP_VERSION = "FCP1"
DEFAULT_LANGUAGE = "en-US"
MAX_COMPACT_MESSAGE_CHARS = 900
MAX_MEMORY_SUMMARY_CHARS = 220
MAX_RULES = 24
MAX_FULL_PROMPT_TEXT_CHARS = 2400

_EXACT_TEXT_KINDS = {
    "lyrics",
    "poem",
    "poetry",
    "legal",
    "quote",
    "transcript",
    "source_code",
    "code",
    "command",
    "prompt",
    "contract",
    "evidence",
}

_PROVIDER_FIXES: Dict[str, List[str]] = {
    "openai": ["trim_boilerplate", "anti_syc", "no_fake_memory"],
    "gpt": ["trim_boilerplate", "anti_syc", "no_fake_memory"],
    "claude": ["trim_overexplaining", "limit_headers", "keep_voice"],
    "anthropic": ["trim_overexplaining", "limit_headers", "keep_voice"],
    "gemini": ["trim_formality", "reduce_safety_prelude", "anti_syc"],
    "google": ["trim_formality", "reduce_safety_prelude", "anti_syc"],
    "grok": ["trim_edgelord", "keep_kindness", "anti_syc"],
    "local": ["simple_syntax", "no_nested_lists", "no_dense_codes"],
    "offline": ["simple_syntax", "short_answer", "no_fake_capabilities"],
    "opencode_zen": ["reference_only", "verify_facts", "no_personal_memory"],
}


def _now() -> float:
    return time.time()


def _safe_slug(value: str, fallback: str = "anon") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or fallback)).strip("._-")
    return (cleaned or fallback)[:120]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clip(text: str, limit: int) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _turn_audience(task: Optional[Dict[str, Any]], room_id: str) -> str:
    requested = str(
        (task or {}).get("audience") or (task or {}).get("visibility") or ""
    ).casefold()
    # A client cannot turn a shared physical room into a private channel just
    # by setting task.audience="private". That would expose personal memories.
    private_rooms = {"pubpartner", "phone", "private", "dressing_room"}
    if room_id not in private_rooms:
        return requested if requested in {"shared", "public"} else "shared"
    if requested in {"shared", "public"}:
        return requested
    return "private"


def _string_list(values: Any, *, limit: int = MAX_RULES) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw = [v.strip() for v in re.split(r"[,;\n]+", values) if v.strip()]
    elif isinstance(values, Iterable):
        raw = [str(v).strip() for v in values if str(v).strip()]
    else:
        raw = [str(values).strip()]
    seen: set[str] = set()
    out: List[str] = []
    for item in raw:
        key = item.lower()
        if key not in seen:
            out.append(item[:80])
            seen.add(key)
        if len(out) >= limit:
            break
    return out


def _detect_exact_kind(text: str, declared: str = "") -> str:
    declared = (declared or "").lower().strip()
    if declared in _EXACT_TEXT_KINDS:
        return declared
    lower = text.lower()
    if "```" in text:
        return "code"
    if any(word in lower for word in ("lyrics", "chorus", "verse", "bridge:")):
        return "lyrics"
    if any(word in lower for word in ("here is the exact", "quote this", "verbatim", "do not alter")):
        return "quote"
    if re.search(r"(^|\n)\s*(def |class |function |import |from |const |let |var |python |bash |npm |git )", text):
        return "code"
    # Newline-heavy short lines are often poems/lyrics; preserve cautiously.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 3 and sum(1 for ln in lines if len(ln) <= 64) >= max(3, int(len(lines) * 0.7)):
        return "poetry"
    return declared or "message"


@dataclass
class SourceRecord:
    """Immutable source message stored before any transformation."""

    source_id: str
    user_id: str
    session_id: str
    text: str
    kind: str
    language: str
    sha256: str
    byte_len: int
    char_len: int
    created_at: float
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_sha256: str = ""
    encoding: str = "utf-8"
    newline_count: int = 0
    endswith_newline: bool = False
    audit_hash: str = ""
    prev_audit_hash: str = ""
    sealed: bool = True

    def ref(self) -> Dict[str, Any]:
        return {
            "id": self.source_id,
            "kind": self.kind,
            "sha256": self.sha256,
            "raw_sha256": self.raw_sha256 or self.sha256,
            "chars": self.char_len,
            "bytes": self.byte_len,
            "encoding": self.encoding,
            "newline_count": self.newline_count,
            "endswith_newline": self.endswith_newline,
        }

    def integrity(self) -> Dict[str, Any]:
        return {
            "sha256": self.sha256,
            "raw_sha256": self.raw_sha256 or self.sha256,
            "audit_hash": self.audit_hash,
            "prev_audit_hash": self.prev_audit_hash,
            "sealed": self.sealed,
            "encoding": self.encoding,
        }


class VerbatimVault:
    """Lossless source buffer for exact user text.

    The vault stores the user's original UTF-8 bytes before any transformation.
    Metadata is JSON for easy inspection, the exact text is also sealed in a
    sidecar `.utf8` file, and every write appends a tiny hash-chained audit row.
    This is not a full security vault, but it is no longer just a casual note file.
    """

    def __init__(self, data_dir: Path):
        self.root = Path(data_dir) / "pubpartner" / "verbatim"
        self.root.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, user_id: str, session_id: str) -> Path:
        path = self.root / _safe_slug(user_id) / _safe_slug(session_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _record_path(self, user_id: str, session_id: str, source_id: str) -> Path:
        return self._session_dir(user_id, session_id) / f"{_safe_slug(source_id)}.json"

    def _raw_path(self, user_id: str, session_id: str, source_id: str) -> Path:
        return self._session_dir(user_id, session_id) / f"{_safe_slug(source_id)}.utf8"

    def _audit_path(self, user_id: str, session_id: str) -> Path:
        return self._session_dir(user_id, session_id) / "audit_hash_chain.jsonl"

    def _last_audit_hash(self, user_id: str, session_id: str) -> str:
        audit = self._audit_path(user_id, session_id)
        if not audit.exists():
            return "GENESIS"
        last = "GENESIS"
        try:
            for line in audit.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                last = json.loads(line).get("audit_hash") or last
        except Exception:
            return "UNREADABLE_AUDIT"
        return last

    @staticmethod
    def _audit_hash(payload: Dict[str, Any]) -> str:
        core = dict(payload)
        core.pop("audit_hash", None)
        return _sha256_text(json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    def _prepare_audit(self, rec: SourceRecord, event: str = "store") -> Dict[str, Any]:
        prev = self._last_audit_hash(rec.user_id, rec.session_id)
        payload = {
            "event": event,
            "source_id": rec.source_id,
            "sha256": rec.sha256,
            "raw_sha256": rec.raw_sha256 or rec.sha256,
            "prev_audit_hash": prev,
            "ts": rec.created_at,
        }
        payload["audit_hash"] = self._audit_hash(payload)
        return payload

    def _write_audit(self, rec: SourceRecord, audit_payload: Dict[str, Any]) -> SourceRecord:
        rec.prev_audit_hash = str(audit_payload.get("prev_audit_hash") or "GENESIS")
        rec.audit_hash = str(audit_payload.get("audit_hash") or "")
        audit = self._audit_path(rec.user_id, rec.session_id)
        with audit.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(audit_payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        return rec

    def _append_audit(self, rec: SourceRecord, event: str = "store") -> SourceRecord:
        # Backward-compatible helper for older call sites. New store path uses
        # prepare -> write metadata/raw -> append, so audit never claims a failed write.
        return self._write_audit(rec, self._prepare_audit(rec, event))

    def store(
        self,
        *,
        user_id: str,
        session_id: str,
        text: str,
        kind: str = "message",
        language: str = DEFAULT_LANGUAGE,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SourceRecord:
        if not isinstance(text, str):
            text = str(text)
        raw = text.encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        source_id = f"src_{int(_now() * 1000)}_{digest[:12]}_{uuid.uuid4().hex[:8]}"
        detected_kind = _detect_exact_kind(text, kind)
        meta = dict(metadata or {})
        meta.update({
            "declared_kind": kind or "message",
            "detected_kind": detected_kind,
            "lossless_capture": True,
            "transform_status": "original_preserved_before_any_transform",
        })
        rec = SourceRecord(
            source_id=source_id,
            user_id=user_id or "anon",
            session_id=session_id or "default",
            text=text,
            kind=detected_kind,
            language=language or DEFAULT_LANGUAGE,
            sha256=digest,
            raw_sha256=digest,
            byte_len=len(raw),
            char_len=len(text),
            newline_count=text.count("\n"),
            endswith_newline=text.endswith("\n"),
            created_at=_now(),
            parent_id=parent_id,
            metadata=meta,
            sealed=True,
        )
        audit_payload = self._prepare_audit(rec, "store")
        rec.prev_audit_hash = str(audit_payload["prev_audit_hash"])
        rec.audit_hash = str(audit_payload["audit_hash"])
        payload = asdict(rec)
        path = self._record_path(rec.user_id, rec.session_id, source_id)
        raw_path = self._raw_path(rec.user_id, rec.session_id, source_id)
        if path.exists() or raw_path.exists():
            raise FileExistsError(f"source id collision or attempted overwrite: {source_id}")
        tmp_raw = raw_path.with_suffix(".utf8.tmp")
        tmp_json = path.with_suffix(".json.tmp")
        try:
            tmp_raw.write_bytes(raw)
            tmp_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_raw.replace(raw_path)
            tmp_json.replace(path)
            self._write_audit(rec, audit_payload)
        except Exception:
            for tmp_path in (tmp_raw, tmp_json):
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    pass
            raise
        return rec

    def load(self, *, user_id: str, session_id: str, source_id: str) -> SourceRecord:
        path = self._record_path(user_id or "anon", session_id or "default", source_id)
        if not path.exists():
            raise FileNotFoundError(source_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        rec = SourceRecord(**payload)
        raw = rec.text.encode("utf-8")
        if _sha256_text(rec.text) != rec.sha256:
            raise ValueError(f"verbatim source JSON text hash mismatch: {source_id}")
        raw_path = self._raw_path(rec.user_id, rec.session_id, source_id)
        if rec.sealed and not raw_path.exists():
            raise ValueError(f"verbatim source raw-byte sidecar missing for sealed source: {source_id}")
        if raw_path.exists():
            sealed = raw_path.read_bytes()
            if hashlib.sha256(sealed).hexdigest() != (rec.raw_sha256 or rec.sha256):
                raise ValueError(f"verbatim source raw-byte hash mismatch: {source_id}")
            if sealed != raw:
                raise ValueError(f"verbatim source JSON/raw sidecar mismatch: {source_id}")
        return rec

    def list_session(self, *, user_id: str, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        folder = self._session_dir(user_id or "anon", session_id or "default")
        rows: List[Dict[str, Any]] = []
        for path in sorted(folder.glob("src_*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload.pop("text", None)
                rows.append(payload)
            except Exception:
                continue
            if len(rows) >= limit:
                break
        return rows

    def verify_session_audit(self, *, user_id: str, session_id: str) -> Dict[str, Any]:
        audit = self._audit_path(user_id or "anon", session_id or "default")
        if not audit.exists():
            return {"ok": True, "entries": 0, "last_hash": "GENESIS", "warning": "no audit rows"}
        prev = "GENESIS"
        entries = 0
        source_ids: List[str] = []
        for lineno, line in enumerate(audit.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception as exc:
                return {"ok": False, "line": lineno, "error": f"invalid audit json: {exc}"}
            expected = self._audit_hash(payload)
            if payload.get("audit_hash") != expected:
                return {"ok": False, "line": lineno, "error": "audit hash mismatch"}
            if payload.get("prev_audit_hash") != prev:
                return {"ok": False, "line": lineno, "error": "audit chain break", "expected_prev": prev}
            src_id = str(payload.get("source_id") or "")
            try:
                rec = self.load(user_id=user_id, session_id=session_id, source_id=src_id)
            except Exception as exc:
                return {"ok": False, "line": lineno, "source_id": src_id, "error": f"source verification failed: {exc}"}
            if rec.audit_hash and rec.audit_hash != payload.get("audit_hash"):
                return {"ok": False, "line": lineno, "source_id": src_id, "error": "record audit hash mismatch"}
            prev = str(payload["audit_hash"])
            entries += 1
            source_ids.append(src_id)
        return {"ok": True, "entries": entries, "last_hash": prev, "source_ids": source_ids}


@dataclass
class FriendProfile:
    friend_id: str = "friend"
    display_name: str = "Friend"
    role: List[str] = field(default_factory=lambda: ["ai_friend", "collaborator"])
    tone: List[str] = field(default_factory=lambda: ["warm", "direct", "practical"])
    cadence: List[str] = field(default_factory=lambda: ["plain", "low_fluff"])
    avoid: List[str] = field(default_factory=lambda: ["generic_assistant", "fake_memory"])
    boundaries: List[str] = field(default_factory=lambda: ["no_fake_done", "ask_when_needed"])
    principles: List[str] = field(default_factory=list)
    self_concept: str = ""
    mode_policy: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Optional[Dict[str, Any]]) -> "FriendProfile":
        payload = dict(payload or {})
        return cls(
            friend_id=_safe_slug(payload.get("friend_id") or payload.get("id") or "friend", "friend"),
            display_name=str(payload.get("display_name") or payload.get("name") or payload.get("friend_id") or "Friend")[:80],
            role=_string_list(payload.get("role") or ["ai_friend", "collaborator"]),
            tone=_string_list(payload.get("tone") or ["warm", "direct", "practical"]),
            cadence=_string_list(payload.get("cadence") or payload.get("cad") or ["plain", "low_fluff"]),
            avoid=_string_list(payload.get("avoid") or ["generic_assistant", "fake_memory"]),
            boundaries=_string_list(payload.get("boundaries") or payload.get("bound") or ["no_fake_done", "ask_when_needed"]),
            principles=_string_list(payload.get("principles") or payload.get("law") or [], limit=16),
            self_concept=_clip(payload.get("self_concept") or payload.get("identity") or "", 480),
            mode_policy=dict(payload.get("mode_policy") or payload.get("modes") or {}),
        )

    def compact(self) -> Dict[str, Any]:
        return {
            "id": self.friend_id,
            "name": self.display_name,
            "role": self.role,
            "tone": self.tone,
            "cad": self.cadence,
            "avoid": self.avoid,
            "bound": self.boundaries,
            "law": self.principles,
            "identity": self.self_concept,
            "modes": self.mode_policy,
        }


@dataclass
class UserPrimer:
    user_id: str = "anon"
    rules: List[str] = field(default_factory=lambda: ["direct", "warm", "no_fluff"])
    workflow: List[str] = field(default_factory=lambda: ["preserve_exact_text", "show_done_not_vibes"])
    accessibility: List[str] = field(default_factory=list)
    language: str = DEFAULT_LANGUAGE

    @classmethod
    def from_payload(cls, user_id: str, payload: Optional[Dict[str, Any]]) -> "UserPrimer":
        payload = dict(payload or {})
        return cls(
            user_id=user_id or str(payload.get("user_id") or "anon"),
            rules=_string_list(payload.get("rules") or payload.get("roe") or ["direct", "warm", "no_fluff"]),
            workflow=_string_list(payload.get("workflow") or ["preserve_exact_text", "show_done_not_vibes"]),
            accessibility=_string_list(payload.get("accessibility") or payload.get("acc") or []),
            language=str(payload.get("language") or payload.get("lang") or DEFAULT_LANGUAGE)[:32],
        )

    def compact(self) -> Dict[str, Any]:
        return {"id": self.user_id, "roe": self.rules, "wf": self.workflow, "acc": self.accessibility}


@dataclass
class ProviderProfile:
    provider: str = "generic"
    model: str = "unknown"
    fixes: List[str] = field(default_factory=lambda: ["trim_boilerplate", "anti_syc", "no_fake_memory"])

    @classmethod
    def from_payload(cls, payload: Optional[Dict[str, Any]]) -> "ProviderProfile":
        payload = dict(payload or {})
        provider = str(payload.get("provider") or payload.get("name") or payload.get("p") or "generic").lower()[:60]
        model = str(payload.get("model") or "unknown")[:120]
        default = _PROVIDER_FIXES.get(provider, ["trim_boilerplate", "anti_syc", "no_fake_memory"])
        return cls(provider=provider, model=model, fixes=_string_list(payload.get("fixes") or payload.get("fix") or default, limit=16))

    def compact(self) -> Dict[str, Any]:
        return {"p": self.provider, "model": self.model, "fix": self.fixes}


@dataclass
class MemoryRef:
    id: str
    kind: str
    text: str
    importance: int = 5
    source: str = "memory"

    def compact(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "k": self.kind,
            "imp": self.importance,
            "src": self.source,
            "txt": _clip(self.text, MAX_MEMORY_SUMMARY_CHARS),
        }


@dataclass
class FCP1Packet:
    language: str
    user: UserPrimer
    friend: FriendProfile
    provider: ProviderProfile
    task: Dict[str, Any]
    project: Dict[str, Any]
    safety: List[str]
    output: Dict[str, Any]
    source: SourceRecord
    memories: List[MemoryRef] = field(default_factory=list)
    alex_packet: Optional[Dict[str, Any]] = None
    jeremy_whisper: str = ""
    guidance: List[Dict[str, Any]] = field(default_factory=list)
    vessel_context: Dict[str, Any] = field(default_factory=dict)
    conversation: List[Dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=_now)

    def canonical(self, *, include_source_text: bool = False) -> Dict[str, Any]:
        exact_required = self.source.kind in _EXACT_TEXT_KINDS or self.source.kind != "message"
        msg_block: Dict[str, Any] = {
            "ref": self.source.ref(),
            "lossless": True,
            "verbatim_required": exact_required,
            "text_status": "included" if include_source_text else "omitted_ref_only",
        }
        if include_source_text:
            msg_block["text"] = self.source.text
        else:
            msg_block["preview"] = _clip(self.source.text.replace("\n", "\\n").strip(), 180)
            msg_block["note"] = "Original text is sealed in VerbatimVault; restore by msg.ref.id and verify sha256 before quoting."
        source_policy = {
            "immutable": True,
            "quote_policy": "quote_only_after_restoring_msg_ref",
            "derived_ok": True,
            "derived_must_not_replace_original": True,
            "integrity": self.source.integrity(),
        }
        return {
            "v": FCP_VERSION,
            "lang": self.language,
            "u": self.user.compact(),
            "f": self.friend.compact(),
            "m": [m.compact() for m in self.memories],
            "proj": self.project,
            "task": self.task,
            "safe": self.safety,
            "out": self.output,
            "norm": self.provider.compact(),
            "alex": self._compact_alex(),
            "jeremy": self._compact_jeremy(),
            "guide": self.guidance,
            "vessel": self.vessel_context,
            "history": self.conversation,
            "msg": msg_block,
            "source_policy": source_policy,
            "ts": self.created_at,
        }

    def as_compact_text(self, *, include_source_text: bool = True) -> str:
        data = self.canonical(include_source_text=include_source_text)
        source = data["msg"]
        def j(value: Any) -> str:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        lines = ["@FCP1"]
        lines.append(f"lang={data['lang']}")
        lines.append(f"u={j(data['u'])}")
        lines.append(f"f={j(data['f'])}")
        if data["m"]:
            lines.append(f"m={j(data['m'])}")
        lines.append(f"proj={j(data['proj'])}")
        lines.append(f"task={j(data['task'])}")
        lines.append(f"safe={j(data['safe'])}")
        lines.append(f"out={j(data['out'])}")
        lines.append(f"norm={j(data['norm'])}")
        if data.get("alex"):
            lines.append(f"alex={j(data['alex'])}")
        if data.get("jeremy"):
            lines.append(f"jeremy={j(data['jeremy'])}")
        if data.get("guide"):
            lines.append(f"guide={j(data['guide'])}")
        if data.get("vessel"):
            lines.append(f"vessel={j(data['vessel'])}")
        if data.get("history"):
            lines.append(f"history={j(data['history'])}")
        lines.append(f"msg_ref={j(source['ref'])};lossless=true;kind={self.source.kind}")
        lines.append(f"source_policy={j(data['source_policy'])}")
        if include_source_text and "text" in source:
            lines.append("msg<<FCP1_VERBATIM")
            lines.append(source["text"])
            lines.append("FCP1_VERBATIM")
        elif "text_b64" in source:
            lines.append(f"msg_b64={source['text_b64']}")
        return "\n".join(lines)

    def as_json(self, *, include_source_text: bool = True) -> str:
        return json.dumps(self.canonical(include_source_text=include_source_text), ensure_ascii=False, separators=(",", ":"))

    def _compact_alex(self) -> Dict[str, Any]:
        if not self.alex_packet:
            return {}
        keys = [
            "alex_state", "user_battery", "tone_guidance", "pace_guidance",
            "intervention_style", "care_priority", "fragility_level", "do_not_touch",
            "response_guidelines", "anchor_message", "analysis_source",
            "private_memory_context_withheld", "emotional_coordination",
            "system_alex_guidance",
        ]
        return {k: self.alex_packet.get(k) for k in keys if k in self.alex_packet}

    def _compact_jeremy(self) -> Dict[str, Any]:
        if not self.jeremy_whisper:
            return {}
        return {"whisper": _clip(self.jeremy_whisper, 260)}


class PubPartnerSpine:
    """Builds friend-preserving context packets and wires Alex/Jeremy state."""

    def __init__(
        self,
        data_dir: Path,
        *,
        alex_bridge: Optional[AlexJeremyBridge] = None,
        cricket_keeper: Optional[CricketKeeper] = None,
        vessel_runtime: Optional[PubPartnerVesselRuntime] = None,
        scoped_memory: bool = False,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.vault = VerbatimVault(self.data_dir)
        self.alex_bridge = alex_bridge
        self.cricket_keeper = cricket_keeper
        self.vessel_runtime = vessel_runtime
        self.scoped_memory = scoped_memory
        self.session_dir = self.data_dir / "pubpartner" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.provider_dispatcher = PubPartnerProviderDispatcher()
        self.blackbox_witness = None
        self.voice_restorer = AlexPersonalizationEngine()
        self.profiles = PubPartnerProfileStore(self.data_dir)
        self.guidance_store = PubPartnerGuidanceStore(self.data_dir)
        self.token_counter = PubPartnerTokenCounter()
        self.receipts = PubPartnerReceiptStore(self.data_dir)
        self.relationship = RelationshipEngine(self.data_dir)
        self.knowledge = PubPartnerKnowledgeBroker()

    def _default_vessel_friend(self) -> Dict[str, Any]:
        """Combine the single authored Alex voice with her persistent vessel.

        User edits to the canonical friend profile survive sessions; the vessel
        contributes identity state. Explicit per-turn friend profiles still win.
        """
        vessel_friend = self.vessel_runtime.friend_profile()
        if vessel_friend.get("friend_id") != "alex":
            return vessel_friend
        authored = self.profiles.load_profile("friend", "alex", fallback_id="alex")
        merged = {**authored, **vessel_friend}
        for key in ("role", "tone", "cadence", "avoid", "boundaries", "principles"):
            merged[key] = list(dict.fromkeys(
                [*authored.get(key, []), *vessel_friend.get(key, [])]
            ))
        merged["mode_policy"] = {
            **authored.get("mode_policy", {}), **vessel_friend.get("mode_policy", {})
        }
        return merged

    def set_byok_manager(self, manager: Any) -> None:
        """Attach the encrypted BYOK store after the main app boots it.

        PubPartner is initialized before the legacy BYOK subsystem in the boot
        order, so this explicit late-binding seam keeps startup dependency-safe.
        """
        self.knowledge.set_byok_manager(manager)
        self.provider_dispatcher.set_byok_manager(manager)

    def _session_path(self, user_id: str, session_id: str) -> Path:
        return self.session_dir / f"{_safe_slug(user_id or 'anon')}_{_safe_slug(session_id or 'default')}.json"

    def _read_session_state(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """Load saved PubPartner session defaults, if present.

        This is intentionally forgiving: a missing or unreadable session file must
        not block a turn. The turn can still run with explicit/default settings.
        """
        path = self._session_path(user_id or "anon", session_id or "default")
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    async def create_session(
        self,
        *,
        user_id: str,
        session_id: Optional[str] = None,
        project_id: str = "default",
        room_id: str = "pubpartner",
        friend: Optional[Dict[str, Any]] = None,
        user_primer: Optional[Dict[str, Any]] = None,
        provider: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        user_id = user_id or "anon"
        session_id = session_id or f"pp_{int(_now() * 1000)}_{uuid.uuid4().hex[:6]}"
        if friend is None and self.vessel_runtime is not None:
            friend = self._default_vessel_friend()
            self.vessel_runtime.ensure_relationship(user_id=user_id)
        friend = self.profiles.resolve_friend(friend)
        if self.vessel_runtime is not None and str(friend.get("friend_id") or friend.get("id")) == "alex" and not (friend.get("self_concept") or friend.get("identity")):
            friend = {**friend, "self_concept": self.vessel_runtime.friend_profile().get("self_concept", "")}
        user_primer = self.profiles.resolve_user(user_id, user_primer)
        provider = self.profiles.resolve_provider(provider)
        profile = FriendProfile.from_payload(friend)
        primer = UserPrimer.from_payload(user_id, user_primer)
        provider_profile = ProviderProfile.from_payload(provider)
        alex_packet = None
        whisper = ""
        if self.alex_bridge is not None:
            alex_packet = self.alex_bridge.build_entry_packet(
                user_id=user_id,
                session_id=session_id,
                project_id=project_id,
                room_id=room_id,
                display_name=profile.display_name,
                metadata={"presence_mode": "pubpartner", "availability": "friend_layer"},
            )
            whisper = self.alex_bridge.jeremy_whisper(user_id=user_id, session_id=session_id)
        state = {
            "session_id": session_id,
            "user_id": user_id,
            "project_id": project_id,
            "room_id": room_id,
            "friend": profile.compact(),
            "user": primer.compact(),
            "provider": provider_profile.compact(),
            "alex_bridge": alex_packet,
            "jeremy_whisper": whisper,
            "created_at": _now(),
        }
        self._write_session_state(user_id, session_id, state)
        await self._jeremy_remember(
            self.memory_scope(user_id, profile.friend_id, project_id, room_id),
            f"PubPartner session {session_id} opened for user {user_id} project {project_id} room {room_id}.",
            memory_type="event",
            importance=4,
            tags=["pubpartner", "session", user_id, project_id],
            source="system",
        )
        return state

    async def build_turn_packet(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
        project_id: str = "default",
        room_id: str = "pubpartner",
        friend: Optional[Dict[str, Any]] = None,
        user_primer: Optional[Dict[str, Any]] = None,
        provider: Optional[Dict[str, Any]] = None,
        task: Optional[Dict[str, Any]] = None,
        output: Optional[Dict[str, Any]] = None,
        safety: Optional[Sequence[str]] = None,
        content_kind: str = "message",
        language: str = DEFAULT_LANGUAGE,
        history: Optional[Sequence[Dict[str, Any]]] = None,
        max_memories: int = 6,
        prompt_mode: str = "auto",
        log_turn: bool = True,
    ) -> Dict[str, Any]:
        user_id = user_id or "anon"
        session_id = session_id or "default"
        session_state = self._read_session_state(user_id, session_id)
        if session_state:
            if project_id == "default":
                project_id = str(session_state.get("project_id") or project_id)
            if room_id == "pubpartner":
                room_id = str(session_state.get("room_id") or room_id)
            friend = friend if friend is not None else session_state.get("friend")
            user_primer = user_primer if user_primer is not None else session_state.get("user")
            provider = provider if provider is not None else session_state.get("provider")
        if friend is None and self.vessel_runtime is not None:
            friend = self._default_vessel_friend()
        friend = self.profiles.resolve_friend(friend)
        if self.vessel_runtime is not None and str(friend.get("friend_id") or friend.get("id")) == "alex" and not (friend.get("self_concept") or friend.get("identity")):
            friend = {**friend, "self_concept": self.vessel_runtime.friend_profile().get("self_concept", "")}
        user_primer = self.profiles.resolve_user(user_id, user_primer)
        provider = self.profiles.resolve_provider(provider)
        profile = FriendProfile.from_payload(friend)
        primer = UserPrimer.from_payload(user_id, user_primer)
        provider_profile = ProviderProfile.from_payload(provider)
        turn_audience = _turn_audience(task, room_id)
        if history is None and turn_audience == "private":
            history = self._saved_private_history(
                user_id=user_id, session_id=session_id, friend_id=profile.friend_id,
            )
        source = self.vault.store(
            user_id=user_id,
            session_id=session_id,
            text=message,
            kind=content_kind,
            language=language or primer.language,
            metadata={"project_id": project_id, "room_id": room_id, "friend_id": profile.friend_id},
        )
        vessel_context: Dict[str, Any] = {}
        vessel_event_id = ""
        if self.vessel_runtime is not None:
            vessel_friend_id = str(
                self.vessel_runtime.friend_profile().get("friend_id") or ""
            )
            if profile.friend_id == vessel_friend_id:
                provider_name = provider_profile.provider.casefold()
                budget_profile = (
                    "small"
                    if provider_name in {"local", "offline", "ollama"}
                    else "medium"
                )
                compiled = self.vessel_runtime.compile_turn(
                    user_id=user_id,
                    message=message,
                    session_id=session_id,
                    room_id=room_id,
                    project_id=project_id,
                    budget_profile=budget_profile,
                    audience=turn_audience,
                )
                vessel_context = compiled.to_dict()
                # Compile from prior evidence first; only then append this exact
                # turn as an uncertain observation. The current sentence cannot
                # therefore retrieve itself as an established memory.
                recorded_event = self.vessel_runtime.record_user_turn(
                    user_id=user_id,
                    message=message,
                    source_ref=source.source_id,
                    source_hash=source.sha256,
                    session_id=session_id,
                    room_id=room_id,
                    literalness=("fictional" if content_kind in {"writing_request", "manuscript", "fiction"} else "uncertain"),
                    visibility=(
                        "private_relationship"
                        if turn_audience == "private"
                        else "room_scoped"
                    ),
                )
                vessel_event_id = str(recorded_event.get("event_id") or "")

        # Jeremy receives a memory pointer, not a lossy rewrite of the user text.
        await self._jeremy_remember(
            self.memory_scope(user_id, profile.friend_id, project_id, room_id),
            f"Exact user turn preserved as {source.source_id} sha256={source.sha256} kind={source.kind}: {_clip(message, 500)}",
            memory_type="event" if source.kind == "message" else "instruction",
            importance=7 if source.kind in _EXACT_TEXT_KINDS else 5,
            tags=["pubpartner", "verbatim", source.kind, user_id, project_id],
            source="conversation",
        )

        memories = await self._jeremy_memories(
            self.memory_scope(user_id, profile.friend_id, project_id, room_id),
            message, history or [], max_memories=max_memories,
        )
        alex_packet = None
        whisper = ""
        if self.alex_bridge is not None:
            try:
                alex_packet = await self.alex_bridge.process_user_turn(
                    user_id=user_id,
                    session_id=session_id,
                    text=message,
                    project_id=project_id,
                    room_id=room_id,
                    metadata={"source_id": source.source_id, "content_kind": source.kind},
                )
            except Exception as exc:
                # A failed Alex analysis must not destroy the user's turn. Fall back
                # to the last safe packet and make the failure visible in receipts.
                alex_packet = self.alex_bridge.current_packet(user_id=user_id, session_id=session_id)
                alex_packet = dict(alex_packet)
                alex_packet["analysis_source"] = "fallback_current_packet"
                alex_packet["analysis_error"] = f"{type(exc).__name__}: {exc}"[:240]
            whisper = self.alex_bridge.jeremy_whisper(user_id=user_id, session_id=session_id)

            # Alex's own remembered content reaches the model only on the user's private
            # audience (same rule as guidance below), selected by relevance to this message.
            if turn_audience == "private" and hasattr(self.alex_bridge, "recalled_for_speaker"):
                try:
                    have = {m.text for m in memories}
                    for row in self.alex_bridge.recalled_for_speaker(
                            user_id=user_id, query=message, limit=min(3, max_memories)):
                        if row["text"] in have:
                            continue
                        memories.append(MemoryRef(
                            id=f"alex:{row['id']}", kind=row["kind"], text=row["text"],
                            importance=6, source="alex_memory"))
                except Exception:
                    pass  # recall is an enrichment; it must never break the turn


        guidance = self.guidance_store.compact(
            user_id=user_id,
            friend_id=profile.friend_id,
            project_id=project_id or "default",
            task=task or {},
            limit=8,
        )
        relationship_guidance = (
            self.relationship.compact(
                user_id=user_id,
                friend_id=profile.friend_id,
                project_id=project_id or "*",
                session_id=session_id or "*",
                query=message,
                limit=8,
            )
            if turn_audience == "private"
            else []
        )
        # Relationship lessons are user-owned guidance derived from explicit
        # encounters. Keep their provenance visible in FCP1 rather than silently
        # blending them into generic profile text.
        guidance = [*relationship_guidance, *guidance][:16]
        packet = FCP1Packet(
            language=language or primer.language,
            user=primer,
            friend=profile,
            provider=provider_profile,
            task=self._task_block(task, source),
            project={"id": project_id or "default", "room": room_id or "pubpartner"},
            safety=list(safety or self._default_safety(source)),
            output=dict(output or {"fmt": "plain", "len": "useful", "lang": language or primer.language}),
            source=source,
            memories=memories,
            alex_packet=alex_packet,
            jeremy_whisper=whisper,
            guidance=guidance,
            vessel_context=vessel_context,
            conversation=[{"role": row["role"], "content": row["content"]} for row in (history or [])],
        )
        prompt_policy = self.prompt_policy(source, prompt_mode=prompt_mode)
        llm_prompt_text = packet.as_compact_text(include_source_text=prompt_policy["include_source_text"])
        llm_prompt_json = packet.as_json(include_source_text=prompt_policy["include_source_text"])
        turn_id = f"turn_{int(_now() * 1000)}_{uuid.uuid4().hex[:8]}"
        result = {
            "ok": True,
            "turn_id": turn_id,
            "source": source.ref(),
            "verbatim_restores": True,
            "fcp1": packet.canonical(include_source_text=True),
            "fcp1_text": packet.as_compact_text(include_source_text=True),
            "fcp1_json": packet.as_json(include_source_text=True),
            "llm_prompt_text": llm_prompt_text,
            "llm_prompt_json": llm_prompt_json,
            "prompt_policy": prompt_policy,
            "token_estimate": self.token_counter.estimate(llm_prompt_text, provider=provider_profile.provider, model=provider_profile.model),
            "full_packet_token_estimate": self.token_counter.estimate(packet.as_compact_text(include_source_text=True), provider=provider_profile.provider, model=provider_profile.model),
            "token_comparison": self.token_counter.compare(llm_prompt_text, packet.as_compact_text(include_source_text=True), provider=provider_profile.provider, model=provider_profile.model),
            "guidance_count": len(guidance),
            "alex_bridge": alex_packet,
            "jeremy_whisper": whisper,
            "memory_count": len(memories),
            "vessel_context_hash": vessel_context.get("context_hash"),
            "vessel_claim_count": len(vessel_context.get("claims") or []),
            "vessel_event_count": len(vessel_context.get("events") or []),
            "vessel_recorded_event_id": vessel_event_id,
        }
        if log_turn:
            self._append_turn(user_id, session_id, result)
        return result

    @serialized_turn
    async def run_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
        project_id: str = "default",
        room_id: str = "pubpartner",
        friend: Optional[Dict[str, Any]] = None,
        user_primer: Optional[Dict[str, Any]] = None,
        provider: Optional[Dict[str, Any]] = None,
        task: Optional[Dict[str, Any]] = None,
        output: Optional[Dict[str, Any]] = None,
        safety: Optional[Sequence[str]] = None,
        content_kind: str = "message",
        language: str = DEFAULT_LANGUAGE,
        history: Optional[Sequence[Dict[str, Any]]] = None,
        max_memories: int = 6,
        prompt_mode: str = "auto",
        allow_fallback: bool = True,
        knowledge: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build an FCP1 turn, dispatch it to a provider, then restore friend voice.

        This is the first real PubPartner live-loop vertebra. It still defaults
        to deterministic/local providers unless a caller supplies a live provider
        configuration. Missing live services are reported honestly and can fall
        back to the offline provider without pretending the requested provider ran.
        """
        turn = await self.build_turn_packet(
            user_id=user_id,
            session_id=session_id,
            message=message,
            project_id=project_id,
            room_id=room_id,
            friend=friend,
            user_primer=user_primer,
            provider=provider,
            task=task,
            output=output,
            safety=safety,
            content_kind=content_kind,
            language=language,
            history=history,
            max_memories=max_memories,
            prompt_mode=prompt_mode,
            log_turn=False,
        )
        knowledge_task = dict(task or {})
        knowledge_task.setdefault("content_kind", content_kind)
        knowledge_result = await self.knowledge.query(
            user_id=user_id or "anon",
            message=message,
            config=knowledge,
            task=knowledge_task,
        )
        turn = self.knowledge.inject_reference(turn, knowledge_result)
        provider_result = await self.provider_dispatcher.dispatch(turn, provider or {})
        provider_fallback: Optional[Dict[str, Any]] = None
        if allow_fallback and not provider_result.ok and provider_result.provider not in {"offline", "mock"}:
            provider_fallback = provider_result.as_dict()
            fallback_config = dict(provider or {})
            fallback_config["provider"] = "offline"
            provider_result = await self.provider_dispatcher.dispatch(turn, fallback_config)
            provider_result.warnings.append("fell back to offline provider after requested provider was unavailable")

        source_policy = ((turn.get("fcp1") or {}).get("source_policy") or {})
        friend_block = ((turn.get("fcp1") or {}).get("f") or {})
        provider_block = ((turn.get("fcp1") or {}).get("norm") or {})
        voice = self.voice_restorer.restore(
            provider_result.raw_response,
            friend=friend_block,
            provider=provider_block,
            source_policy=source_policy,
            provider_result=provider_result.as_dict(),
            current_message=message,
            alex_packet=turn.get("alex_bridge") or {},
            guidance=((turn.get("fcp1") or {}).get("guide") or []),
        )
        live_result = dict(turn)
        receipt = self._live_receipt(
            turn,
            provider_result.as_dict(),
            voice.as_dict(),
            provider_fallback,
            knowledge_result.as_dict(),
        )
        receipt_chain_row = self.receipts.append(user_id=user_id or "anon", session_id=session_id or "default", receipt=receipt)
        live_result.update({
            "live_loop": True,
            "provider_result": provider_result.as_dict(),
            "provider_fallback": provider_fallback,
            "knowledge_result": knowledge_result.as_dict(),
            "raw_response": provider_result.raw_response,
            "friend_response": voice.friend_response,
            "voice_restoration": voice.as_dict(),
            "receipt": receipt,
            "receipt_chain": {"ok": True, "receipt_chain_hash": receipt_chain_row.get("receipt_chain_hash"), "prev_receipt_hash": receipt_chain_row.get("prev_receipt_hash")},
            "provenance": {
                "source_ref": turn["source"],
                "memory_count": turn.get("memory_count", 0),
                "vessel_context_hash": turn.get("vessel_context_hash"),
                "vessel_claim_count": turn.get("vessel_claim_count", 0),
                "vessel_event_count": turn.get("vessel_event_count", 0),
                "provider": provider_result.provider,
                "model": provider_result.model,
                "fallback_used": provider_fallback is not None,
                "knowledge_provider": knowledge_result.provider if knowledge_result.requested else None,
                "knowledge_mode": knowledge_result.mode,
                "knowledge_used": knowledge_result.used_in_prompt,
                "knowledge_privacy_scope": knowledge_result.privacy_scope,
                "prompt_policy": turn.get("prompt_policy"),
                "verbatim_restores": turn.get("verbatim_restores") is True,
            },
        })
        friend_id = str(friend_block.get("id") or friend_block.get("friend_id") or "friend")
        encounter = self.relationship.record_encounter(
            user_id=user_id or "anon",
            friend_id=friend_id,
            session_id=session_id or "default",
            project_id=project_id or "default",
            source_id=str((turn.get("source") or {}).get("id") or ""),
            source_sha256=str((turn.get("source") or {}).get("sha256") or ""),
            user_excerpt=message,
            raw_response=provider_result.raw_response,
            friend_response=voice.friend_response,
            provider=provider_result.provider,
            model=provider_result.model,
            receipt_id=str(receipt.get("receipt_id") or ""),
            guidance_count=int(turn.get("guidance_count") or 0),
            relationship_lesson_ids=[
                str(row.get("id"))
                for row in ((turn.get("fcp1") or {}).get("guide") or [])
                if isinstance(row, dict) and row.get("source") == "relationship" and row.get("id")
            ],
            metadata={
                "fallback_used": provider_fallback is not None,
                "content_kind": content_kind,
                "knowledge_provider": knowledge_result.provider if knowledge_result.requested else None,
                "knowledge_mode": knowledge_result.mode,
                "knowledge_used": knowledge_result.used_in_prompt,
            },
        )
        learned = self.relationship.extract_explicit_lessons(
            user_id=user_id or "anon",
            friend_id=friend_id,
            text=message,
            encounter_id=str(encounter.get("encounter_id") or ""),
            project_id=project_id or "*",
            session_id=session_id or "*",
        ) if content_kind not in {"writing_request", "manuscript", "fiction"} else []
        vessel_learning: List[Dict[str, Any]] = []
        vessel_learning_errors: List[Dict[str, str]] = []
        if (
            self.vessel_runtime is not None
            and str(turn.get("vessel_recorded_event_id") or "")
            and friend_id
            == str(self.vessel_runtime.friend_profile().get("friend_id") or "")
        ):
            for lesson in learned:
                try:
                    vessel_learning.append(
                        self.vessel_runtime.ingest_explicit_lesson(
                            user_id=user_id or "anon",
                            event_id=str(turn["vessel_recorded_event_id"]),
                            lesson=lesson,
                        )
                    )
                except Exception as exc:
                    vessel_learning_errors.append(
                        {
                            "lesson_id": str(lesson.get("lesson_id") or ""),
                            "error": f"{type(exc).__name__}: {exc}"[:300],
                        }
                    )
        live_result["relationship"] = {
            "encounter_id": encounter.get("encounter_id"),
            "encounter_hash": encounter.get("encounter_hash"),
            "applied_lessons": [
                row for row in ((turn.get("fcp1") or {}).get("guide") or [])
                if isinstance(row, dict) and row.get("source") == "relationship"
            ],
            "learned_lessons": learned,
            "learning_mode": "explicit_user_signals_only",
            "vessel_claims": vessel_learning,
            "vessel_sync_errors": vessel_learning_errors,
        }
        self._append_turn(user_id or "anon", session_id or "default", live_result)
        if self.blackbox_witness is not None:
            live_result['blackbox_committed'] = bool(self.blackbox_witness.record_event(
                'partner.private_turn', source='pubpartner', actor=user_id,
                data={'session_id': session_id, 'room_id': room_id,
                      'message': message, 'reply': live_result.get('friend_response', ''),
                      'receipt_id': receipt.get('receipt_id'), 'provider_ok': provider_result.ok}))
        return live_result

    def _live_receipt(
        self,
        turn: Dict[str, Any],
        provider_result: Dict[str, Any],
        voice_result: Dict[str, Any],
        provider_fallback: Optional[Dict[str, Any]],
        knowledge_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raw = str(provider_result.get("raw_response") or "")
        friend_response = str(voice_result.get("friend_response") or "")
        prompt = str(turn.get("llm_prompt_text") or "")
        return {
            "event": "pubpartner.turn.live",
            "receipt_id": f"rcpt_{int(_now() * 1000)}_{uuid.uuid4().hex[:8]}",
            "turn_id": turn.get("turn_id"),
            "ts": _now(),
            "source_id": (turn.get("source") or {}).get("id"),
            "source_sha256": (turn.get("source") or {}).get("sha256"),
            "prompt_sha256": _sha256_text(prompt),
            "raw_response_sha256": _sha256_text(raw),
            "friend_response_sha256": _sha256_text(friend_response),
            "personalization": {
                "applied": bool(voice_result.get("personalization_applied", True)),
                "change_level": voice_result.get("change_level", "unknown"),
                "reason": voice_result.get("reason", ""),
                "rules_used": list(voice_result.get("rules_used") or []),
                "protected_text_preserved": bool(voice_result.get("protected_text_preserved", True)),
                "warnings": list(voice_result.get("warnings") or []),
            },
            "alex_analysis": {
                "source": ((turn.get("alex_bridge") or {}).get("analysis_source")),
                "state": ((turn.get("alex_bridge") or {}).get("alex_state")),
                "processing_time_ms": ((turn.get("alex_bridge") or {}).get("processing_time_ms")),
                "private_memory_context_withheld": bool((turn.get("alex_bridge") or {}).get("private_memory_context_withheld")),
            },
            "provider": provider_result.get("provider"),
            "model": provider_result.get("model"),
            "provider_ok": provider_result.get("ok"),
            "fallback_used": provider_fallback is not None,
            "knowledge": {
                "requested": bool((knowledge_result or {}).get("requested")),
                "provider": (knowledge_result or {}).get("provider"),
                "model": (knowledge_result or {}).get("model"),
                "mode": (knowledge_result or {}).get("mode"),
                "used_in_prompt": bool((knowledge_result or {}).get("used_in_prompt")),
                "ok": bool((knowledge_result or {}).get("ok")),
                "text_sha256": (knowledge_result or {}).get("text_sha256"),
                "privacy_scope": (knowledge_result or {}).get("privacy_scope"),
            },
            "token_estimate": turn.get("token_estimate"),
            "prompt_policy": turn.get("prompt_policy"),
            "verbatim_restores": turn.get("verbatim_restores") is True,
            "vessel_context_hash": turn.get("vessel_context_hash"),
            "vessel_claim_count": turn.get("vessel_claim_count", 0),
            "vessel_event_count": turn.get("vessel_event_count", 0),
        }

    def restore_source(self, *, user_id: str, session_id: str, source_id: str) -> Dict[str, Any]:
        rec = self.vault.load(user_id=user_id, session_id=session_id, source_id=source_id)
        return {
            "ok": True,
            "source": rec.ref(),
            "text": rec.text,
            "language": rec.language,
            "metadata": rec.metadata,
            "integrity": rec.integrity(),
        }

    def restore_source_span(
        self,
        *,
        user_id: str,
        session_id: str,
        source_id: str,
        start: int = 0,
        end: Optional[int] = None,
    ) -> Dict[str, Any]:
        rec = self.vault.load(user_id=user_id, session_id=session_id, source_id=source_id)
        text_len = len(rec.text)
        start = max(0, min(int(start), text_len))
        end = text_len if end is None else max(start, min(int(end), text_len))
        span = rec.text[start:end]
        return {
            "ok": True,
            "source": rec.ref(),
            "span": {
                "start": start,
                "end": end,
                "chars": len(span),
                "sha256": _sha256_text(span),
                "text": span,
                "restore_policy": "verbatim_slice_from_immutable_source",
            },
        }

    def verify_quote(
        self,
        *,
        user_id: str,
        session_id: str,
        source_id: str,
        quote: str,
        normalize_newlines: bool = False,
    ) -> Dict[str, Any]:
        if not isinstance(quote, str):
            raise TypeError("quote must be a string")
        rec = self.vault.load(user_id=user_id, session_id=session_id, source_id=source_id)
        haystack = rec.text
        needle = quote
        if normalize_newlines:
            haystack = haystack.replace("\r\n", "\n").replace("\r", "\n")
            needle = needle.replace("\r\n", "\n").replace("\r", "\n")
        spans: List[Dict[str, Any]] = []
        if needle:
            start = 0
            while True:
                idx = haystack.find(needle, start)
                if idx < 0:
                    break
                end = idx + len(needle)
                spans.append({
                    "start": idx,
                    "end": end,
                    "chars": len(needle),
                    "sha256": _sha256_text(needle),
                })
                start = idx + 1
        return {
            "ok": bool(spans),
            "source": rec.ref(),
            "quote_sha256": _sha256_text(quote),
            "exact_match": bool(spans) and not normalize_newlines,
            "normalized_newlines": bool(normalize_newlines),
            "matches": spans,
            "match_count": len(spans),
            "policy": "quote is display-safe only if ok=true and exact_match=true, otherwise restore source span or ask user",
        }

    def session_sources(self, *, user_id: str, session_id: str, limit: int = 50) -> Dict[str, Any]:
        return {
            "ok": True,
            "sources": self.vault.list_session(user_id=user_id, session_id=session_id, limit=limit),
            "audit": self.vault.verify_session_audit(user_id=user_id, session_id=session_id),
        }

    def verify_session(self, *, user_id: str, session_id: str) -> Dict[str, Any]:
        return self.vault.verify_session_audit(user_id=user_id, session_id=session_id)


    async def launch_check(self) -> Dict[str, Any]:
        """Pre-flight report for turning PubPartner on locally.

        This does not claim live cloud providers work. It proves the local friend
        loop has the required pieces and reports unavailable providers honestly.
        """
        providers = await self.provider_dispatcher.status("all")
        friend_profiles = self.profiles.list_profiles("friend").get("profiles", [])
        user_profiles = self.profiles.list_profiles("user").get("profiles", [])
        ui_path = Path("static") / "pubpartner.html"
        checks = {
            "verbatim_vault": self.vault.root.exists(),
            "session_store": self.session_dir.exists(),
            "guidance_store": self.guidance_store.root.exists(),
            "receipt_store": self.receipts.root.exists(),
            "relationship_store": self.relationship.root.exists(),
            "backup_module": (Path(__file__).with_name("pubpartner_backup.py")).exists(),
            "friend_profiles_seeded": bool(friend_profiles),
            "user_profiles_seeded": bool(user_profiles),
            "mock_provider_available": providers.get("providers", {}).get("mock", {}).get("available") is True,
            "offline_provider_available": providers.get("providers", {}).get("offline", {}).get("available") is True,
            "ui_file_present": ui_path.exists(),
            "alex_bridge_hook": self.alex_bridge is not None,
            "jeremy_cricket_hook": self.cricket_keeper is not None,
        }
        required = [
            "verbatim_vault", "session_store", "guidance_store", "receipt_store",
            "relationship_store", "backup_module",
            "friend_profiles_seeded", "user_profiles_seeded",
            "mock_provider_available", "offline_provider_available", "ui_file_present",
        ]
        return {
            "ok": all(checks.get(k) for k in required),
            "mode": "local_activation_preflight",
            "checks": checks,
            "providers": providers,
            "friend_profiles": [p.get("id") for p in friend_profiles],
            "user_profiles": [p.get("id") for p in user_profiles],
            "ui": "/pubpartner",
            "notes": [
                "mock/offline providers are enough to turn on the local friend loop",
                "openai/ollama are optional until configured and tested",
                "exact source text remains in VerbatimVault and is restored by source id",
                "explicit relationship lessons are reviewable, portable, and provider-independent",
                "friend backups exclude provider keys and runtime secrets",
            ],
        }

    def _saved_private_history(self, *, user_id: str, session_id: str,
                               friend_id: str, exchanges: int = 4) -> List[Dict[str, str]]:
        """Resume an authenticated friend's completed private dialogue from disk.

        Only completed real-provider replies are conversation history. Exact user
        turns come back from the existing VerbatimVault, not stripped JSON logs.
        We intentionally do not import private chat into shared/public rooms.
        """
        try:
            turns = self.list_turns(user_id=user_id, session_id=session_id, limit=40)["turns"]
        except (OSError, ValueError, KeyError):
            return []
        pairs: List[List[Dict[str, str]]] = []
        for row in reversed(turns):
            if not isinstance(row, dict):
                continue
            fcp1 = row.get("fcp1") or {}
            if not isinstance(fcp1, dict):
                continue
            saved_friend = (fcp1.get("f") or {}).get("id")
            saved_project = fcp1.get("proj") or {}
            if saved_friend != friend_id or _turn_audience(fcp1.get("task"), str(saved_project.get("room") or "")) != "private":
                continue
            provider = row.get("provider_result") or {}
            if provider.get("ok") is not True or provider.get("provider") in {"mock", "echo", "offline"}:
                continue
            reply = row.get("friend_response")
            source_id = (row.get("source") or {}).get("id")
            if not isinstance(reply, str) or not reply.strip() or not isinstance(source_id, str):
                continue
            try:
                original = self.vault.load(user_id=user_id, session_id=session_id, source_id=source_id)
                user_text = original.text
            except (OSError, ValueError, KeyError, FileNotFoundError):
                continue
            pairs.append([
                {"role": "user", "content": _clip(user_text, 700)},
                {"role": "assistant", "content": _clip(reply, 900)},
            ])
            if len(pairs) >= exchanges:
                break
        return [entry for pair in reversed(pairs) for entry in pair]

    def list_turns(self, *, user_id: str, session_id: str, limit: int = 50) -> Dict[str, Any]:
        path = self.session_dir / f"{_safe_slug(user_id)}_{_safe_slug(session_id)}_turns.jsonl"
        rows: List[Dict[str, Any]] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    rows.append({"error": "invalid turn log row"})
        return {"ok": True, "turns": rows[-max(1, min(500, int(limit))):]}

    def list_profiles(self, kind: str) -> Dict[str, Any]:
        return self.profiles.list_profiles(kind)

    def load_profile(self, kind: str, profile_id: str) -> Dict[str, Any]:
        return {"ok": True, "kind": kind, "profile": self.profiles.load_profile(kind, profile_id, fallback_id="friend" if kind == "friend" else ("anon" if kind == "user" else "mock"))}

    def save_profile(self, kind: str, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.profiles.save_profile(kind, profile_id, payload)

    def add_guidance(self, **kwargs: Any) -> Dict[str, Any]:
        return self.guidance_store.add(**kwargs)

    def list_guidance(self, *, user_id: str, friend_id: str = "*", project_id: str = "*", limit: int = 100) -> Dict[str, Any]:
        return self.guidance_store.list(user_id=user_id, friend_id=friend_id, project_id=project_id, limit=limit)

    def list_receipts(self, *, user_id: str, session_id: str, limit: int = 50) -> Dict[str, Any]:
        return self.receipts.list(user_id=user_id, session_id=session_id, limit=limit)

    def verify_receipts(self, *, user_id: str, session_id: str) -> Dict[str, Any]:
        return self.receipts.verify(user_id=user_id, session_id=session_id)

    def relationship_summary(self, *, user_id: str, friend_id: str, project_id: str = "*", session_id: str = "*") -> Dict[str, Any]:
        return self.relationship.summary(user_id=user_id, friend_id=friend_id, project_id=project_id, session_id=session_id)

    def list_relationship_lessons(self, *, user_id: str, friend_id: str, status: str = "all", project_id: str = "*", session_id: str = "*", limit: int = 200) -> Dict[str, Any]:
        return self.relationship.list_lessons(user_id=user_id, friend_id=friend_id, status=status, project_id=project_id, session_id=session_id, limit=limit)

    def update_relationship_lesson(self, *, user_id: str, friend_id: str, lesson_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        return self.relationship.update_lesson(user_id=user_id, friend_id=friend_id, lesson_id=lesson_id, patch=patch)

    def add_relationship_lesson(self, **kwargs: Any) -> Dict[str, Any]:
        return self.relationship.add_lesson(**kwargs)

    def list_relationship_encounters(self, *, user_id: str, friend_id: str, limit: int = 100) -> Dict[str, Any]:
        return self.relationship.list_encounters(user_id=user_id, friend_id=friend_id, limit=limit)

    def estimate_prompt_tokens(self, *, text: str, provider: str = "generic", model: str = "unknown") -> Dict[str, Any]:
        return {"ok": True, "token_estimate": self.token_counter.estimate(text, provider=provider, model=model)}

    @staticmethod
    def prompt_policy(source: SourceRecord, *, prompt_mode: str = "auto") -> Dict[str, Any]:
        """Choose whether the outgoing LLM prompt should carry full source text.

        `fcp1_text` always remains available as a full debug/proof packet. This
        policy only controls the token-conscious prompt intended for the engine.
        Exact artifacts are included when small enough; long artifacts travel by
        reference unless a caller explicitly requests `full`.
        """
        mode = (prompt_mode or "auto").lower().strip()
        if mode in {"full", "include", "include_source_text"}:
            return {"mode": "full", "include_source_text": True, "reason": "caller_requested_full_source_text"}
        if mode in {"ref", "ref_only", "omit"}:
            return {"mode": "ref_only", "include_source_text": False, "reason": "caller_requested_ref_only", "requires_restore_before_quote": True}
        exact = source.kind in _EXACT_TEXT_KINDS or source.kind != "message"
        if source.char_len <= MAX_COMPACT_MESSAGE_CHARS:
            return {"mode": "auto_small", "include_source_text": True, "reason": "small_source_needed_for_turn"}
        if exact and source.char_len <= MAX_FULL_PROMPT_TEXT_CHARS:
            return {"mode": "auto_exact_full", "include_source_text": True, "reason": "exact_artifact_small_enough_for_direct_work"}
        return {
            "mode": "auto_ref_only",
            "include_source_text": False,
            "reason": "source_too_large_for_token_light_prompt",
            "requires_restore_before_quote": True,
            "recommendation": "retrieve targeted spans from VerbatimVault before asking model to edit or quote",
        }

    @staticmethod
    def estimate_tokens(text: str) -> Dict[str, Any]:
        # Conservative no-dependency estimator; provider token APIs should replace
        # this during dispatch. Kept here so tests and offline mode have a budget.
        utf8 = text.encode("utf-8")
        rough = max(1, int(len(text) / 4))
        return {"provider": "rough_local", "estimated_tokens": rough, "chars": len(text), "bytes": len(utf8)}

    def memory_scope(self, user_id: str, friend_id: str, project_id: str, room_id: str) -> str:
        if not self.scoped_memory:
            return friend_id
        # Integrated hosts isolate relationship/project memories. Historical
        # character-wide stores are preserved; attribution is needed to import.
        key = json.dumps([user_id, friend_id, project_id, room_id], ensure_ascii=False)
        return "pp_" + _sha256_text(key)[:48]

    async def _jeremy_remember(
        self,
        friend_id: str,
        content: str,
        *,
        memory_type: str = "event",
        importance: int = 5,
        tags: Optional[List[str]] = None,
        source: str = "system",
    ) -> int:
        if self.cricket_keeper is None:
            return -1
        try:
            cricket = await self.cricket_keeper.get(friend_id or "friend")
            mtype = JeremyMemoryType(memory_type) if JeremyMemoryType is not None else memory_type
            return await cricket.remember(content, memory_type=mtype, importance=importance, tags=tags or [], source=source)
        except Exception:
            return -1

    async def _jeremy_memories(
        self,
        friend_id: str,
        prompt: str,
        history: Sequence[Dict[str, Any]],
        *,
        max_memories: int,
    ) -> List[MemoryRef]:
        if self.cricket_keeper is None:
            return []
        try:
            cricket = await self.cricket_keeper.get(friend_id or "friend")
            recalled = await cricket.recall(prompt, max_results=max_memories, min_importance=3)
            refs: List[MemoryRef] = []
            for mem in recalled:
                refs.append(MemoryRef(
                    id=f"jeremy:{mem.id}",
                    kind=getattr(mem.memory_type, "value", str(mem.memory_type)),
                    text=mem.content,
                    importance=int(mem.importance),
                    source=mem.source,
                ))
            return refs
        except Exception:
            return []

    def _task_block(self, task: Optional[Dict[str, Any]], source: SourceRecord) -> Dict[str, Any]:
        base = dict(task or {})
        base.setdefault("mode", "friend_chat")
        base.setdefault("goal", "answer_as_recognizable_friend")
        guards = _string_list(base.get("guard") or [])
        guards.extend(["preserve_user_intent", "no_fake_memory"])
        if source.kind in _EXACT_TEXT_KINDS or source.kind != "message":
            guards.append("do_not_alter_exact_text")
            guards.append("quote_only_from_msg_ref")
        base["guard"] = _string_list(guards, limit=20)
        return base

    def _default_safety(self, source: SourceRecord) -> List[str]:
        rules = [
            "privacy_first",
            "no_fake_memories",
            "distinguish_source_text_from_summary",
            "do_not_claim_llm_work_is_done_without_proof",
        ]
        if source.kind in _EXACT_TEXT_KINDS or source.kind != "message":
            rules.extend([
                "immutable_source_text: never paraphrase when quoting",
                "derived summaries must cite msg_ref and cannot replace original",
            ])
        return rules

    def _message_looks_stressed(self, text: str) -> bool:
        lower = text.lower()
        return any(token in lower for token in ("fuck", "pissed", "tired", "angry", "panic", "overwhelmed", "can't", "cant"))

    def _write_session_state(self, user_id: str, session_id: str, state: Dict[str, Any]) -> None:
        path = self._session_path(user_id, session_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _append_turn(self, user_id: str, session_id: str, turn: Dict[str, Any]) -> None:
        path = self.session_dir / f"{_safe_slug(user_id)}_{_safe_slug(session_id)}_turns.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        light = dict(turn)
        # Turn logs are pointers/provenance, not another verbatim text store.
        # The exact source lives in VerbatimVault. This prevents long lyrics/code/legal
        # artifacts from being silently duplicated in session JSONL.
        if isinstance(light.get("fcp1"), dict):
            light["fcp1"] = json.loads(json.dumps(light["fcp1"], ensure_ascii=False))
            msg = light["fcp1"].get("msg") if isinstance(light["fcp1"], dict) else None
            if isinstance(msg, dict) and "text" in msg:
                msg.pop("text", None)
                msg["text_status"] = "omitted_turn_log_ref_only"
                msg["note"] = "Exact source text lives only in VerbatimVault; restore by msg.ref.id."
        if "fcp1_text" in light:
            light["fcp1_text"] = _clip(light["fcp1_text"], 4000)
        if "fcp1_json" in light:
            light["fcp1_json"] = _clip(light["fcp1_json"], 4000)
        if "llm_prompt_text" in light:
            light["llm_prompt_text"] = _clip(light["llm_prompt_text"], 4000)
        if "llm_prompt_json" in light:
            light["llm_prompt_json"] = _clip(light["llm_prompt_json"], 4000)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(light, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
