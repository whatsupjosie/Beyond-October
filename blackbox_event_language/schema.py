"""Compact non-English BlackBox event language.

The primary record is a coded wire string. English is produced only by the
decoder/report layer using the in-program key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, Mapping
from urllib.parse import quote, unquote


VERSION = "BBX1"
ZERO_HASH = "0" * 64

BLACKBOX_KEY: Dict[str, Dict[str, str] | str] = {
    "version": VERSION,
    "channels": {
        "AIT": "AI thought or decision trace",
        "CHT": "chat message transcript",
        "BRT": "broadcast output trace",
        "ACT": "AI/tool action trace",
        "APP": "approval or denial trace",
        "ERR": "runtime error trace",
        "REC": "recording pipeline trace",
        "CRS": "crash-position trace",
        "ACC": "BlackBox access trace",
        "LEG": "legal request or disclosure trace",
        "DSC": "disciplinary or conduct review trace",
        "WLT": "iteration wallet trace",
        "PER": "performance budget trace",
    },
    "sources": {
        "BBX": "BlackBox recorder",
        "SYS": "PubCast system",
        "ALEX": "Alex AI system",
        "JER": "Jeremy/Pub Manager system",
        "VPK": "Visual Patch Kit",
        "REC": "recording pipeline",
        "USR": "user-facing client",
    },
    "events": {
        "LKA": "lock acquired",
        "LKR": "lock released",
        "DCP": "decision packet captured",
        "MSG": "chat message persisted",
        "TCR": "tool call requested",
        "TCD": "tool call completed",
        "APR": "approval recorded",
        "DNY": "denial recorded",
        "ERR": "error observed",
        "EXP": "export created",
        "ACS": "BlackBox accessed",
        "CPI": "crash-position initiated",
        "CPS": "crash-position snapshot",
        "BPR": "budget pressure recorded",
        "CND": "conduct event recorded",
        "RVW": "review initiated",
        "RSP": "response action recorded",
        "WLR": "wallet rollover requested",
        "WLA": "wallet rollover approved",
        "WLD": "wallet rollover denied",
        "WLP": "manual wallet package recorded",
    },
    "coverage": {
        "F": "full coverage for declared segment",
        "P": "partial coverage",
        "S": "sampled coverage",
        "U": "unknown coverage",
    },
}

REQUIRED_FIELDS = ("seq", "t", "ch", "src", "act", "ev", "cov", "sid", "rid", "ph", "h", "p")


class BlackBoxValidationError(ValueError):
    """Raised when a BlackBox coded event violates the schema."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _code_table(name: str) -> Mapping[str, str]:
    table = BLACKBOX_KEY.get(name, {})
    return table if isinstance(table, Mapping) else {}


def _clean_atom(value: Any, field_name: str) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        raise BlackBoxValidationError(f"{field_name} is required")
    if "|" in text or "\n" in text or "\r" in text:
        raise BlackBoxValidationError(f"{field_name} contains an illegal separator")
    return text


def _encode_payload(payload: Mapping[str, Any] | str | None) -> str:
    if payload is None:
        return "-"
    if isinstance(payload, str):
        return quote(payload, safe="-_.:,@/")
    parts = []
    for key in sorted(payload):
        clean_key = str(key).strip()
        if not clean_key:
            continue
        value = payload[key]
        parts.append(f"{quote(clean_key, safe='-_.')}:{quote(str(value), safe='-_.:,@/')}")
    return ",".join(parts) if parts else "-"


def _decode_payload(payload: str) -> Dict[str, str]:
    if payload in {"", "-"}:
        return {}
    out: Dict[str, str] = {}
    for item in payload.split(","):
        if not item:
            continue
        if ":" not in item:
            out[unquote(item)] = ""
            continue
        key, value = item.split(":", 1)
        out[unquote(key)] = unquote(value)
    return out


def _hash_material(fields: Mapping[str, Any]) -> str:
    ordered = []
    for key in REQUIRED_FIELDS:
        if key == "h":
            continue
        ordered.append(f"{key}={fields.get(key, '')}")
    return "|".join(ordered)


def record_hash(fields: Mapping[str, Any]) -> str:
    return sha256(_hash_material(fields).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BlackBoxRecord:
    seq: int
    ch: str
    src: str
    act: str
    ev: str
    cov: str
    sid: str
    rid: str
    payload: Mapping[str, Any] | str | None = field(default_factory=dict)
    t: str = field(default_factory=utc_now)
    ph: str = ZERO_HASH
    h: str = ""

    def fields_without_hash(self) -> Dict[str, str]:
        return {
            "seq": str(int(self.seq)),
            "t": _clean_atom(self.t, "t"),
            "ch": _clean_atom(self.ch, "ch"),
            "src": _clean_atom(self.src, "src"),
            "act": _clean_atom(self.act, "act"),
            "ev": _clean_atom(self.ev, "ev"),
            "cov": _clean_atom(self.cov, "cov"),
            "sid": _clean_atom(self.sid, "sid"),
            "rid": _clean_atom(self.rid, "rid"),
            "ph": _clean_atom(self.ph, "ph"),
            "h": "",
            "p": _encode_payload(self.payload),
        }

    def to_fields(self) -> Dict[str, str]:
        fields = self.fields_without_hash()
        fields["h"] = self.h or record_hash(fields)
        return fields


def validate_record(fields: Mapping[str, Any]) -> None:
    for key in REQUIRED_FIELDS:
        if key not in fields:
            raise BlackBoxValidationError(f"missing field {key}")
    try:
        seq = int(fields["seq"])
    except (TypeError, ValueError) as exc:
        raise BlackBoxValidationError("seq must be an integer") from exc
    if seq < 0:
        raise BlackBoxValidationError("seq must be non-negative")
    if str(fields["ch"]) not in _code_table("channels"):
        raise BlackBoxValidationError(f"unknown channel {fields['ch']}")
    if str(fields["src"]) not in _code_table("sources"):
        raise BlackBoxValidationError(f"unknown source {fields['src']}")
    if str(fields["ev"]) not in _code_table("events"):
        raise BlackBoxValidationError(f"unknown event {fields['ev']}")
    if str(fields["cov"]) not in _code_table("coverage"):
        raise BlackBoxValidationError(f"unknown coverage {fields['cov']}")
    expected = record_hash(fields)
    if fields.get("h") != expected:
        raise BlackBoxValidationError("record hash mismatch")


def encode_record(record: BlackBoxRecord) -> str:
    fields = record.to_fields()
    validate_record(fields)
    body = "|".join(f"{key}={fields[key]}" for key in REQUIRED_FIELDS)
    return f"{VERSION}|{body}"


def parse_record(wire: str) -> Dict[str, str]:
    parts = str(wire).strip().split("|")
    if not parts or parts[0] != VERSION:
        raise BlackBoxValidationError("unsupported BlackBox version")
    fields: Dict[str, str] = {}
    for item in parts[1:]:
        if "=" not in item:
            raise BlackBoxValidationError(f"malformed field {item!r}")
        key, value = item.split("=", 1)
        fields[key] = value
    validate_record(fields)
    return fields


def decode_record(wire: str) -> Dict[str, Any]:
    fields = parse_record(wire)
    return {
        "version": VERSION,
        "seq": int(fields["seq"]),
        "timestamp": fields["t"],
        "channel": {"code": fields["ch"], "label": _code_table("channels")[fields["ch"]]},
        "source": {"code": fields["src"], "label": _code_table("sources")[fields["src"]]},
        "actor": fields["act"],
        "event": {"code": fields["ev"], "label": _code_table("events")[fields["ev"]]},
        "coverage": {"code": fields["cov"], "label": _code_table("coverage")[fields["cov"]]},
        "session_id": fields["sid"],
        "record_id": fields["rid"],
        "previous_hash": fields["ph"],
        "hash": fields["h"],
        "payload": _decode_payload(fields["p"]),
    }


__all__ = [
    "BLACKBOX_KEY",
    "VERSION",
    "ZERO_HASH",
    "BlackBoxRecord",
    "BlackBoxValidationError",
    "decode_record",
    "encode_record",
    "parse_record",
    "record_hash",
    "utc_now",
    "validate_record",
]
