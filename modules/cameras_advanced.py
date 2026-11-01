#!/usr/bin/env python3
"""
PubCast AI - Advanced Camera Management System
Copyright (c) 2024-2025 Rear View Foresight LLC
"Feic Mo Chroí - See My Heart"

Complete camera management system with professional broadcast features,
multi-source handling, and seamless integration with the PubCast platform.
"""

import asyncio
import logging
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import uuid
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CameraTransport(str, Enum):
    """Camera transport types supported by PubCast"""
    USB_WEBCAM = "usb_webcam"
    IP_CAMERA = "ip_camera"
    NDI_SOURCE = "ndi_source"
    OBS_VIRTUAL = "obs_virtual"
    VOXEL_ENGINE = "voxel_engine"
    SCREEN_CAPTURE = "screen_capture"
    FILE_PLAYBACK = "file_playback"
    VIRTUAL_BACKGROUND = "virtual_background"

class CameraStatus(str, Enum):
    """Camera operational status"""
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ONLINE = "online"
    RECORDING = "recording"
    ERROR = "error"
    MAINTENANCE = "maintenance"

class CameraRole(str, Enum):
    """Camera roles in production"""
    PROGRAM = "program"        # Currently live/program output
    PREVIEW = "preview"        # Selected for next cut
    STANDBY = "standby"        # Available but not selected
    BACKUP = "backup"          # Emergency fallback
    DISABLED = "disabled"      # Temporarily disabled

@dataclass
class CameraMetadata:
    """Rich metadata for camera sources"""
    name: str
    transport: CameraTransport
    status: CameraStatus = CameraStatus.OFFLINE
    role: CameraRole = CameraRole.STANDBY
    
    # Connection details
    connection_string: str = ""
    username: str = ""
    password: str = ""
    port: int = 0
    
    # Video specifications
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    format: str = "h264"
    
    # Quality metrics
    bitrate: int = 5000000  # 5 Mbps default
    latency_ms: float = 0.0
    frame_drops: int = 0
    signal_strength: float = 100.0
    
    # Position and orientation
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    fov: float = 90.0
    
    # Production settings
    scene_name: str = ""
    preset_name: str = ""
    auto_switch_enabled: bool = False
    effects_enabled: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_frame_at: float = 0.0
    last_error_at: float = 0.0
    error_message: str = ""
    
    # Analytics
    total_frames: int = 0
    total_errors: int = 0
    uptime_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CameraMetadata':
        """Create from dictionary"""
        return cls(**data)

class CameraSource:
    """Individual camera source with real-time monitoring"""
    
    def __init__(self, camera_id: str, metadata: CameraMetadata):
        self.id = camera_id
        self.metadata = metadata
        self.is_capturing = False
        self.capture_process: Optional[subprocess.Popen] = None
        self.frame_buffer: List[bytes] = []
        self.buffer_lock = threading.Lock()
        self.stats_lock = threading.Lock()
        
        # Performance monitoring
        self.frame_times: List[float] = []
        self.last_stats_update = time.time()
        self.connection_attempts = 0
        self.max_connection_attempts = 5

        # Voxel engine TCP connection
        self._voxel_reader = None
        self._voxel_writer = None
        
    async def connect(self) -> bool:
        """Establish connection to camera source"""
        try:
            logger.info(f"Connecting to camera {self.id} ({self.metadata.transport.value})")
            self.metadata.status = CameraStatus.CONNECTING
            self.metadata.error_message = ""
            self.connection_attempts += 1
            success = await self._establish_connection()
            
            if success:
                self.metadata.status = CameraStatus.ONLINE
                self.metadata.last_frame_at = time.time()
                logger.info(f"Camera {self.id} connected successfully")
                return True
            else:
                self.metadata.status = CameraStatus.ERROR
                if not self.metadata.error_message:
                    self.metadata.error_message = f"Failed to connect after {self.connection_attempts} attempts"
                logger.error("Failed to connect camera %s: %s", self.id, self.metadata.error_message)
                return False
                
        except Exception as e:
            self.metadata.status = CameraStatus.ERROR
            self.metadata.error_message = str(e)
            self.metadata.last_error_at = time.time()
            logger.error(f"Camera {self.id} connection error: {e}")
            return False
    
    async def _establish_connection(self) -> bool:
        """Transport-specific connection logic"""
        transport = self.metadata.transport
        
        if transport == CameraTransport.USB_WEBCAM:
            return await self._connect_usb_webcam()
        elif transport == CameraTransport.IP_CAMERA:
            return await self._connect_ip_camera()
        elif transport == CameraTransport.NDI_SOURCE:
            return await self._connect_ndi_source()
        elif transport == CameraTransport.OBS_VIRTUAL:
            return await self._connect_obs_virtual()
        elif transport == CameraTransport.VOXEL_ENGINE:
            return await self._connect_voxel_engine()
        elif transport == CameraTransport.SCREEN_CAPTURE:
            return await self._connect_screen_capture()
        elif transport == CameraTransport.FILE_PLAYBACK:
            return await self._connect_file_playback()
        else:
            logger.warning(f"Unsupported transport: {transport}")
            return False
    
    async def _connect_usb_webcam(self) -> bool:
        """Connect to USB webcam via V4L2/DirectShow"""
        try:
            device_path = self.metadata.connection_string or "/dev/video0"
            
            # Test connection with ffprobe
            cmd = [
                "ffprobe", 
                "-v", "quiet",
                "-f", "video4linux2" if "linux" in device_path else "dshow",
                "-i", device_path,
                "-show_streams",
                "-select_streams", "v:0"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Parse video specs from ffprobe output
                self._parse_ffprobe_output(stdout.decode())
                return True
            else:
                self.metadata.error_message = stderr.decode()
                return False
                
        except Exception as e:
            self.metadata.error_message = f"USB webcam error: {e}"
            return False
    
    async def _connect_ip_camera(self) -> bool:
        """Connect to IP camera via RTSP/HTTP"""
        try:
            # Build RTSP URL
            if self.metadata.username and self.metadata.password:
                url = f"rtsp://{self.metadata.username}:{self.metadata.password}@{self.metadata.connection_string}"
            else:
                url = f"rtsp://{self.metadata.connection_string}"
            
            if self.metadata.port:
                url += f":{self.metadata.port}"
            
            # Test RTSP stream
            cmd = [
                "ffprobe",
                "-v", "quiet", 
                "-rtsp_transport", "tcp",
                "-i", url,
                "-show_streams",
                "-select_streams", "v:0"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self._parse_ffprobe_output(stdout.decode())
                return True
            else:
                self.metadata.error_message = stderr.decode()
                return False
                
        except Exception as e:
            self.metadata.error_message = f"IP camera error: {e}"
            return False
    
    async def _connect_ndi_source(self) -> bool:
        """NDI requires the native NDI SDK, which this runtime does not bundle."""
        self.metadata.error_message = "NDI capture backend is not installed"
        logger.warning("NDI source %s unavailable: %s", self.id, self.metadata.error_message)
        return False
    
    async def _connect_obs_virtual(self) -> bool:
        """Connect to OBS Virtual Camera"""
        try:
            # OBS Virtual Camera typically shows up as a standard webcam
            return await self._connect_usb_webcam()
        except Exception as e:
            self.metadata.error_message = f"OBS Virtual Camera error: {e}"
            return False
    
    async def _connect_voxel_engine(self) -> bool:
        """
        Connect to PubWorld voxel engine via TCP.
        Sends a HELLO handshake and waits for acknowledgement.
        Voxel engine listens on tcp://localhost:9010 by default.
        """
        import asyncio
        try:
            conn_str = self.metadata.connection_string or "tcp://localhost:9010"
            # Parse tcp://host:port
            if conn_str.startswith("tcp://"):
                conn_str = conn_str[6:]
            host, _, port_str = conn_str.rpartition(":")
            host = host or "127.0.0.1"
            port = int(port_str) if port_str.isdigit() else 9010

            # Attempt TCP connection with timeout
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )

            # Send HELLO handshake: {"type":"hello","client":"pubcast_camera"}
            import json
            hello = json.dumps({
                "type":   "hello",
                "client": "pubcast_camera",
                "width":  self.metadata.width,
                "height": self.metadata.height,
                "fps":    self.metadata.fps,
                "format": self.metadata.format,
            }).encode() + b'\n'

            writer.write(hello)
            await writer.drain()

            # Wait for ACK with timeout
            try:
                ack_line = await asyncio.wait_for(reader.readline(), timeout=3.0)
                ack = json.loads(ack_line.decode().strip())
                if ack.get("type") == "ack":
                    # Store connection for frame reads
                    self._voxel_reader = reader
                    self._voxel_writer = writer
                    logger.info(f"[VoxelCamera] Connected to {host}:{port}")
                    return True
                else:
                    logger.warning(f"[VoxelCamera] Unexpected ACK: {ack}")
                    writer.close()
                    return False
            except asyncio.TimeoutError:
                logger.warning(f"[VoxelCamera] No ACK from {host}:{port} — voxel engine is not ready")
                writer.close()
                self.metadata.error_message = f"No voxel-engine ACK from {host}:{port}"
                return False

        except asyncio.TimeoutError:
            self.metadata.error_message = "Voxel engine connection timed out"
            logger.warning("[VoxelCamera] %s", self.metadata.error_message)
            return False
        except ConnectionRefusedError:
            self.metadata.error_message = "Voxel engine connection refused"
            logger.warning("[VoxelCamera] %s", self.metadata.error_message)
            return False
        except Exception as e:
            self.metadata.error_message = f"Voxel engine connect error: {e}"
            logger.error(f"[VoxelCamera] Connect error: {e}")
            return False
    
    async def _connect_screen_capture(self) -> bool:
        """Connect to screen capture source"""
        try:
            # Screen capture via ffmpeg
            display = self.metadata.connection_string or ":0.0"
            
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-f", "x11grab",
                "-i", display,
                "-show_streams",
                "-select_streams", "v:0"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self._parse_ffprobe_output(stdout.decode())
                return True
            else:
                self.metadata.error_message = stderr.decode()
                return False
                
        except Exception as e:
            self.metadata.error_message = f"Screen capture error: {e}"
            return False
    
    async def _connect_file_playback(self) -> bool:
        """Connect to file playback source"""
        try:
            file_path = self.metadata.connection_string
            
            if not Path(file_path).exists():
                self.metadata.error_message = f"File not found: {file_path}"
                return False
            
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-i", file_path,
                "-show_streams",
                "-select_streams", "v:0"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self._parse_ffprobe_output(stdout.decode())
                return True
            else:
                self.metadata.error_message = stderr.decode()
                return False
                
        except Exception as e:
            self.metadata.error_message = f"File playback error: {e}"
            return False
    
    def _parse_ffprobe_output(self, output: str):
        """Parse ffprobe output to extract video specifications"""
        lines = output.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('width='):
                self.metadata.width = int(line.split('=')[1])
            elif line.startswith('height='):
                self.metadata.height = int(line.split('=')[1])
            elif line.startswith('r_frame_rate='):
                rate = line.split('=')[1]
                if '/' in rate:
                    num, den = rate.split('/')
                    self.metadata.fps = float(num) / float(den)
                else:
                    self.metadata.fps = float(rate)
    
    def _capture_input_args(self) -> Optional[List[str]]:
        """Return ffmpeg input arguments for transports with a real capture backend."""
        transport = self.metadata.transport
        source = self.metadata.connection_string
        if transport in {CameraTransport.USB_WEBCAM, CameraTransport.OBS_VIRTUAL}:
            device = source or "/dev/video0"
            input_format = "video4linux2" if device.startswith("/dev/") else "dshow"
            return ["-f", input_format, "-i", device]
        if transport == CameraTransport.IP_CAMERA:
            if self.metadata.username and self.metadata.password:
                url = f"rtsp://{self.metadata.username}:{self.metadata.password}@{source}"
            else:
                url = f"rtsp://{source}"
            if self.metadata.port:
                url += f":{self.metadata.port}"
            return ["-rtsp_transport", "tcp", "-i", url]
        if transport == CameraTransport.SCREEN_CAPTURE:
            return ["-f", "x11grab", "-i", source or ":0.0"]
        if transport == CameraTransport.FILE_PLAYBACK:
            return ["-re", "-i", source]
        return None

    async def start_capture(self) -> bool:
        """Start a real ffmpeg raw-frame capture pipeline for supported transports."""
        if self.is_capturing:
            return True
        input_args = self._capture_input_args()
        if input_args is None:
            self.metadata.status = CameraStatus.ERROR
            self.metadata.error_message = f"No frame capture backend for {self.metadata.transport.value}"
            logger.warning("Camera %s cannot capture: %s", self.id, self.metadata.error_message)
            return False
        try:
            self.is_capturing = True
            self.metadata.status = CameraStatus.ONLINE
            self.metadata.error_message = ""
            loop = asyncio.get_running_loop()
            self.capture_task = loop.run_in_executor(None, self._capture_frames, input_args)
            logger.info("Started real capture for camera %s", self.id)
            return True
        except Exception as exc:
            self.is_capturing = False
            self.metadata.status = CameraStatus.ERROR
            self.metadata.error_message = str(exc)
            logger.error("Failed to start capture for camera %s: %s", self.id, exc)
            return False

    def _capture_frames(self, input_args: List[str]) -> None:
        """Read RGB frames from ffmpeg; never synthesize frames as capture success."""
        frame_size = int(self.metadata.width) * int(self.metadata.height) * 3
        cmd = [
            "ffmpeg", "-loglevel", "error", *input_args,
            "-vf", f"scale={int(self.metadata.width)}:{int(self.metadata.height)}",
            "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",
        ]
        try:
            self.capture_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=frame_size * 2
            )
            if self.capture_process.stdout is None:
                raise RuntimeError("ffmpeg capture stdout is unavailable")
            while self.is_capturing:
                started = time.time()
                frame_data = self.capture_process.stdout.read(frame_size)
                if len(frame_data) != frame_size:
                    stderr = b""
                    if self.capture_process.stderr is not None:
                        stderr = self.capture_process.stderr.read() or b""
                    raise RuntimeError(
                        "camera stream ended before a complete frame" +
                        (f": {stderr.decode(errors='replace').strip()}" if stderr else "")
                    )
                with self.buffer_lock:
                    self.frame_buffer.append(frame_data)
                    if len(self.frame_buffer) > 30:
                        self.frame_buffer.pop(0)
                elapsed = time.time() - started
                with self.stats_lock:
                    self.frame_times.append(elapsed)
                    if len(self.frame_times) > 100:
                        self.frame_times.pop(0)
                    self.metadata.last_frame_at = time.time()
                    self.metadata.total_frames += 1
        except Exception as exc:
            if self.is_capturing:
                self.metadata.status = CameraStatus.ERROR
                self.metadata.error_message = str(exc)
                self.metadata.last_error_at = time.time()
                self.metadata.total_errors += 1
                logger.error("Capture error for camera %s: %s", self.id, exc)
        finally:
            proc = self.capture_process
            self.capture_process = None
            if proc is not None:
                try:
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=2)
                finally:
                    # The capture worker owns these streams. Reap first, then
                    # release both pipes even if ffmpeg already exited itself.
                    for stream in (proc.stdout, proc.stderr, proc.stdin):
                        if stream is not None:
                            stream.close()
            self.is_capturing = False

    async def stop_capture(self):
        """Stop capturing frames and terminate the owned ffmpeg process."""
        self.is_capturing = False
        proc = self.capture_process
        if proc is not None and proc.poll() is None:
            proc.terminate()
        if hasattr(self, "capture_task"):
            try:
                await asyncio.wait_for(asyncio.shield(self.capture_task), timeout=3.0)
            except asyncio.TimeoutError:
                proc = self.capture_process
                if proc is not None and proc.poll() is None:
                    proc.kill()
        self.metadata.status = CameraStatus.OFFLINE
        logger.info("Stopped capture for camera %s", self.id)

    def get_latest_frame(self) -> Optional[bytes]:
        """Get the most recent frame"""
        with self.buffer_lock:
            return self.frame_buffer[-1] if self.frame_buffer else None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get camera performance statistics"""
        with self.stats_lock:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times) if self.frame_times else 0
            
            return {
                "id": self.id,
                "name": self.metadata.name,
                "status": self.metadata.status.value,
                "role": self.metadata.role.value,
                "transport": self.metadata.transport.value,
                "resolution": f"{self.metadata.width}x{self.metadata.height}",
                "fps": self.metadata.fps,
                "total_frames": self.metadata.total_frames,
                "total_errors": self.metadata.total_errors,
                "frame_drops": self.metadata.frame_drops,
                "latency_ms": self.metadata.latency_ms,
                "signal_strength": self.metadata.signal_strength,
                "avg_frame_time_ms": avg_frame_time * 1000,
                "last_frame_ago": time.time() - self.metadata.last_frame_at if self.metadata.last_frame_at else 0,
                "uptime_seconds": self.metadata.uptime_seconds,
                "error_message": self.metadata.error_message
            }

class AdvancedCameraManager:
    """Advanced camera management with professional broadcast features"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("data/cameras.json")
        self.sources: Dict[str, CameraSource] = {}
        self.executor = ThreadPoolExecutor(max_workers=8)
        
        # Production state
        self.program_source: Optional[str] = None
        self.preview_source: Optional[str] = None
        self.recording_sources: List[str] = []
        
        # Monitoring
        self.monitoring_enabled = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # Auto-switching
        self.auto_switching_enabled = False
        self.auto_switch_rules: Dict[str, Any] = {}
        
        # Load configuration
        self.load_configuration()
    
    def load_configuration(self):
        """Load camera configuration from file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                for camera_data in config.get('cameras', []):
                    metadata = CameraMetadata.from_dict(camera_data)
                    camera = CameraSource(camera_data['id'], metadata)
                    self.sources[camera_data['id']] = camera
                
                # Load production state
                production_state = config.get('production_state', {})
                self.program_source = production_state.get('program_source')
                self.preview_source = production_state.get('preview_source')
                self.recording_sources = production_state.get('recording_sources', [])
                
                logger.info(f"Loaded configuration for {len(self.sources)} cameras")
            else:
                logger.info("No camera configuration found, starting with defaults")
                self._create_default_cameras()
                
        except Exception as e:
            logger.error(f"Failed to load camera configuration: {e}")
            self._create_default_cameras()
    
    def _create_default_cameras(self):
        """Create default camera setup"""
        default_cameras = [
            {
                "id": "cam1",
                "metadata": CameraMetadata(
                    name="Main Camera",
                    transport=CameraTransport.USB_WEBCAM,
                    connection_string="/dev/video0",
                    role=CameraRole.PROGRAM
                )
            },
            {
                "id": "cam2", 
                "metadata": CameraMetadata(
                    name="Secondary Camera",
                    transport=CameraTransport.USB_WEBCAM,
                    connection_string="/dev/video1",
                    role=CameraRole.PREVIEW
                )
            },
            {
                "id": "voxel",
                "metadata": CameraMetadata(
                    name="Voxel Engine",
                    transport=CameraTransport.VOXEL_ENGINE,
                    connection_string="tcp://localhost:9001",
                    role=CameraRole.STANDBY,
                    width=1920,
                    height=1080,
                    fps=60.0
                )
            },
            {
                "id": "screen",
                "metadata": CameraMetadata(
                    name="Screen Capture", 
                    transport=CameraTransport.SCREEN_CAPTURE,
                    connection_string=":0.0",
                    role=CameraRole.STANDBY
                )
            }
        ]
        
        for camera_config in default_cameras:
            camera = CameraSource(camera_config["id"], camera_config["metadata"])
            self.sources[camera_config["id"]] = camera
        
        # Set initial program and preview
        if "cam1" in self.sources:
            self.program_source = "cam1"
            self.sources["cam1"].metadata.role = CameraRole.PROGRAM
            
        if "cam2" in self.sources:
            self.preview_source = "cam2"
            self.sources["cam2"].metadata.role = CameraRole.PREVIEW
    
    def save_configuration(self):
        """Save current camera configuration"""
        try:
            config = {
                "cameras": [
                    {
                        "id": camera_id,
                        **source.metadata.to_dict()
                    }
                    for camera_id, source in self.sources.items()
                ],
                "production_state": {
                    "program_source": self.program_source,
                    "preview_source": self.preview_source,
                    "recording_sources": self.recording_sources
                },
                "auto_switch_rules": self.auto_switch_rules,
                "last_updated": time.time()
            }
            
            write_json(self.config_path, config)
                
            logger.info("Camera configuration saved")
            
        except Exception as e:
            logger.error(f"Failed to save camera configuration: {e}")
    
    async def initialize_all_cameras(self) -> Dict[str, bool]:
        """Initialize all configured cameras"""
        results = {}
        
        # Connect all cameras in parallel
        connection_tasks = [
            self.connect_camera(camera_id) 
            for camera_id in self.sources.keys()
        ]
        
        connection_results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        for camera_id, result in zip(self.sources.keys(), connection_results):
            if isinstance(result, Exception):
                results[camera_id] = False
                logger.error(f"Failed to initialize camera {camera_id}: {result}")
            else:
                results[camera_id] = result
        
        # Start monitoring
        await self.start_monitoring()
        
        logger.info(f"Camera initialization complete: {sum(results.values())}/{len(results)} cameras online")
        return results
    
    async def connect_camera(self, camera_id: str) -> bool:
        """Connect a specific camera"""
        if camera_id not in self.sources:
            logger.error(f"Camera {camera_id} not found")
            return False
        
        camera = self.sources[camera_id]
        success = await camera.connect()
        
        if success:
            # Start capturing if this is program/preview camera
            if camera_id in [self.program_source, self.preview_source]:
                await camera.start_capture()
        
        return success
    
    async def disconnect_camera(self, camera_id: str):
        """Disconnect a specific camera"""
        if camera_id in self.sources:
            await self.sources[camera_id].stop_capture()
            logger.info(f"Disconnected camera {camera_id}")
    
    async def cut_to_camera(self, camera_id: str) -> bool:
        """Perform immediate cut to specified camera"""
        if camera_id not in self.sources:
            logger.error(f"Camera {camera_id} not found")
            return False
        
        camera = self.sources[camera_id]
        if camera.metadata.status != CameraStatus.ONLINE:
            logger.error(f"Camera {camera_id} is not online")
            return False
        
        # Update roles
        if self.program_source:
            self.sources[self.program_source].metadata.role = CameraRole.STANDBY
        
        camera.metadata.role = CameraRole.PROGRAM
        self.program_source = camera_id
        
        # Ensure camera is capturing
        if not camera.is_capturing:
            await camera.start_capture()
        
        logger.info(f"Cut to camera {camera_id}")
        
        # Save state
        self.save_configuration()
        
        return True
    
    async def set_preview_camera(self, camera_id: str) -> bool:
        """Set preview camera for next transition"""
        if camera_id not in self.sources:
            logger.error(f"Camera {camera_id} not found")
            return False
        
        camera = self.sources[camera_id]
        if camera.metadata.status != CameraStatus.ONLINE:
            logger.error(f"Camera {camera_id} is not online")
            return False
        
        # Update roles
        if self.preview_source:
            self.sources[self.preview_source].metadata.role = CameraRole.STANDBY
        
        camera.metadata.role = CameraRole.PREVIEW
        self.preview_source = camera_id
        
        # Ensure camera is capturing
        if not camera.is_capturing:
            await camera.start_capture()
        
        logger.info(f"Set preview camera to {camera_id}")
        
        # Save state
        self.save_configuration()
        
        return True
    
    async def auto_transition(self, duration_seconds: float = 1.0) -> bool:
        """Perform auto transition from program to preview"""
        if not self.preview_source:
            logger.error("No preview camera set for transition")
            return False
        
        if not self.program_source:
            logger.error("No program camera set")
            return False
        
        preview_camera = self.sources[self.preview_source]
        if preview_camera.metadata.status != CameraStatus.ONLINE:
            logger.error(f"Preview camera {self.preview_source} is not online")
            return False
        
        # Camera-state transition only. Program video mixing is owned elsewhere.
        logger.info(f"Scheduling {duration_seconds}s source-state transition from {self.program_source} to {self.preview_source}")
        await asyncio.sleep(duration_seconds)
        
        # Swap program and preview
        old_program = self.program_source
        new_program = self.preview_source
        
        # Update roles
        self.sources[old_program].metadata.role = CameraRole.STANDBY
        self.sources[new_program].metadata.role = CameraRole.PROGRAM
        
        self.program_source = new_program
        self.preview_source = old_program
        self.sources[old_program].metadata.role = CameraRole.PREVIEW
        
        logger.info(f"Transition complete: {new_program} is now program")
        
        # Save state
        self.save_configuration()
        
        return True
    
    def add_camera(self, camera_id: str, metadata: CameraMetadata) -> bool:
        """Add a new camera source"""
        if camera_id in self.sources:
            logger.warning(f"Camera {camera_id} already exists")
            return False
        
        camera = CameraSource(camera_id, metadata)
        self.sources[camera_id] = camera
        
        logger.info(f"Added camera {camera_id}: {metadata.name}")
        
        # Save configuration
        self.save_configuration()
        
        return True
    
    def remove_camera(self, camera_id: str) -> bool:
        """Remove a camera source"""
        if camera_id not in self.sources:
            logger.warning(f"Camera {camera_id} not found")
            return False
        
        # Disconnect if connected
        _t = asyncio.create_task(self.disconnect_camera(camera_id))
        _t.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        
        # Update production state
        if self.program_source == camera_id:
            self.program_source = None
        if self.preview_source == camera_id:
            self.preview_source = None
        if camera_id in self.recording_sources:
            self.recording_sources.remove(camera_id)
        
        del self.sources[camera_id]
        
        logger.info(f"Removed camera {camera_id}")
        
        # Save configuration
        self.save_configuration()
        
        return True
    
    async def start_monitoring(self):
        """Start camera monitoring task"""
        if not self.monitoring_enabled:
            self.monitoring_enabled = True
            self.monitoring_task = asyncio.create_task(self._monitor_cameras())
            logger.info("Camera monitoring started")
    
    async def stop_monitoring(self):
        """Stop camera monitoring"""
        if self.monitoring_enabled:
            self.monitoring_enabled = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            logger.info("Camera monitoring stopped")
    
    async def _monitor_cameras(self):
        """Monitor camera health and performance"""
        while self.monitoring_enabled:
            try:
                current_time = time.time()
                
                for camera_id, camera in self.sources.items():
                    if camera.metadata.status == CameraStatus.ONLINE:
                        # Check for frame timeout
                        if camera.metadata.last_frame_at > 0:
                            frame_age = current_time - camera.metadata.last_frame_at
                            if frame_age > 5.0:  # 5 second timeout
                                camera.metadata.status = CameraStatus.ERROR
                                camera.metadata.error_message = "Frame timeout"
                                logger.warning(f"Camera {camera_id} frame timeout")
                        
                        # Update uptime
                        camera.metadata.uptime_seconds += 1.0
                        
                        # Calculate latency
                        with camera.stats_lock:
                            if camera.frame_times:
                                avg_frame_time = sum(camera.frame_times) / len(camera.frame_times)
                                camera.metadata.latency_ms = avg_frame_time * 1000
                
                # Auto-switching logic
                if self.auto_switching_enabled:
                    await self._check_auto_switch_rules()
                
                await asyncio.sleep(1.0)  # Monitor every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Camera monitoring error: {e}")
                await asyncio.sleep(1.0)
    
    async def _check_auto_switch_rules(self):
        """
        Check and apply auto-switching rules.
        Reads Switchblade priority vector if available.
        Locks camera during identity moments. Enables auto-switch otherwise.
        """
        # If Switchblade has issued a priority vector, read it
        vector = getattr(self, '_switchblade_vector', None)

        if vector is not None:
            # Identity moment: lock program camera — do not auto-switch
            if getattr(vector, 'identity_moment', False):
                return  # Hard lock — no switch during identity moments

            # If E4 is assisting, don't switch cameras — disrupts render budget
            if getattr(vector, 'e4_assist', False):
                return

        # Normal auto-switch logic: switch if program camera has errors
        if self.program_source and self.program_source in self.sources:
            program_cam = self.sources[self.program_source]
            if program_cam.metadata.status.value == 'error':
                # Find best available backup
                for cam_id, cam in self.sources.items():
                    if (cam_id != self.program_source and
                        cam.metadata.status.value == 'online' and
                        cam.metadata.role.value in ('preview', 'standby')):
                        logger.info(f"[CameraManager] Auto-switch: {self.program_source} → {cam_id} (program cam error)")
                        await self.cut_to_camera(cam_id)
                        break
    
    def get_camera_stats(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific camera"""
        if camera_id in self.sources:
            return self.sources[camera_id].get_stats()
        return None
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all cameras"""
        stats = {
            "cameras": {},
            "production_state": {
                "program_source": self.program_source,
                "preview_source": self.preview_source,
                "recording_sources": self.recording_sources
            },
            "system": {
                "total_cameras": len(self.sources),
                "online_cameras": len([c for c in self.sources.values() if c.metadata.status == CameraStatus.ONLINE]),
                "error_cameras": len([c for c in self.sources.values() if c.metadata.status == CameraStatus.ERROR]),
                "monitoring_enabled": self.monitoring_enabled,
                "auto_switching_enabled": self.auto_switching_enabled
            }
        }
        
        for camera_id, camera in self.sources.items():
            stats["cameras"][camera_id] = camera.get_stats()
        
        return stats
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of camera system status"""
        online = len([c for c in self.sources.values() if c.metadata.status == CameraStatus.ONLINE])
        total = len(self.sources)
        
        return {
            "total_cameras": total,
            "online_cameras": online,
            "offline_cameras": total - online,
            "program_camera": self.program_source,
            "preview_camera": self.preview_source,
            "health_status": "healthy" if online >= total * 0.8 else "degraded" if online > 0 else "critical"
        }
    
    async def shutdown(self):
        """Shutdown camera manager and all sources"""
        logger.info("Shutting down camera manager")
        
        # Stop monitoring
        await self.stop_monitoring()
        
        # Disconnect all cameras
        disconnect_tasks = [
            self.disconnect_camera(camera_id) 
            for camera_id in self.sources.keys()
        ]
        
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Save final state
        self.save_configuration()
        
        logger.info("Camera manager shutdown complete")

# Factory functions for common setups

def create_default_cameras() -> AdvancedCameraManager:
    """Create camera manager with default setup"""
    manager = AdvancedCameraManager()
    return manager

def create_voxel_camera() -> CameraMetadata:
    """Create metadata for voxel engine camera"""
    return CameraMetadata(
        name="PubCast Voxel Engine",
        transport=CameraTransport.VOXEL_ENGINE,
        connection_string="tcp://localhost:9001",
        width=1920,
        height=1080,
        fps=60.0,
        format="rgba",
        scene_name="default"
    )

def create_usb_camera(device_path: str = "/dev/video0", name: str = "USB Camera") -> CameraMetadata:
    """Create metadata for USB webcam"""
    return CameraMetadata(
        name=name,
        transport=CameraTransport.USB_WEBCAM,
        connection_string=device_path,
        width=1920,
        height=1080,
        fps=30.0,
        format="h264"
    )

def create_ip_camera(host: str, username: str = "", password: str = "", port: int = 554, name: str = "IP Camera") -> CameraMetadata:
    """Create metadata for IP camera"""
    return CameraMetadata(
        name=name,
        transport=CameraTransport.IP_CAMERA,
        connection_string=host,
        username=username,
        password=password,
        port=port,
        width=1920,
        height=1080,
        fps=30.0,
        format="h264"
    )

# Example usage
if __name__ == "__main__":
    async def main():
        # Create camera manager
        camera_manager = create_default_cameras()
        
        # Add a voxel engine camera
        voxel_meta = create_voxel_camera()
        camera_manager.add_camera("voxel_engine", voxel_meta)
        
        # Initialize all cameras
        results = await camera_manager.initialize_all_cameras()
        
        print("Camera initialization results:")
        for camera_id, success in results.items():
            print(f"  {camera_id}: {'✓' if success else '✗'}")
        
        # Get system stats
        stats = camera_manager.get_all_stats()
        print(f"\\nSystem status: {stats['system']}")
        
        # Exercise source switching in the standalone module demo
        await asyncio.sleep(2)
        
        if camera_manager.sources:
            camera_id = list(camera_manager.sources.keys())[0]
            print(f"\\nCutting to camera: {camera_id}")
            await camera_manager.cut_to_camera(camera_id)
        
        await asyncio.sleep(3)
        
        # Cleanup
        await camera_manager.shutdown()

    asyncio.run(main())
