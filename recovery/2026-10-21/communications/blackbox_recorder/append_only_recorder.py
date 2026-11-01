"""Append-only recorder for compact BlackBox records."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Mapping

from blackbox_event_language.schema import (
    ZERO_HASH,
    BlackBoxRecord,
    BlackBoxValidationError,
    decode_record,
    encode_record,
    parse_record,
)


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    checked: int
    errors: List[str]


class AppendOnlyBlackBoxRecorder:
    """Tiny append-only recorder with hash chaining and crash-position support."""

    def __init__(self, path: Path | str, session_id: str, compute_budget_percent: float = 3.0):
        self._lock = threading.RLock()
        self.path = Path(path)
        self.session_id = str(session_id)
        self.compute_budget_percent = float(compute_budget_percent)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        self._previous_hash = ZERO_HASH
        if self.path.exists() and self.path.stat().st_size:
            self._restore_tail()

    def _restore_tail(self) -> None:
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return
        last = decode_record(lines[-1])
        self._seq = int(last["seq"]) + 1
        self._previous_hash = str(last["hash"])

    @property
    def next_seq(self) -> int:
        return self._seq

    @property
    def previous_hash(self) -> str:
        return self._previous_hash

    def append(
        self,
        *,
        ch: str,
        src: str,
        act: str,
        ev: str,
        cov: str,
        payload: Mapping[str, Any] | str | None = None,
    ) -> str:
        with self._lock:
            return self._append_locked(ch=ch, src=src, act=act, ev=ev, cov=cov, payload=payload)

    def _append_locked(self, *, ch, src, act, ev, cov, payload=None):
        started = perf_counter()
        record = BlackBoxRecord(
            seq=self._seq,
            ch=ch,
            src=src,
            act=act,
            ev=ev,
            cov=cov,
            sid=self.session_id,
            rid=f"{self.session_id}:{self._seq}",
            ph=self._previous_hash,
            payload=payload,
        )
        wire = encode_record(record)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(wire + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        decoded = decode_record(wire)
        self._previous_hash = decoded["hash"]
        self._seq += 1
        elapsed_ms = (perf_counter() - started) * 1000
        if elapsed_ms > 8 and ch != "ACC":
            self.append_budget_pressure(elapsed_ms)
        return wire

    def access(self, actor: str, access: str, scope: str, reason: str = "") -> str:
        return self.append(
            ch="ACC",
            src="BBX",
            act=actor,
            ev="ACS",
            cov="F",
            payload={"access": access, "scope": scope, "reason": reason or "-"},
        )

    def append_budget_pressure(self, elapsed_ms: float) -> str:
        return self.append(
            ch="PER",
            src="BBX",
            act="SYS",
            ev="BPR",
            cov="S",
            payload={
                "target_pct": self.compute_budget_percent,
                "append_ms": f"{elapsed_ms:.3f}",
                "degrade": "sample_low_priority",
            },
        )

    def crash_position(self, signal: str, known: Mapping[str, Any] | None = None) -> List[str]:
        """Record crash-position initiation and a compact final known-state snapshot."""

        records = [
            self.append(
                ch="CRS",
                src="BBX",
                act="SYS",
                ev="CPI",
                cov="F",
                payload={"signal": signal, "last_seq": max(0, self._seq - 1)},
            )
        ]
        snapshot: Dict[str, Any] = dict(known or {})
        snapshot.setdefault("flush", "attempted")
        records.append(
            self.append(
                ch="CRS",
                src="BBX",
                act="SYS",
                ev="CPS",
                cov="P",
                payload=snapshot,
            )
        )
        return records

    def request_wallet_rollover(self, scope: str, reason: str = "long_term_rollover") -> str:
        return self.append(
            ch="WLT",
            src="BBX",
            act="SYS",
            ev="WLR",
            cov="F",
            payload={"scope": scope, "reason": reason},
        )

    def approve_wallet_rollover(self, actor: str, request_id: str) -> str:
        return self.append(
            ch="WLT",
            src="USR",
            act=actor,
            ev="WLA",
            cov="F",
            payload={"request": request_id},
        )

    def record_manual_wallet_package(self, actor: str, wallet: str, package_hash: str, scope: str) -> str:
        return self.append(
            ch="WLT",
            src="USR",
            act=actor,
            ev="WLP",
            cov="F",
            payload={"wallet": wallet, "package_hash": package_hash, "scope": scope, "method": "manual"},
        )

    def read_records(self, actor: str = "SYS", reason: str = "read") -> List[Dict[str, Any]]:
        self.access(actor=actor, access="read", scope=self.session_id, reason=reason)
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [decode_record(line) for line in lines]

    def verify(self) -> VerificationResult:
        with self._lock:
            return self._verify_locked()

    def _verify_locked(self) -> VerificationResult:
        errors: List[str] = []
        previous = ZERO_HASH
        checked = 0
        if not self.path.exists():
            return VerificationResult(ok=True, checked=0, errors=[])
        for expected_seq, line in enumerate(line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()):
            try:
                fields = parse_record(line)
                if int(fields["seq"]) != expected_seq:
                    errors.append(f"sequence gap at line {expected_seq}: got {fields['seq']}")
                if fields["ph"] != previous:
                    errors.append(f"previous hash mismatch at seq {fields['seq']}")
                previous = fields["h"]
                checked += 1
            except BlackBoxValidationError as exc:
                errors.append(str(exc))
        return VerificationResult(ok=not errors, checked=checked, errors=errors)


__all__ = ["AppendOnlyBlackBoxRecorder", "VerificationResult"]


