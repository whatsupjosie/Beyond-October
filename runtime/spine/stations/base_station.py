from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..event_bus import EventBus


class BaseStation(ABC):
    """Base class for operational stations."""

    def __init__(self, station_id: str, station_type: str, event_bus: EventBus):
        self.station_id = station_id
        self.station_type = station_type
        self.event_bus = event_bus
        self.active_performer: Optional[str] = None
        self.local_state: Dict[str, Any] = {}

    @abstractmethod
    def on_activated(self, performer_id: str) -> bool: ...

    @abstractmethod
    def on_deactivated(self, performer_id: str) -> None: ...

    @abstractmethod
    def on_interaction(self, performer_id: str, interaction_data: Dict[str, Any]) -> Dict[str, Any]: ...

    @abstractmethod
    def get_state(self) -> Dict[str, Any]: ...

    def emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        payload = {"station_id": self.station_id, "station_type": self.station_type, **(data or {})}
        self.event_bus.emit(event_type, payload, source=self.station_id)