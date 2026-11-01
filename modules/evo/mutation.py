"""Typed state-change proposals for EVO agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any, Literal

Role = Literal["performer", "anchor", "director", "producer", "observer", "background", "system"]


@dataclass(frozen=True, slots=True)
class StateMutationRequest:
    source: str
    role: Role
    path: str
    value: Any
    priority: int = 0
    confidence: float = 1.0
    reason: str = ""
    created_at: float = field(default_factory=time)

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("mutation source must be non-empty")
        if not self.path.strip() or self.path.startswith(".") or self.path.endswith("."):
            raise ValueError(f"invalid mutation path: {self.path!r}")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
