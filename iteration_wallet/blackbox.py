"""Iteration Wallet BlackBox evidence chain.

BlackBox records custody events, protected-action decisions, incident bundles,
and Human Intent receipts in one local tamper-evident chain. It is not external
cryptographic sealing; it is deterministic local evidence that can be inspected
and verified without network access.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class BlackBoxError(RuntimeError):
    """Raised for expected BlackBox evidence failures."""


class BlackBox:
    """Local hash-chained evidence store."""

    def __init__(self, vault_root: str | Path):
        self.vault_root = Path(vault_root)
        self.blackbox_dir = self.vault_root / "blackbox"
        self.event_dir = self.blackbox_dir / "events"
        self.incident_dir = self.blackbox_dir / "incidents"
        self.request_dir = self.blackbox_dir / "requests"
        self.receipt_dir = self.blackbox_dir / "receipts"
        self.chain_file = self.blackbox_dir / "chain_head.json"
        for directory in (self.blackbox_dir, self.event_dir, self.incident_dir, self.request_dir, self.receipt_dir):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _canonical_json(data: Dict[str, Any]) -> str:
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _current_chain_state(self) -> tuple[str, int]:
        if not self.chain_file.exists():
            return "GENESIS", 0
        try:
            data = json.loads(self.chain_file.read_text(encoding="utf-8"))
            return str(data.get("event_hash") or "GENESIS"), int(data.get("chain_index", 0))
        except Exception:
            return "GENESIS", 0

    def current_chain_head(self) -> str:
        return self._current_chain_state()[0]

    def write_event(self, event_type: str, summary: str, **extra: Any) -> Dict[str, Any]:
        """Write a hash-chained BlackBox event."""
        event_id = uuid.uuid4().hex[:16]
        previous_hash, previous_index = self._current_chain_state()
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "summary": summary,
            "created_at": self.now().isoformat(),
            "previous_event_hash": previous_hash,
            "chain_index": previous_index + 1,
            **extra,
        }
        event_hash = hashlib.sha256((previous_hash + self._canonical_json(event)).encode("utf-8")).hexdigest()
        event["event_hash"] = event_hash
        self._write_json_atomic(self.event_dir / f"{event_id}.json", event)
        self._write_json_atomic(
            self.chain_file,
            {"event_id": event_id, "event_hash": event_hash, "chain_index": event["chain_index"], "updated_at": event["created_at"]},
        )
        return event

    def iter_events(self) -> Iterable[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for path in self.event_dir.glob("*.json"):
            try:
                events.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception as exc:
                raise BlackBoxError(f"unreadable event {path.name}: {exc}") from exc
        events.sort(key=lambda item: (int(item.get("chain_index", 0)), item.get("created_at", ""), item.get("event_id", "")))
        return events

    def verify_chain(self) -> Dict[str, Any]:
        try:
            events = list(self.iter_events())
        except BlackBoxError as exc:
            return {"ok": False, "reason": str(exc)}
        previous = "GENESIS"
        expected_index = 1
        for event in events:
            if int(event.get("chain_index", 0)) != expected_index:
                return {"ok": False, "reason": "chain index gap", "event_id": event.get("event_id")}
            if event.get("previous_event_hash") != previous:
                return {"ok": False, "reason": "broken previous hash", "event_id": event.get("event_id")}
            payload = dict(event)
            supplied = payload.pop("event_hash", None)
            expected = hashlib.sha256((previous + self._canonical_json(payload)).encode("utf-8")).hexdigest()
            if supplied != expected:
                return {"ok": False, "reason": "event hash mismatch", "event_id": event.get("event_id")}
            previous = str(supplied)
            expected_index += 1
        return {"ok": True, "event_count": len(events), "chain_head": previous}

    @staticmethod
    def incident_key(*parts: Optional[str]) -> str:
        raw = "|".join(str(part or "") for part in parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def update_request_incident_bundle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        incident_id = self.incident_key(request.get("vault_id"), request.get("object_id"), request.get("action"), request.get("requester_id"), request.get("tool_family"))
        path = self.incident_dir / f"{incident_id}.json"
        if path.exists():
            try:
                incident = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                incident = {}
        else:
            incident = {"incident_id": incident_id, "incident_type": "BOT_REQUEST_PRESSURE", "created_at": self.now().isoformat(), "raw_request_ids": []}
        incident.update({
            "updated_at": self.now().isoformat(),
            "vault_id": request.get("vault_id"),
            "object_id": request.get("object_id"),
            "action": request.get("action"),
            "requester_id": request.get("requester_id"),
            "tool_family": request.get("tool_family"),
            "classification": str(request.get("classification") or "normal"),
            "status": request.get("status"),
            "matching_request_count": int(request.get("matching_request_count") or 0),
        })
        incident.setdefault("raw_request_ids", []).append(request.get("request_id"))
        incident["summary"] = "Repeated protected access pressure"
        self._write_json_atomic(path, incident)
        self.write_event("REQUEST_INCIDENT_BUNDLE_UPDATED", incident["summary"], incident=incident)
        return incident

    def issue_human_intent_receipt(
        self,
        *,
        action_key: str,
        action_label: str,
        actor_id: str = "local-human",
        actor_kind: str = "human",
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        section_id: Optional[str] = None,
        object_id: Optional[str] = None,
        object_name: Optional[str] = None,
        custody_state: Optional[str] = None,
        result_summary: str = "",
        decision: str = "approved",
        linked_event_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write a durable receipt for a protected human-intent decision."""
        if actor_kind != "human":
            raise BlackBoxError("Human Intent receipts can only be issued for human actors")
        receipt_id = uuid.uuid4().hex[:16]
        payload = {
            "receipt_id": receipt_id,
            "receipt_type": "human_intent",
            "action_key": action_key,
            "action_label": action_label,
            "actor_id": actor_id,
            "actor_kind": actor_kind,
            "session_id": session_id,
            "project_id": project_id,
            "section_id": section_id,
            "object_id": object_id,
            "object_name": object_name,
            "custody_state": custody_state,
            "decision": decision,
            "result_summary": result_summary,
            "linked_event_hash": linked_event_hash or self.current_chain_head(),
            "metadata": metadata or {},
            "created_at": self.now().isoformat(),
            "raw_tokens_exposed": False,
            "protected_paths_exposed": False,
        }
        payload["receipt_hash"] = hashlib.sha256(self._canonical_json(payload).encode("utf-8")).hexdigest()
        self._write_json_atomic(self.receipt_dir / f"{receipt_id}.json", payload)
        event = self.write_event(
            "HUMAN_INTENT_RECEIPT_ISSUED",
            f"Human Intent receipt issued for {action_key}",
            receipt_id=receipt_id,
            receipt_hash=payload["receipt_hash"],
            action_key=action_key,
            decision=decision,
            project_id=project_id,
            section_id=section_id,
            object_id=object_id,
        )
        payload["blackbox_event_id"] = event.get("event_id")
        payload["blackbox_event_hash"] = event.get("event_hash")
        self._write_json_atomic(self.receipt_dir / f"{receipt_id}.json", payload)
        return payload

    def iter_receipts(self) -> Iterable[Dict[str, Any]]:
        receipts: List[Dict[str, Any]] = []
        for path in self.receipt_dir.glob("*.json"):
            try:
                receipts.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception as exc:
                raise BlackBoxError(f"unreadable receipt {path.name}: {exc}") from exc
        receipts.sort(key=lambda item: (item.get("created_at", ""), item.get("receipt_id", "")))
        return receipts

    def verify_receipts(self) -> Dict[str, Any]:
        try:
            receipts = list(self.iter_receipts())
        except BlackBoxError as exc:
            return {"ok": False, "reason": str(exc)}
        for receipt in receipts:
            payload = dict(receipt)
            supplied = payload.pop("receipt_hash", None)
            payload.pop("blackbox_event_id", None)
            payload.pop("blackbox_event_hash", None)
            expected = hashlib.sha256(self._canonical_json(payload).encode("utf-8")).hexdigest()
            if supplied != expected:
                return {"ok": False, "reason": "receipt hash mismatch", "receipt_id": receipt.get("receipt_id")}
            if receipt.get("raw_tokens_exposed") is not False or receipt.get("protected_paths_exposed") is not False:
                return {"ok": False, "reason": "receipt exposes protected material", "receipt_id": receipt.get("receipt_id")}
        return {"ok": True, "receipt_count": len(receipts)}

    def write_custody_event(self, event_type: str, summary: str, *, project_id: Optional[str] = None, section_id: Optional[str] = None, file_id: Optional[str] = None, state: Optional[str] = None, **extra: Any) -> Dict[str, Any]:
        return self.write_event(event_type, summary, project_id=project_id, section_id=section_id, file_id=file_id, state=state, custody_event=True, **extra)

    def write_violation_event(self, violation_type: str, summary: str, **extra: Any) -> Dict[str, Any]:
        return self.write_event(violation_type, summary, custody_violation=True, possible_intrusion=True, **extra)

    def build_report(self, limit: int = 100) -> Dict[str, Any]:
        events = list(self.iter_events())[-limit:]
        incidents = []
        for path in self.incident_dir.glob("*.json"):
            try:
                incidents.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return {
            "summary": "BlackBox custody evidence report",
            "generated_at": self.now().isoformat(),
            "event_count_included": len(events),
            "events": events,
            "incident_bundles": sorted(incidents, key=lambda item: item.get("updated_at", "")),
            "chain": self.verify_chain(),
            "receipts": self.verify_receipts(),
        }


__all__ = ["BlackBox", "BlackBoxError"]
