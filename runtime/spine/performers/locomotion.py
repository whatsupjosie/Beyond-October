from __future__ import annotations

import math
from typing import Dict, List

from ..event_bus import EventBus
from ..performer_registry import PerformerRegistry


class LocomotionSystem:
    """Small deterministic movement system for avatars."""

    def __init__(self, performer_registry: PerformerRegistry, event_bus: EventBus, speed: float = 1.4):
        self.registry = performer_registry
        self.event_bus = event_bus
        self.update_rate = 60
        self.speed = float(speed)
        self._elapsed = 0.0

    def move_to(self, performer_id: str, target_position: List[float]) -> None:
        performer = self.registry._require(performer_id)
        performer.target_position = [float(v) for v in target_position[:3]]
        performer.mark_dirty()
        self.registry.set_locomotion_state(performer_id, "walking")

    def update(self, delta_time: float) -> None:
        self._elapsed += max(0.0, float(delta_time))
        for performer in self.registry.all_performers():
            if performer.locomotion_state != "walking" or performer.target_position is None:
                continue
            dx = [performer.target_position[i] - performer.position[i] for i in range(3)]
            distance = math.sqrt(sum(v * v for v in dx))
            if distance <= 0.01:
                performer.position = list(performer.target_position)
                performer.velocity = [0.0, 0.0, 0.0]
                performer.target_position = None
                performer.mark_dirty()
                self.registry.set_locomotion_state(performer.performer_id, "idle")
                continue
            step = min(distance, self.speed * max(0.0, float(delta_time)))
            direction = [v / distance for v in dx]
            new_position = [performer.position[i] + direction[i] * step for i in range(3)]
            performer.velocity = [direction[i] * self.speed for i in range(3)]
            self.registry.update_performer_transform(performer.performer_id, new_position, performer.rotation)
            self.registry.apply_animation_frame(performer.performer_id, self.get_walk_animation_frame(performer.performer_id, self._elapsed))

    def stop(self, performer_id: str) -> None:
        performer = self.registry._require(performer_id)
        performer.velocity = [0.0, 0.0, 0.0]
        performer.target_position = None
        performer.mark_dirty()
        self.registry.set_locomotion_state(performer_id, "idle")

    def get_walk_animation_frame(self, performer_id: str, elapsed: float) -> Dict:
        phase = math.sin(elapsed * math.tau * 1.2)
        return {"animation": "walk", "bones": {"left_upper_leg": {"rotation": [phase * 18.0, 0.0, 0.0]}, "right_upper_leg": {"rotation": [-phase * 18.0, 0.0, 0.0]}, "left_upper_arm": {"rotation": [-phase * 10.0, 0.0, 0.0]}, "right_upper_arm": {"rotation": [phase * 10.0, 0.0, 0.0]}, "spine": {"rotation": [0.0, phase * 2.0, 0.0]}}}