from __future__ import annotations
from typing import Any, Dict
from .base_station import BaseStation

class CameraStation(BaseStation):
    def __init__(self, station_id: str, event_bus):
        super().__init__(station_id, "camera", event_bus)
        self.local_state.update({"live": False, "target": None})
    def on_activated(self, performer_id: str) -> bool:
        self.active_performer = performer_id
        self.emit_event("camera:focused", {"performer_id": performer_id})
        return True
    def on_deactivated(self, performer_id: str) -> None:
        if self.active_performer == performer_id:
            self.active_performer = None
            self.local_state["live"] = False
    def on_interaction(self, performer_id: str, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        if "live" in interaction_data:
            self.local_state["live"] = bool(interaction_data["live"])
            self.emit_event("camera:live", {"performer_id": performer_id, "live": self.local_state["live"]})
        if "target" in interaction_data:
            self.local_state["target"] = interaction_data["target"]
            self.emit_event("camera:focused", {"performer_id": performer_id, "target": self.local_state["target"]})
        return self.get_state()
    def get_state(self) -> Dict[str, Any]:
        return {"station_id": self.station_id, "station_type": self.station_type, "active_performer": self.active_performer, **self.local_state}