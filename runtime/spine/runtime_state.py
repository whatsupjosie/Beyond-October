from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .event_bus import EventBus
from .performer_registry import PerformerRegistry
from .station_registry import StationRegistry


@dataclass
class RuntimeState:
    """Composition root for the PubCast runtime spine."""

    event_bus: EventBus = field(default_factory=EventBus)
    current_room: str = "default"

    def __post_init__(self) -> None:
        self.performers = PerformerRegistry(self.event_bus)
        self.stations = StationRegistry(self.event_bus)

    def enter_room(self, performer_id: str, room_id: str) -> None:
        performer = self.performers._require(performer_id)
        previous = performer.current_room
        performer.current_room = room_id
        performer.mark_dirty()
        self.event_bus.emit("room:exited", {"performer_id": performer_id, "room_id": previous}, source="runtime_state")
        self.event_bus.emit("room:entered", {"performer_id": performer_id, "room_id": room_id}, source="runtime_state")

    def snapshot(self) -> Dict[str, Any]:
        return {"current_room": self.current_room, "performers": [item.to_dict() for item in self.performers.all_performers()], "stations": self.stations.broadcast_station_states(), "events": list(self.event_bus.history[-32:])}