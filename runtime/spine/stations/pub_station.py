from __future__ import annotations
from typing import Any, Dict
from .base_station import BaseStation

class PubStation(BaseStation):
    def __init__(self, station_id: str, event_bus):
        super().__init__(station_id, "pub", event_bus)
        self.local_state.update({"topic": "open"})
    def on_activated(self, performer_id: str) -> bool:
        self.active_performer = performer_id
        self.emit_event("pub:interaction", {"performer_id": performer_id, "action": "joined"})
        return True
    def on_deactivated(self, performer_id: str) -> None:
        if self.active_performer == performer_id:
            self.active_performer = None
            self.emit_event("pub:interaction", {"performer_id": performer_id, "action": "left"})
    def on_interaction(self, performer_id: str, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        if "message" in interaction_data:
            self.emit_event("pub:message", {"performer_id": performer_id, "message": str(interaction_data["message"])})
        return self.get_state()
    def get_state(self) -> Dict[str, Any]:
        return {"station_id": self.station_id, "station_type": self.station_type, "active_performer": self.active_performer, **self.local_state}