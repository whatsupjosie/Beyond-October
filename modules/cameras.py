# PubCast AI — cameras.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""
Camera Management System for PubCast AI

Professional camera source management supporting NDI, RTMP, SRT, virtual cameras,
and future integration with Rust rendering core for 3D voxel cameras.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Union


class CameraTransport(str, Enum):
    """Delivery mechanism for a camera feed."""
    NDI = "ndi"
    RTMP = "rtmp"
    SRT = "srt"
    FILE = "file"
    VIRTUAL = "virtual"
    VOXEL_3D = "voxel_3d"  # For future Rust renderer integration


@dataclass
class CameraSource:
    """Describes a physical or virtual camera feed that can be recorded."""
    
    source_id: str
    name: str
    location: str
    description: str
    transport: CameraTransport
    endpoint: str
    audio_channels: int = 2
    video_enabled: bool = True
    audio_enabled: bool = True
    tags: List[str] = field(default_factory=list)
    is_private: bool = False
    
    # 3D positioning for voxel cameras (future Rust integration)
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    fov: float = 60.0
    focus: float = 5.0          # metres to the sharp plane; set with update_pose (rotation is [tilt, pan, roll] in degrees, position in metres, y up)


@dataclass(frozen=True)
class CameraSwitchEvent:
    destination: str
    source_id: str
    previous_source_id: Optional[str]
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class CameraPoseEvent:
    source_id: str
    position: List[float]
    rotation: List[float]
    fov: float
    timestamp: float = field(default_factory=time.time)
    focus: float = 5.0


CameraEvent = Union[CameraSwitchEvent, CameraPoseEvent]


@dataclass
class CameraStatus:
    """Represents the health of a camera feed."""
    
    source_id: str
    online: bool
    last_check: float = field(default_factory=time.time)
    latency_ms: Optional[float] = None
    frame_rate: Optional[float] = None
    notes: Optional[str] = None


class CameraManager:
    """
    Keeps track of all camera feeds and their latest health information.
    Designed for integration with Rust rendering core for high-performance 3D cameras.
    """

    def __init__(self) -> None:
        self._sources: Dict[str, CameraSource] = {}
        self._status: Dict[str, CameraStatus] = {}
        
        # Program/Preview switching (professional broadcast workflow)
        self._program_source: Optional[str] = None
        self._preview_source: Optional[str] = None
        self._listeners: Dict[int, Callable[[CameraEvent], None]] = {}
        self._next_listener_id = 1

    # Registration and lookup
    def register(self, source: CameraSource) -> None:
        """Register a camera source."""
        self._sources[source.source_id] = source
        if source.source_id not in self._status:
            self._status[source.source_id] = CameraStatus(
                source_id=source.source_id,
                online=True,
                notes="Registered",
            )

    def remove(self, source_id: str) -> None:
        """Remove a camera source."""
        self._sources.pop(source_id, None)
        self._status.pop(source_id, None)

    def list_sources(self) -> List[CameraSource]:
        """Get all registered camera sources."""
        return list(self._sources.values())

    def get(self, source_id: str) -> Optional[CameraSource]:
        """Get specific camera source by ID."""
        return self._sources.get(source_id)

    # Canonical camera events / Program-Preview switching
    def subscribe(self, callback: Callable[[CameraEvent], None]) -> int:
        token = self._next_listener_id
        self._next_listener_id += 1
        self._listeners[token] = callback
        return token

    def unsubscribe(self, token: int) -> bool:
        return self._listeners.pop(token, None) is not None

    def _emit(self, event: CameraEvent) -> None:
        for callback in list(self._listeners.values()):
            try:
                callback(event)
            except Exception:
                # Camera state is authoritative; diagnostics may not roll it back.
                pass

    def set_program_source(self, source_id: str) -> bool:
        """Set Program. Invalid/idempotent changes do not emit an event."""
        if source_id not in self._sources:
            return False
        previous = self._program_source
        if previous == source_id:
            return True
        self._program_source = source_id
        self._emit(CameraSwitchEvent("program", source_id, previous))
        return True

    def set_preview_source(self, source_id: str) -> bool:
        """Set Preview. Invalid/idempotent changes do not emit an event."""
        if source_id not in self._sources:
            return False
        previous = self._preview_source
        if previous == source_id:
            return True
        self._preview_source = source_id
        self._emit(CameraSwitchEvent("preview", source_id, previous))
        return True

    def update_pose(self, source_id: str, *, position=None, rotation=None, fov=None, focus=None) -> bool:
        source = self._sources.get(source_id)
        if source is None:
            return False
        changed = False
        if position is not None:
            pos = [float(v) for v in position]
            if len(pos) != 3:
                raise ValueError("position must contain x,y,z")
            if pos != source.position:
                source.position = pos; changed = True
        if rotation is not None:
            rot = [float(v) for v in rotation]
            if len(rot) != 3:
                raise ValueError("rotation must contain x,y,z")
            if rot != source.rotation:
                source.rotation = rot; changed = True
        if fov is not None:
            new_fov = float(fov)
            if not 1.0 <= new_fov <= 179.0:
                raise ValueError("fov must be between 1 and 179 degrees")
            if new_fov != source.fov:
                source.fov = new_fov; changed = True
        if focus is not None:
            new_focus = float(focus)
            if not 0.3 <= new_focus <= 200.0:
                raise ValueError("focus must be between 0.3 and 200 metres")
            if new_focus != source.focus:
                source.focus = new_focus; changed = True
        if changed:
            self._emit(CameraPoseEvent(source_id, list(source.position), list(source.rotation), source.fov, focus=source.focus))
        return True

    def take(self) -> bool:
        """Atomically exchange Program and Preview, then emit the resulting changes."""
        if not self._program_source or not self._preview_source:
            return False
        old_program, old_preview = self._program_source, self._preview_source
        if old_program == old_preview:
            return True
        self._program_source, self._preview_source = old_preview, old_program
        now = time.time()
        self._emit(CameraSwitchEvent("program", self._program_source, old_program, now))
        self._emit(CameraSwitchEvent("preview", self._preview_source, old_preview, now))
        return True

    def get_program_source(self) -> Optional[CameraSource]:
        """Get current program source."""
        if self._program_source:
            return self._sources.get(self._program_source)
        return None

    def get_preview_source(self) -> Optional[CameraSource]:
        """Get current preview source."""  
        if self._preview_source:
            return self._sources.get(self._preview_source)
        return None

    # Status management
    def set_status(
        self,
        source_id: str,
        *,
        online: Optional[bool] = None,
        latency_ms: Optional[float] = None,
        frame_rate: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Update camera status metrics."""
        if source_id not in self._sources:
            raise KeyError(f"Unknown camera '{source_id}'")
            
        entry = self._status.setdefault(
            source_id,
            CameraStatus(source_id=source_id, online=True),
        )
        
        if online is not None:
            entry.online = online
        if latency_ms is not None:
            entry.latency_ms = latency_ms
        if frame_rate is not None:
            entry.frame_rate = frame_rate
        if notes is not None:
            entry.notes = notes
        entry.last_check = time.time()

    def status(self, source_id: str) -> Optional[CameraStatus]:
        """Get status for specific camera."""
        return self._status.get(source_id)

    def list_status(self) -> List[CameraStatus]:
        """Get status for all cameras."""
        return list(self._status.values())


# Factory function for default camera setup
def create_default_cameras() -> CameraManager:
    """Create camera manager with default virtual camera setup."""
    
    manager = CameraManager()
    
    # Virtual cameras for immediate use
    manager.register(
        CameraSource(
            source_id="wide_shot",
            name="Wide Shot",
            description="Wide angle view of the scene",
            location="virtual",
            transport=CameraTransport.VIRTUAL,
            endpoint="virtual://wide_shot",
            position=[0.0, 2.0, 5.0],
            rotation=[0.0, 0.0, 0.0],
            fov=75.0,
            tags=["virtual", "wide", "establishing"]
        )
    )
    
    manager.register(
        CameraSource(
            source_id="medium_shot", 
            name="Medium Shot",
            description="Medium framing for dialogue",
            location="virtual",
            transport=CameraTransport.VIRTUAL,
            endpoint="virtual://medium_shot",
            position=[2.0, 1.5, 3.0],
            rotation=[0.0, -15.0, 0.0],
            fov=50.0,
            tags=["virtual", "medium", "dialogue"]
        )
    )
    
    manager.register(
        CameraSource(
            source_id="close_up",
            name="Close Up",
            description="Close framing for emotion",
            location="virtual", 
            transport=CameraTransport.VIRTUAL,
            endpoint="virtual://close_up",
            position=[1.0, 1.0, 1.5],
            rotation=[0.0, 0.0, 0.0],
            fov=35.0,
            tags=["virtual", "close", "emotion"]
        )
    )
    
    manager.register(
        CameraSource(
            source_id="overhead",
            name="Overhead Shot", 
            description="Top-down view",
            location="virtual",
            transport=CameraTransport.VIRTUAL,
            endpoint="virtual://overhead",
            position=[0.0, 5.0, 0.0],
            rotation=[90.0, 0.0, 0.0],
            fov=90.0,
            tags=["virtual", "overhead", "establishing"]
        )
    )
    
    # Physical camera examples (NDI sources)
    manager.register(
        CameraSource(
            source_id="cam1_ndi",
            name="Camera 1 NDI",
            description="Physical NDI camera #1",
            location="studio",
            transport=CameraTransport.NDI,
            endpoint="ndi://camera-1",
            tags=["physical", "ndi", "studio"]
        )
    )
    
    manager.register(
        CameraSource(
            source_id="cam2_rtmp",
            name="Camera 2 RTMP", 
            description="RTMP stream camera #2",
            location="remote",
            transport=CameraTransport.RTMP,
            endpoint="rtmp://streaming-server/cam2",
            tags=["physical", "rtmp", "remote"]
        )
    )
    
    # Set default program/preview
    manager.set_program_source("wide_shot")
    manager.set_preview_source("medium_shot")
    
    return manager
