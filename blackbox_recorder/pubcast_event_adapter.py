"""Map PubCast runtime events into compact BlackBox records.

This module intentionally does not import PubCast runtime code. It is the small
adapter layer that can later sit behind the spine event bus, WebSocket hub, or
tool-call logger without changing their contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Dict, Mapping

from .append_only_recorder import AppendOnlyBlackBoxRecorder


EVENT_MAP = {
    "blackbox.archive_policy_changed": ("ACC", "DCP", "F"),
    "runtime.coverage_gap": ("ERR", "ERR", "P"),
    "runtime.blackbox_recovered": ("ACC", "LKA", "F"),
    "system.event": ("ACT", "DCP", "F"),
    "internal.audit": ("AIT", "DCP", "F"),
    "partner.turn_request": ("ACT", "DCP", "F"),
    "partner.private_turn": ("CHT", "MSG", "F"),
    "partner.turn_started": ("CHT", "MSG", "F"),
    "partner.turn_failed": ("ACT", "ERR", "F"),
    "partner.generation": ("ACT", "DCP", "F"),
    "runtime.heartbeat": ("ACC", "DCP", "F"),
    "runtime.blackbox_stopped": ("ACC", "LKR", "F"),
    "runtime.blackbox_restarted": ("ACC", "LKA", "F"),
    "capture.chunk_committed": ("REC", "DCP", "F"),
    "capture.started": ("REC", "DCP", "F"),
    "capture.stopped": ("REC", "DCP", "F"),
    "blackbox.saved": ("REC", "DCP", "F"),
    "blackbox.preserved": ("REC", "DCP", "F"),
    "recording.artifact": ("REC", "DCP", "F"),
    "recording.upload_started": ("REC", "DCP", "F"),
    "recording.upload_abandoned": ("REC", "DCP", "F"),
    "production.panic": ("ACT", "DCP", "F"),
    "production.video_cue": ("ACT", "DCP", "F"),
    "camera.switched": ("BRT", "DCP", "F"),
    "ai.decision_packet": ("AIT", "DCP", "P"),
    "switchblade.decision": ("AIT", "DCP", "P"),
    "chat.turn": ("AIT", "DCP", "P"),
    "chat.message": ("CHT", "MSG", "F"),
    "runtime.blackbox_ready": ("ACC", "LKA", "F"),
    "visual_patch.approved": ("APP", "APR", "F"),
    "audio.state": ("ACT", "DCP", "S"),
    "ai.tool_requested": ("ACT", "TCR", "F"),
    "ai.tool_completed": ("ACT", "TCD", "F"),
    "approval.approved": ("APP", "APR", "F"),
    "approval.denied": ("APP", "DNY", "F"),
    "broadcast.program_frame": ("BRT", "DCP", "S"),
    "camera.visibility": ("BRT", "DCP", "S"),
    "recording.preflight": ("REC", "DCP", "S"),
    "studio.readiness": ("REC", "DCP", "S"),
    "studio.action": ("ACT", "DCP", "F"),
    "recording.state": ("REC", "DCP", "S"),
    "runtime.error": ("ERR", "ERR", "F"),
    "conduct.event": ("DSC", "CND", "F"),
    "conduct.response": ("DSC", "RSP", "F"),
    "legal.export": ("LEG", "EXP", "F"),
}

SOURCE_MAP = {
    "alex": "ALEX",
    "jeremy": "JER",
    "pub_manager": "JER",
    "visual_patch": "VPK",
    "recorder": "REC",
    "recording": "REC",
    "blackbox": "BBX",
    "user": "USR",
    "chat": "SYS",
    "system": "SYS",
}


@dataclass(frozen=True)
class MappedPubCastEvent:
    ch: str
    src: str
    act: str
    ev: str
    cov: str
    payload: Dict[str, Any]


def _source_code(source: str) -> str:
    return SOURCE_MAP.get(str(source or "").strip().lower(), "SYS")


def map_pubcast_event(event: Mapping[str, Any]) -> MappedPubCastEvent:
    """Convert a normal PubCast event dict into a BBX event description."""

    event_type = str(event.get("event_type") or event.get("type") or "runtime.error")
    ch, ev, cov = EVENT_MAP.get(event_type, ("ERR", "ERR", "U"))
    source = _source_code(str(event.get("source") or event.get("src") or "system"))
    actor = str(event.get("actor") or event.get("actor_id") or event.get("source") or "SYS")
    data = event.get("data") if isinstance(event.get("data"), Mapping) else {}
    payload: Dict[str, Any] = {"event_type": event_type}
    for key, value in data.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            payload[str(key)] = value
        else:
            payload[f"{key}_type"] = type(value).__name__
    # Keep the scalar projection for existing offline tools, with a lossless
    # JSON copy preserving nested values, nulls, booleans and numeric types.
    # Envelope fields are assigned last so event details cannot replace identity.
    payload['data_json'] = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    payload['event_type'] = event_type
    payload['source_name'] = str(event.get('source') or event.get('src') or 'system')
    if "request_id" in event:
        payload["request_id"] = event["request_id"]
    if "record_hash" in event:
        payload["record_hash"] = event["record_hash"]
    handling = event.get("data_handling") if isinstance(event.get("data_handling"), Mapping) else {}
    if str(handling.get("classification") or "").upper() == "LIMITED":
        # BlackBox is the authoritative exception to Limited Exposure. Preserve
        # the complete event rather than the compact adapter's normal scalar-only
        # projection. JSON is canonicalised for deterministic replay/hash input.
        payload["data_class"] = "LIMITED"
        payload["raw_event_json"] = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return MappedPubCastEvent(ch=ch, src=source, act=actor, ev=ev, cov=cov, payload=payload)


def record_pubcast_event(recorder: AppendOnlyBlackBoxRecorder, event: Mapping[str, Any]) -> str:
    mapped = map_pubcast_event(event)
    return recorder.append(
        ch=mapped.ch,
        src=mapped.src,
        act=mapped.act,
        ev=mapped.ev,
        cov=mapped.cov,
        payload=mapped.payload,
    )


__all__ = ["EVENT_MAP", "SOURCE_MAP", "MappedPubCastEvent", "map_pubcast_event", "record_pubcast_event"]


