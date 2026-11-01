# PubCast AI — camera_manager.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rear View Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""
Compatibility adapter for the advanced camera manager.

This file intentionally re-exports the real implementation from
``modules.cameras_advanced`` so older handoffs that import
``modules.camera_manager`` can work without creating a second camera
system. Production routes still use ``modules.cameras`` unless explicitly
migrated through the parallel-deployment path.
"""

from .cameras_advanced import (
    AdvancedCameraManager,
    CameraMetadata,
    CameraRole,
    CameraSource,
    CameraStatus,
    CameraTransport,
    create_default_cameras,
    create_ip_camera,
    create_usb_camera,
    create_voxel_camera,
)

__all__ = [
    "AdvancedCameraManager",
    "CameraMetadata",
    "CameraRole",
    "CameraSource",
    "CameraStatus",
    "CameraTransport",
    "create_default_cameras",
    "create_ip_camera",
    "create_usb_camera",
    "create_voxel_camera",
]
