"""
PUBCAST CAMERA VISION INTEGRATION
Integrates cinematic camera vision with existing PubCast infrastructure
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Try to import structlog, fall back to standard logging
try:
    import structlog
    logger = structlog.get_logger("pubcast.vision")
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("pubcast.vision")

# Camera Manager imports (existing system)
try:
    from camera_manager import (
        CameraManager, CameraSource, CameraType, CameraStatus, 
        PTZCapability, SwitcherState
    )
    CAMERA_MANAGER_AVAILABLE = True
except ImportError:
    CAMERA_MANAGER_AVAILABLE = False
    logger.warning("CameraManager not available, using standalone mode")

# ============================================================================
# VISION SYSTEM CORE COMPONENTS
# ============================================================================

@dataclass
class Vector3D:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    def distance_to(self, other: 'Vector3D') -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx*dx + dy*dy + dz*dz)
    
    def dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass
class CameraFrustum:
    """Defines the camera's field of view"""
    fov_horizontal: float = 60.0  # degrees
    fov_vertical: float = 45.0    # degrees
    near_plane: float = 0.1
    far_plane: float = 100.0
    
    def is_in_frustum(self, cam_pos: Vector3D, cam_rot: Vector3D, target_pos: Vector3D) -> bool:
        """Check if a point is within the camera's viewing frustum"""
        dx = target_pos.x - cam_pos.x
        dy = target_pos.y - cam_pos.y
        dz = target_pos.z - cam_pos.z
        distance = math.sqrt(dx*dx + dy*dy + dz*dz)
        
        if distance < self.near_plane or distance > self.far_plane:
            return False
        
        target_yaw = math.degrees(math.atan2(dx, dz))
        target_pitch = math.degrees(math.atan2(dy, math.sqrt(dx*dx + dz*dz)))
        
        yaw_diff = abs(self._angle_diff(target_yaw, cam_rot.y))
        pitch_diff = abs(self._angle_diff(target_pitch, cam_rot.x))
        
        return yaw_diff <= self.fov_horizontal / 2 and pitch_diff <= self.fov_vertical / 2
    
    @staticmethod
    def _angle_diff(a: float, b: float) -> float:
        diff = (a - b + 180) % 360 - 180
        return diff


@dataclass
class VisibleObject:
    """Represents an object visible to the camera"""
    object_id: str
    object_type: str
    position: Vector3D
    distance: float
    screen_position: Tuple[float, float]  # Normalized [-1, 1]
    occlusion_factor: float = 0.0
    
    def dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "position": self.position.dict(),
            "distance": self.distance,
            "screen_position": self.screen_position,
            "occlusion_factor": self.occlusion_factor
        }


@dataclass
class CameraFrame:
    """Represents a single frame captured by the camera"""
    frame_id: int
    timestamp: float
    camera_id: str
    camera_position: Vector3D
    camera_rotation: Vector3D
    visible_avatars: List[VisibleObject] = field(default_factory=list)
    visible_objects: List[VisibleObject] = field(default_factory=list)
    frame_quality: str = "good"  # good, poor, blocked
    exposure_level: float = 1.0
    focus_target: Optional[str] = None
    
    def dict(self) -> Dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "camera_id": self.camera_id,
            "camera_position": self.camera_position.dict(),
            "camera_rotation": self.camera_rotation.dict(),
            "visible_avatars": [v.dict() for v in self.visible_avatars],
            "visible_objects": [v.dict() for v in self.visible_objects],
            "frame_quality": self.frame_quality,
            "exposure_level": self.exposure_level,
            "focus_target": self.focus_target
        }


class StreamQuality(Enum):
    LOW = "360p"
    MEDIUM = "720p"
    HIGH = "1080p"
    ULTRA = "4K"


@dataclass
class StreamConfig:
    """Configuration for camera streaming"""
    quality: StreamQuality = StreamQuality.MEDIUM
    fps: int = 30
    bitrate: int = 5000
    encoding: str = "H264"
    buffer_size: int = 60  # frames


# ============================================================================
# VISION-ENABLED CAMERA BOT
# ============================================================================

@dataclass
class VisionCameraBot:
    """Camera bot with vision capabilities integrated with PubCast"""
    camera_id: str
    world_id: str
    position: Vector3D
    rotation: Vector3D
    target_avatar_id: Optional[str] = None
    shot_type: str = "medium"
    motion_style: str = "steady"
    
    # Vision components
    frustum: CameraFrustum = field(default_factory=CameraFrustum)
    stream_config: StreamConfig = field(default_factory=StreamConfig)
    is_streaming: bool = False
    frame_buffer: List[CameraFrame] = field(default_factory=list)
    frame_counter: int = 0
    
    # Integration with CameraManager
    camera_source: Optional[CameraSource] = None
    
    # Vision statistics
    visible_count: int = 0
    last_frame: Optional[CameraFrame] = None
    
    def world_to_screen(self, world_pos: Vector3D) -> Tuple[float, float]:
        """Convert world coordinates to normalized screen space [-1, 1]"""
        dx = world_pos.x - self.position.x
        dy = world_pos.y - self.position.y
        dz = world_pos.z - self.position.z
        
        screen_x = math.atan2(dx, dz) / math.radians(self.frustum.fov_horizontal / 2)
        screen_y = math.atan2(dy, math.sqrt(dx*dx + dz*dz)) / math.radians(self.frustum.fov_vertical / 2)
        
        return (screen_x, screen_y)
    
    def capture_visible_objects(self, scene_objects: List[Dict[str, Any]]) -> List[VisibleObject]:
        """Determine which objects are visible to this camera"""
        visible = []
        
        for obj in scene_objects:
            obj_pos = Vector3D(
                obj.get("x", 0),
                obj.get("y", 0),
                obj.get("z", 0)
            )
            
            if self.frustum.is_in_frustum(self.position, self.rotation, obj_pos):
                distance = self.position.distance_to(obj_pos)
                screen_pos = self.world_to_screen(obj_pos)
                
                visible.append(VisibleObject(
                    object_id=obj.get("id", "unknown"),
                    object_type=obj.get("type", "generic"),
                    position=obj_pos,
                    distance=distance,
                    screen_position=screen_pos,
                    occlusion_factor=0.0
                ))
        
        return visible
    
    def capture_frame(self, scene_objects: List[Dict[str, Any]], 
                     lights: List[Dict[str, Any]] = None) -> CameraFrame:
        """Capture a complete frame with all visible elements"""
        visible_objects = self.capture_visible_objects(scene_objects)
        
        # Separate avatars from other objects
        visible_avatars = [v for v in visible_objects if v.object_type == "avatar"]
        visible_props = [v for v in visible_objects if v.object_type != "avatar"]
        
        # Evaluate frame quality
        frame_quality = "good"
        if not visible_avatars and self.target_avatar_id:
            frame_quality = "blocked"
        elif self.target_avatar_id and not any(v.object_id == self.target_avatar_id for v in visible_avatars):
            frame_quality = "poor"
        
        # Calculate exposure
        exposure = self._calculate_exposure(lights or [])
        
        frame = CameraFrame(
            frame_id=self.frame_counter,
            timestamp=time.time(),
            camera_id=self.camera_id,
            camera_position=Vector3D(self.position.x, self.position.y, self.position.z),
            camera_rotation=Vector3D(self.rotation.x, self.rotation.y, self.rotation.z),
            visible_avatars=visible_avatars,
            visible_objects=visible_props,
            frame_quality=frame_quality,
            exposure_level=exposure,
            focus_target=self.target_avatar_id
        )
        
        self.frame_counter += 1
        self.last_frame = frame
        self.visible_count = len(visible_avatars) + len(visible_props)
        
        # Add to buffer if streaming
        if self.is_streaming:
            self.frame_buffer.append(frame)
            if len(self.frame_buffer) > self.stream_config.buffer_size:
                self.frame_buffer.pop(0)
        
        return frame
    
    def _calculate_exposure(self, lights: List[Dict[str, Any]]) -> float:
        """Calculate exposure level based on nearby lights"""
        total_light = 0.0
        for light in lights:
            light_pos = Vector3D(
                light.get("x", 0),
                light.get("y", 0),
                light.get("z", 0)
            )
            distance = self.position.distance_to(light_pos)
            if distance < 20:
                intensity = light.get("intensity", 1.0)
                total_light += intensity / (distance + 0.1)
        return min(max(total_light / 2.0, 0.1), 3.0)
    
    def start_stream(self, quality: StreamQuality = StreamQuality.MEDIUM):
        """Start streaming camera feed"""
        self.stream_config.quality = quality
        self.is_streaming = True
        self.frame_buffer.clear()
        logger.info("stream_start")
    
    def stop_stream(self):
        """Stop streaming camera feed"""
        self.is_streaming = False
        logger.info("stream_stop")
    
    def get_stream_stats(self) -> Dict[str, Any]:
        """Get streaming statistics"""
        return {
            "camera_id": self.camera_id,
            "is_streaming": self.is_streaming,
            "quality": self.stream_config.quality.value,
            "fps": self.stream_config.fps,
            "buffer_frames": len(self.frame_buffer),
            "total_frames": self.frame_counter,
            "last_visible_count": self.visible_count,
            "frame_quality": self.last_frame.frame_quality if self.last_frame else "unknown"
        }
    
    def get_frame_report(self) -> Dict[str, Any]:
        """Get detailed report of what the camera currently sees"""
        if not self.last_frame:
            return {"camera_id": self.camera_id, "status": "no_frames"}
        
        frame = self.last_frame
        return {
            "camera_id": self.camera_id,
            "frame_id": frame.frame_id,
            "position": frame.camera_position.dict(),
            "rotation": frame.camera_rotation.dict(),
            "quality": frame.frame_quality,
            "exposure": frame.exposure_level,
            "visible_avatars": len(frame.visible_avatars),
            "visible_objects": len(frame.visible_objects),
            "avatars": [
                {
                    "id": v.object_id,
                    "distance": round(v.distance, 2),
                    "screen_pos": [round(v.screen_position[0], 2), round(v.screen_position[1], 2)]
                }
                for v in sorted(frame.visible_avatars, key=lambda x: x.distance)
            ]
        }


# ============================================================================
# PUBCAST STREAMING MANAGER
# ============================================================================

class PubcastVisionManager:
    """Manages camera vision and streaming for PubCast"""
    
    def __init__(self, camera_manager: Optional[CameraManager] = None, data_dir: Optional[Path] = None):
        self.camera_manager = camera_manager
        self.data_dir = data_dir or Path("./data")
        
        # Vision cameras
        self.vision_cameras: Dict[str, VisionCameraBot] = {}
        
        # Broadcasting state
        self.broadcast_name = "PubCast Live"
        self.is_broadcasting = False
        self.primary_camera: Optional[str] = None
        
        # Scene tracking
        self.current_scene_objects: List[Dict[str, Any]] = []
        self.current_lights: List[Dict[str, Any]] = []
        
        # Performance metrics
        self.frames_captured = 0
        self.broadcasts_started = 0
        
        # WebSocket connections for streaming
        self.stream_clients: Set[Any] = set()
        
        logger.info("vision_manager_init")
    
    async def register_vision_camera(self, config: Dict[str, Any]) -> bool:
        """Register a new vision-enabled camera"""
        try:
            camera_id = config.get("camera_id")
            if not camera_id:
                logger.error("vision_camera_register_failed")
                return False
            
            # Create vision camera bot
            bot = VisionCameraBot(
                camera_id=camera_id,
                world_id=config.get("world_id", "default"),
                position=Vector3D(
                    config.get("position_x", 0),
                    config.get("position_y", 2),
                    config.get("position_z", -10)
                ),
                rotation=Vector3D(0, 0, 0),
                target_avatar_id=config.get("target_avatar"),
                shot_type=config.get("shot_type", "medium"),
                motion_style=config.get("motion_style", "steady")
            )
            
            # Configure FOV if specified
            if "fov" in config:
                bot.frustum.fov_horizontal = config["fov"]
            
            # Register with camera manager if available
            if self.camera_manager and CAMERA_MANAGER_AVAILABLE:
                camera_config = {
                    "camera_id": camera_id,
                    "name": config.get("name", f"Vision Camera {camera_id}"),
                    "type": "voxel_engine",
                    "source": f"vision://{camera_id}",
                    "resolution": f"{config.get('width', 1920)}x{config.get('height', 1080)}",
                    "fps": config.get("fps", 30),
                    "ptz": "software",
                    "recording": True
                }
                await self.camera_manager.register_camera(camera_config)
            
            self.vision_cameras[camera_id] = bot
            logger.info("vision_camera_registered")
            return True
            
        except Exception as e:
            logger.error("vision_camera_register_error: %s", e)
            return False
    
    def update_scene_objects(self, objects: List[Dict[str, Any]], lights: List[Dict[str, Any]] = None):
        """Update the current scene objects and lights"""
        self.current_scene_objects = objects
        self.current_lights = lights or []
    
    async def update_all_cameras(self) -> Dict[str, CameraFrame]:
        """Update all vision cameras and capture frames"""
        frames = {}
        
        for camera_id, bot in self.vision_cameras.items():
            try:
                frame = bot.capture_frame(self.current_scene_objects, self.current_lights)
                frames[camera_id] = frame
                self.frames_captured += 1
                
                # Broadcast frame to WebSocket clients if streaming
                if bot.is_streaming and self.stream_clients:
                    await self._broadcast_frame(frame)
                
            except Exception as e:
                logger.error("camera_update_error: %s", e)
        
        return frames
    
    async def _broadcast_frame(self, frame: CameraFrame):
        """Broadcast frame data to connected WebSocket clients"""
        frame_data = {
            "type": "camera_frame",
            "data": frame.dict()
        }
        
        disconnected = set()
        for client in self.stream_clients:
            try:
                await client.send_json(frame_data)
            except Exception:
                disconnected.add(client)
        
        # Remove disconnected clients
        self.stream_clients -= disconnected
    
    def start_broadcast(self, quality: StreamQuality = StreamQuality.HIGH):
        """Start broadcasting from all registered cameras"""
        for bot in self.vision_cameras.values():
            bot.start_stream(quality)
        
        self.is_broadcasting = True
        self.broadcasts_started += 1
        logger.info("broadcast_started quality=%s", quality.value)
    
    def stop_broadcast(self):
        """Stop broadcasting"""
        for bot in self.vision_cameras.values():
            bot.stop_stream()
        
        self.is_broadcasting = False
        logger.info("broadcast_stopped")
    
    def set_primary_camera(self, camera_id: str):
        """Set the primary broadcasting camera"""
        if camera_id in self.vision_cameras:
            self.primary_camera = camera_id
            logger.info("primary_camera_set")
            
            # Update camera manager if available
            if self.camera_manager and CAMERA_MANAGER_AVAILABLE:
                asyncio.create_task(self.camera_manager.switch_program(camera_id, "CUT"))
        else:
            logger.error("primary_camera_set_failed")
    
    def get_best_camera(self) -> Optional[str]:
        """Automatically select the best camera based on frame quality"""
        good_cameras = [
            (camera_id, bot) 
            for camera_id, bot in self.vision_cameras.items()
            if bot.last_frame and bot.last_frame.frame_quality == "good"
        ]
        
        if not good_cameras:
            return list(self.vision_cameras.keys())[0] if self.vision_cameras else None
        
        # Select camera with most visible avatars
        best_camera_id, _ = max(
            good_cameras, 
            key=lambda x: len(x[1].last_frame.visible_avatars)
        )
        return best_camera_id
    
    def get_camera_stats(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific camera"""
        bot = self.vision_cameras.get(camera_id)
        if not bot:
            return None
        return bot.get_stream_stats()
    
    def get_all_cameras_status(self) -> Dict[str, Any]:
        """Get status of all cameras"""
        return {
            "broadcast_name": self.broadcast_name,
            "is_broadcasting": self.is_broadcasting,
            "primary_camera": self.primary_camera,
            "camera_count": len(self.vision_cameras),
            "cameras": {
                camera_id: bot.get_stream_stats()
                for camera_id, bot in self.vision_cameras.items()
            },
            "frames_captured": self.frames_captured,
            "broadcasts_started": self.broadcasts_started
        }
    
    def get_camera_view(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Get what a specific camera currently sees"""
        bot = self.vision_cameras.get(camera_id)
        if not bot:
            return None
        return bot.get_frame_report()
    
    def get_all_camera_views(self) -> Dict[str, Any]:
        """Get what all cameras currently see"""
        return {
            camera_id: bot.get_frame_report()
            for camera_id, bot in self.vision_cameras.items()
        }
    
    async def add_stream_client(self, websocket):
        """Add a WebSocket client for streaming"""
        self.stream_clients.add(websocket)
        logger.info("stream_client_added")
    
    async def remove_stream_client(self, websocket):
        """Remove a WebSocket client"""
        self.stream_clients.discard(websocket)
        logger.info("stream_client_removed")
    
    async def shutdown(self):
        """Shutdown the vision manager"""
        logger.info("vision_manager_shutdown")
        self.stop_broadcast()
        self.vision_cameras.clear()
        self.stream_clients.clear()


# ============================================================================
# CONVENIENCE FUNCTIONS FOR INTEGRATION
# ============================================================================

def create_integrated_vision_manager(camera_manager: Optional[CameraManager] = None, 
                                     data_dir: Optional[Path] = None) -> PubcastVisionManager:
    """
    Create a vision manager integrated with existing PubCast infrastructure.
    
    Args:
        camera_manager: Existing CameraManager instance (optional)
        data_dir: Data directory path (optional)
    
    Returns:
        Configured PubcastVisionManager instance
    """
    return PubcastVisionManager(camera_manager, data_dir)


async def setup_default_cameras(vision_manager: PubcastVisionManager) -> bool:
    """
    Setup default camera configuration for PubCast.
    
    Creates:
    - Wide shot camera
    - Medium shot camera
    - Close-up camera
    """
    cameras = [
        {
            "camera_id": "cam_wide",
            "name": "Wide Shot",
            "world_id": "studio",
            "position_x": -8,
            "position_y": 3,
            "position_z": -12,
            "shot_type": "wide",
            "motion_style": "steady",
            "fov": 90.0
        },
        {
            "camera_id": "cam_medium",
            "name": "Medium Shot",
            "world_id": "studio",
            "position_x": 6,
            "position_y": 2,
            "position_z": -8,
            "shot_type": "medium",
            "motion_style": "dolly",
            "fov": 60.0
        },
        {
            "camera_id": "cam_closeup",
            "name": "Close-up",
            "world_id": "studio",
            "position_x": 2,
            "position_y": 1.8,
            "position_z": -3,
            "shot_type": "closeup",
            "motion_style": "handheld",
            "fov": 40.0
        }
    ]
    
    success = True
    for cam_config in cameras:
        result = await vision_manager.register_vision_camera(cam_config)
        success = success and result
    
    return success
