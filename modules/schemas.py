# PubCast AI — schemas.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""
modules/schemas.py
------------------
Shared schema / enum types consumed by rooms, orchestrator,
and WebSocket event routing.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import time


class ParticipantRole(str, Enum):
    HOST      = "host"
    GUEST     = "guest"
    BOT       = "bot"
    MODERATOR = "moderator"
    VIEWER    = "viewer"
    HUMAN     = "human"


# ── WebSocket event payloads ──────────────────────────────────────────────────

@dataclass
class SayEvent:
    """A participant says something in a room."""
    room_id:      str
    participant_id: str
    text:         str
    timestamp:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "say",
            "room_id": self.room_id,
            "participant_id": self.participant_id,
            "text": self.text,
            "timestamp": self.timestamp,
        }


@dataclass
class StreamChunkEvent:
    """A streaming text chunk from a bot."""
    room_id:      str
    participant_id: str
    chunk:        str
    timestamp:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "stream_chunk",
            "room_id": self.room_id,
            "participant_id": self.participant_id,
            "chunk": self.chunk,
            "timestamp": self.timestamp,
        }


@dataclass
class DoneEvent:
    """Signals end of a streaming or async operation."""
    room_id:      str
    participant_id: str
    reason:       str = "complete"
    timestamp:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "done",
            "room_id": self.room_id,
            "participant_id": self.participant_id,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class ErrorEvent:
    """Signals an error to a room."""
    room_id:      str
    participant_id: str
    error:        str
    timestamp:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "error",
            "room_id": self.room_id,
            "participant_id": self.participant_id,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class RoomSnapshot:
    """Full state of a room at a point in time."""
    room_id:      str
    participants: List[Dict[str, Any]]
    message_count: int = 0
    timestamp:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "room_snapshot",
            "room_id": self.room_id,
            "participants": self.participants,
            "message_count": self.message_count,
            "timestamp": self.timestamp,
        }


__all__ = [
    "ParticipantRole",
    "SayEvent",
    "StreamChunkEvent",
    "DoneEvent",
    "ErrorEvent",
    "RoomSnapshot",
]


# Security/WebSocket compatibility surface. These types historically lived in
# a top-level schemas module; keep one authoritative implementation in the
# hardened wired security layer while preserving the import contract used by
# hardened_websocket.py and its tests.
from modules.wired.security import (
    ChatMessage, FeedbackMessage, CorrectionMessage, PingMessage, SetPersonaMessage,
)
from pydantic import BaseModel, Field


def validate_websocket_message(data: Dict[str, Any]):
    if not isinstance(data, dict):
        raise ValueError("WebSocket message must be an object")
    msg_type = data.get("type")
    normalized = dict(data)
    # Accept the legacy field names used by older clients/tests while exposing
    # the canonical response_id/message_id fields to the current handler.
    if msg_type == "feedback" and "response_id" not in normalized and "response" in normalized:
        normalized["response_id"] = normalized.pop("response")
    if msg_type == "correction" and "message_id" not in normalized and "message" in normalized:
        normalized["message_id"] = normalized.pop("message")
    model_map = {
        "chat": ChatMessage,
        "feedback": FeedbackMessage,
        "correction": CorrectionMessage,
        "ping": PingMessage,
        "set_persona": SetPersonaMessage,
    }
    model_cls = model_map.get(msg_type)
    if model_cls is None:
        raise ValueError(f"Unknown message type: {msg_type}")
    try:
        model = model_cls(**normalized)
    except Exception as exc:
        # Pydantic ValidationError is deliberately normalized to the historical
        # ValueError contract consumed by hardened_websocket.
        raise ValueError(str(exc)) from exc
    return msg_type, model


class PongMessage(BaseModel):
    type: str = "pong"
    timestamp: float


class ErrorEventResponse(BaseModel):
    type: str = "error"
    error: str
    error_code: str = "error"
    recoverable: bool = True

__all__ += [
    "ChatMessage", "FeedbackMessage", "CorrectionMessage", "PingMessage",
    "SetPersonaMessage", "validate_websocket_message", "PongMessage",
    "ErrorEventResponse",
]
