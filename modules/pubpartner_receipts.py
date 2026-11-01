"""BlackBox-lite PubPartner receipt chain.

This is not the full Oubliette/BlackBox runtime. It is a deterministic custody
ledger for PubPartner live turns so later integration has something real to
verify instead of vibes.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List


def _hash_payload(payload: Dict[str, Any]) -> str:
    core = dict(payload)
    core.pop("receipt_chain_hash", None)
    return hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class PubPartnerReceiptStore:
    def __init__(self, data_dir: Path):
        self.root = Path(data_dir) / "pubpartner" / "receipts"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str, session_id: str) -> Path:
        safe = lambda s: "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(s or "anon"))[:120]
        return self.root / f"{safe(user_id)}_{safe(session_id)}.jsonl"

    def last_hash(self, user_id: str, session_id: str) -> str:
        path = self._path(user_id, session_id)
        last = "GENESIS"
        if not path.exists():
            return last
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                last = json.loads(line).get("receipt_chain_hash") or last
            except Exception:
                return "UNREADABLE_RECEIPT_CHAIN"
        return last

    def append(self, *, user_id: str, session_id: str, receipt: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(receipt or {})
        payload.setdefault("event", "pubpartner.turn.live")
        payload.setdefault("ts", time.time())
        payload["user_id"] = user_id or "anon"
        payload["session_id"] = session_id or "default"
        payload["prev_receipt_hash"] = self.last_hash(user_id, session_id)
        payload["receipt_chain_hash"] = _hash_payload(payload)
        with self._path(user_id, session_id).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        return payload

    def list(self, *, user_id: str, session_id: str, limit: int = 50) -> Dict[str, Any]:
        path = self._path(user_id, session_id)
        rows: List[Dict[str, Any]] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        rows.append({"error": "invalid receipt row"})
        return {"ok": True, "receipts": rows[-max(1, min(500, int(limit))):], "verify": self.verify(user_id=user_id, session_id=session_id)}

    def verify(self, *, user_id: str, session_id: str) -> Dict[str, Any]:
        path = self._path(user_id, session_id)
        if not path.exists():
            return {"ok": True, "entries": 0, "last_hash": "GENESIS"}
        prev = "GENESIS"
        entries = 0
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception as exc:
                return {"ok": False, "line": lineno, "error": f"invalid json: {exc}"}
            if payload.get("prev_receipt_hash") != prev:
                return {"ok": False, "line": lineno, "error": "receipt chain break", "expected_prev": prev}
            expected = _hash_payload(payload)
            if payload.get("receipt_chain_hash") != expected:
                return {"ok": False, "line": lineno, "error": "receipt hash mismatch"}
            prev = str(payload.get("receipt_chain_hash"))
            entries += 1
        return {"ok": True, "entries": entries, "last_hash": prev}
