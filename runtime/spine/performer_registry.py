from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from .event_bus import EventBus
from .performers.performer_state import PerformerState

VALID_LOCOMOTION_STATES = {"idle", "walking", "running", "interacting", "falling", "sitting"}


class PerformerRegistry:
    """Authoritative registry for all performers."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._performers: Dict[str, PerformerState] = {}

    def spawn_performer(self, performer_id: str, name: str, position: List[float], room: str) -> PerformerState:
        if performer_id in self._performers:
            raise ValueError(f"Performer '{performer_id}' already exists")
        performer = PerformerState(performer_id=performer_id, name=name, position=position, current_room=room)
        self._performers[performer_id] = performer
        self.event_bus.emit("performer:spawned", performer.to_dict(), source="performer_registry")
        return performer

    def get_performer(self, performer_id: str) -> Optional[PerformerState]:
        return self._performers.get(performer_id)

    def all_performers(self) -> List[PerformerState]:
        return list(self._performers.values())

    def update_performer_transform(self, performer_id: str, position: List[float], rotation: List[float]) -> PerformerState:
        performer = self._require(performer_id)
        performer.position = [float(v) for v in position[:3]]
        performer.rotation = [float(v) for v in rotation[:4]]
        performer.mark_dirty()
        self.event_bus.emit("performer:moved", performer.to_dict(), source="performer_registry")
        return performer

    def set_locomotion_state(self, performer_id: str, state: str) -> PerformerState:
        if state not in VALID_LOCOMOTION_STATES:
            raise ValueError(f"Unsupported locomotion state '{state}'")
        performer = self._require(performer_id)
        performer.locomotion_state = state
        performer.mark_dirty()
        self.event_bus.emit("performer:state_change", performer.to_dict(), source="performer_registry")
        return performer

    def apply_animation_frame(self, performer_id: str, skeleton_pose: Dict[str, Any]) -> PerformerState:
        performer = self._require(performer_id)
        performer.skeleton_pose = deepcopy(skeleton_pose or {})
        performer.current_animation = str((skeleton_pose or {}).get("animation", performer.current_animation))
        performer.mark_dirty()
        self.event_bus.emit("performer:animated", performer.to_dict(), source="performer_registry")
        return performer

    def activate_station(self, performer_id: str, station_id: str) -> PerformerState:
        performer = self._require(performer_id)
        performer.active_station = station_id
        performer.locomotion_state = "interacting"
        performer.mark_dirty()
        self.event_bus.emit("station:activated", {"performer_id": performer_id, "station_id": station_id}, source="performer_registry")
        return performer

    def deactivate_station(self, performer_id: str) -> PerformerState:
        performer = self._require(performer_id)
        station_id = performer.active_station
        performer.active_station = None
        performer.locomotion_state = "idle"
        performer.mark_dirty()
        self.event_bus.emit("station:deactivated", {"performer_id": performer_id, "station_id": station_id}, source="performer_registry")
        return performer

    def _require(self, performer_id: str) -> PerformerState:
        performer = self._performers.get(performer_id)
        if performer is None:
            raise KeyError(f"Unknown performer '{performer_id}'")
        return performer