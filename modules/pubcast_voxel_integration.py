#!/usr/bin/env python3
# PubCast AI — pubcast_voxel_integration.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""Small e-PETE-facing adapter for the current voxel runtime.

The historical e-PETE code expected ``PubCastVoxelIntegration``. The v5.6 build
already contains ``VoxelStudioIntegration`` and ``VoxelAssetManager``. This file
provides the missing e-PETE import without creating a second room model, second
Bubble path, or fake renderer. It delegates to the existing bridge/renderer where
available and reports missing parts honestly.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("pubcast.pubcast_voxel_integration")


class PubCastVoxelIntegration:
    """e-PETE compatibility adapter for current voxel studio/runtime pieces."""

    def __init__(self, camera_manager=None, hub=None, bridge=None, asset_manager=None, data_dir: Optional[Path] = None, **_: Any) -> None:
        self.camera_manager = camera_manager
        self.hub = hub
        self.bridge = bridge
        self.asset_manager = asset_manager
        self.data_dir = Path(data_dir) if data_dir else Path.cwd() / "data"
        self.available = True
        self._last_scene_id: Optional[str] = None
        self._last_error: Optional[str] = None

    async def load_scene(self, scene: Dict[str, Any]) -> bool:
        """Send a scene load request through the existing e-PETE bridge if present."""
        self._last_scene_id = str(scene.get("scene_id") or scene.get("id") or scene.get("name") or "unnamed_scene")
        if self.bridge and hasattr(self.bridge, "send_command"):
            ok = self.bridge.send_command("LOAD_SCENE", {"scene": self._last_scene_id, "data": scene})
            if not ok:
                self._last_error = "bridge rejected LOAD_SCENE"
            return bool(ok)
        self._last_error = "no bridge attached"
        return False

    async def _restart_voxel_engine(self) -> bool:
        """Restart hook placeholder: honest because process ownership lives in VoxelWebRTCBridge."""
        self._last_error = "restart requested; renderer process is managed by VoxelWebRTCBridge when active"
        logger.warning(self._last_error)
        return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "bridge_attached": self.bridge is not None,
            "asset_manager_attached": self.asset_manager is not None,
            "last_scene_id": self._last_scene_id,
            "last_error": self._last_error,
        }

    async def shutdown(self) -> None:
        return None
