from __future__ import annotations

import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _vec(values: List[float], size: int, default: float = 0.0) -> List[float]:
    out = [float(v) for v in (values or [])[:size]]
    while len(out) < size:
        out.append(default)
    return out


@dataclass
class PerformerState:
    performer_id: str
    name: str
    position: List[float]
    rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 1.0])
    velocity: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    target_position: Optional[List[float]] = None
    locomotion_state: str = "idle"
    current_animation: str = "idle"
    animation_blend: float = 0.0
    skeleton_pose: Dict[str, Any] = field(default_factory=dict)
    active_station: Optional[str] = None
    interaction_data: Dict[str, Any] = field(default_factory=dict)
    current_room: str = "default"
    current_zone: Optional[str] = None
    last_update_time: float = field(default_factory=time.time)
    replication_tick: int = 0
    dirty: bool = True
    avatar_model_id: str = ""
    avatar_skeleton: Any = None

    def __post_init__(self) -> None:
        self.position = _vec(self.position, 3)
        self.rotation = _vec(self.rotation, 4)
        self.velocity = _vec(self.velocity, 3)
        if self.target_position is not None:
            self.target_position = _vec(self.target_position, 3)

    def mark_dirty(self) -> None:
        self.last_update_time = time.time()
        self.replication_tick += 1
        self.dirty = True

    def mark_clean(self) -> None:
        self.dirty = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "performer_id": self.performer_id,
            "name": self.name,
            "position": list(self.position),
            "rotation": list(self.rotation),
            "velocity": list(self.velocity),
            "target_position": list(self.target_position) if self.target_position is not None else None,
            "locomotion_state": self.locomotion_state,
            "current_animation": self.current_animation,
            "animation_blend": float(self.animation_blend),
            "skeleton_pose": deepcopy(self.skeleton_pose),
            "active_station": self.active_station,
            "interaction_data": deepcopy(self.interaction_data),
            "current_room": self.current_room,
            "current_zone": self.current_zone,
            "last_update_time": self.last_update_time,
            "replication_tick": self.replication_tick,
            "dirty": self.dirty,
            "avatar_model_id": self.avatar_model_id,
        }