# PubCast AI — camera_broadcast.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""One place that tells every page when the program or preview camera changes.

Five routes can change cameras (/api/cameras/program, /preview, /switch, /cut,
/api/switcher/*, and the director console's studio actions). Only some of them
broadcast, so cuts from the others changed the backend and nothing on screen.
CameraManager already emits a CameraSwitchEvent for every real change; this
bridge subscribes once and forwards each one to the Hub as the `camera_switch`
message the stage pages already handle. Routes no longer need to remember.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional, Set

from .cameras import CameraManager, CameraSwitchEvent

logger = logging.getLogger("pubcast.camera_broadcast")


class CameraBroadcastBridge:
    def __init__(self, cameras: CameraManager, hub: Any):
        self.cameras = cameras
        self.hub = hub
        self._token: Optional[int] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks: Set[asyncio.Task] = set()
        self.sent = 0

    @property
    def running(self) -> bool:
        return self._token is not None

    def start(self) -> None:
        """Subscribe from inside the running event loop (the app lifespan)."""
        if self._token is not None:
            return
        self._loop = asyncio.get_running_loop()
        self._token = self.cameras.subscribe(self._on_event)
        # Routes that still broadcast themselves check this flag to avoid doubles.
        setattr(self.hub, "camera_events_bridged", True)

    async def stop(self) -> None:
        if self._token is not None:
            self.cameras.unsubscribe(self._token)
            self._token = None
        if self.hub is not None and getattr(self.hub, "camera_events_bridged", False):
            setattr(self.hub, "camera_events_bridged", False)
        pending = [t for t in self._tasks if not t.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()

    def message(self, event: CameraSwitchEvent) -> dict:
        program = self.cameras.get_program_source()
        preview = self.cameras.get_preview_source()
        return {
            "type": "camera_switch",
            "payload": {
                "target": event.destination,
                "source_id": event.source_id,
                "previous_source_id": event.previous_source_id,
                "program": program.source_id if program else None,
                "preview": preview.source_id if preview else None,
                "timestamp": event.timestamp or time.time(),
            },
        }

    def _on_event(self, event: Any) -> None:
        if not isinstance(event, CameraSwitchEvent) or self.hub is None or self._loop is None:
            return
        message = self.message(event)

        def schedule() -> None:
            task = self._loop.create_task(self._send(message))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            schedule()
        elif not self._loop.is_closed():
            self._loop.call_soon_threadsafe(schedule)   # a change made from a worker thread

    async def _send(self, message: dict) -> None:
        try:
            await self.hub.broadcast_system_event(message)
            self.sent += 1
        except Exception:
            logger.exception("camera_switch broadcast failed for %s", message["payload"].get("source_id"))


__all__ = ["CameraBroadcastBridge"]
