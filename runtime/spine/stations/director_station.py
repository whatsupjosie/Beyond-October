from __future__ import annotations
from typing import Any, Dict
from .base_station import BaseStation

class DirectorStation(BaseStation):
    def __init__(self, station_id: str, event_bus):
        super().__init__(station_id, "director", event_bus)
        self.local_state.update({"mode": "standby"})
    def on_activated(self, performer_id: str) -> bool:
        self.active_performer = performer_id
        self.emit_event("station:activated", {"performer_id": performer_id})
        return True
    def on_deactivated(self, performer_id: str) -> None:
        if self.active_performer == performer_id:
            self.active_performer = None
            self.emit_event("station:deactivated", {"performer_id": performer_id})
    def on_interaction(self, performer_id: str, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        if "mode" in interaction_data:
            self.local_state["mode"] = str(interaction_data["mode"])
        self.emit_event("station:state_change", {"performer_id": performer_id, "state": self.local_state})
        return self.get_state()
    def get_state(self) -> Dict[str, Any]:
        return {"station_id": self.station_id, "station_type": self.station_type, "active_performer": self.active_performer, **self.local_state}