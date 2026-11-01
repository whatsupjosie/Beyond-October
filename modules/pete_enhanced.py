#!/usr/bin/env python3
"""
e-PETE ENHANCED - INTERNAL TWIN ENGINE ORCHESTRATOR

This module is infrastructure, not a speaking character. It coordinates and
reports the technical runtime path:
- existing Bridge commands to renderer/Rust/fallback transport
- WebRTC/shared-memory stream status when real modules exist
- system health monitoring and coordination
- emergency/fallback protocols and load balancing
- internal production workflow diagnostics

It must never fake a live Rust/WebRTC/voxel runtime. Missing runtime components
are reported as fallback/missing diagnostics so PubCast can keep booting safely.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import psutil
import time
from pathlib import Path
from typing import Dict, Any, Optional, Set, List, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum


def _ensure_executable_if_possible(path: Path) -> bool:
    """Restore executable bit for packaged renderer binaries on POSIX hosts.

    Zip extraction paths used by some Python tooling can strip executable bits.
    This does not claim the renderer is alive; it only reports whether the file
    exists and is executable after a best-effort permission repair.
    """
    if not path.exists():
        return False
    if os.access(path, os.X_OK):
        return True
    if os.name != "posix":
        return False
    try:
        path.chmod(path.stat().st_mode | 0o111)
    except OSError:
        return os.access(path, os.X_OK)
    return os.access(path, os.X_OK)

# Compatibility repair pass 1 (2026-07-07):
# Prefer existing local modules.  When an upstream subsystem is truly absent,
# use the smallest inactive fallback needed so e-PETE can import and fail
# gracefully instead of crashing PubCast boot.  These fallbacks are NOT
# replacement production systems.
try:
    from pete import (
        SystemHealth, ResourceMetrics, RePeteWorker, Pete as BasePete
    )
    _PETE_BASE_AVAILABLE = True
except ImportError:  # pragma: no cover - compatibility fallback
    _PETE_BASE_AVAILABLE = False

    class SystemHealth(Enum):
        UNKNOWN = "unknown"
        HEALTHY = "healthy"
        DEGRADED = "degraded"
        CRITICAL = "critical"

    @dataclass
    class ResourceMetrics:
        cpu_percent: float = 0.0
        memory_percent: float = 0.0
        gpu_percent: float = 0.0
        timestamp: float = field(default_factory=time.time)

    class RePeteWorker:
        """Inactive compatibility placeholder for absent upstream RePeteWorker."""
        pass

    class BasePete:
        """
        Minimal inactive BasePete compatibility adapter.

        This only preserves import and guarded initialization safety when the
        upstream `pete` module is missing.  It is not a duplicate e-PETE, not a
        user-facing character, and not a replacement for the full upstream base.
        """
        def __init__(self, hub, bridge, motion_system, data_dir, config=None):
            self.hub = hub
            self.bridge = bridge
            self.motion_system = motion_system
            self.data_dir = Path(data_dir)
            self.config = config or {}
            self._monitoring_active = False

        async def start_monitoring(self):
            self._monitoring_active = True

        async def _collect_system_metrics(self):
            try:
                return ResourceMetrics(
                    cpu_percent=float(psutil.cpu_percent(interval=None)),
                    memory_percent=float(psutil.virtual_memory().percent),
                    gpu_percent=0.0,
                )
            except Exception:
                return ResourceMetrics()

        async def _report_status(self, message: str):
            logger.info(message)
            broadcast = getattr(self.hub, "broadcast_system_event", None)
            if callable(broadcast):
                try:
                    await broadcast({"type": "internal_pete_status", "message": message})
                except Exception:
                    logger.debug("Pete fallback status broadcast failed", exc_info=True)

        async def _activate_emergency_protocols(self, metrics):
            logger.warning("e-PETE compatibility fallback emergency marker: %s", metrics)

        async def shutdown(self):
            self._monitoring_active = False

try:
    # Prefer the richer bulletproof bridge when present. main.py already uses it
    # first, and it exposes the real fallback modes (CONNECTED/DEGRADED/EMERGENCY)
    # that e-PETE must report honestly.
    from .bridge_bulletproof import VoxelBridge, BridgeStatus
except ImportError:  # pragma: no cover - compatibility fallback
    try:
        from .bridge import VoxelBridge, BridgeStatus
    except ImportError:  # pragma: no cover - direct execution fallback
        try:
            from modules.bridge_bulletproof import VoxelBridge, BridgeStatus
        except ImportError:
            from modules.bridge import VoxelBridge, BridgeStatus

try:
    from .voxel_webrtc_bridge import VoxelWebRTCBridge
    _WEBRTC_BRIDGE_AVAILABLE = True
except ImportError:  # pragma: no cover - compatibility fallback
    try:
        from modules.voxel_webrtc_bridge import VoxelWebRTCBridge
        _WEBRTC_BRIDGE_AVAILABLE = True
    except ImportError:
        _WEBRTC_BRIDGE_AVAILABLE = False

        class VoxelWebRTCBridge:
            """Inactive compatibility fallback for absent renderer/WebRTC bridge."""
            def __init__(self, *args, **kwargs):
                self.available = False

            async def start_frame_monitoring(self):
                return None

            def connect_shared_memory(self) -> bool:
                return False

            async def connect_renderer_websocket(self) -> bool:
                return False

            def get_status(self) -> Dict[str, Any]:
                return {
                    "available": False,
                    "connected": False,
                    "transport": "missing",
                    "reason": "voxel_webrtc_bridge.py missing",
                    "webrtc_connections": 0,
                    "current_fps": 0.0,
                    "frames_read": 0,
                    "frames_dropped": 0,
                }

try:
    from .pubcast_voxel_integration import PubCastVoxelIntegration
    _PUBCAST_VOXEL_INTEGRATION_AVAILABLE = True
except ImportError:  # pragma: no cover - compatibility fallback
    try:
        from modules.pubcast_voxel_integration import PubCastVoxelIntegration
        _PUBCAST_VOXEL_INTEGRATION_AVAILABLE = True
    except ImportError:
        _PUBCAST_VOXEL_INTEGRATION_AVAILABLE = False

        class PubCastVoxelIntegration:
            """Inactive compatibility fallback for absent voxel integration."""
            def __init__(self, *args, **kwargs):
                self.available = False

            async def _restart_voxel_engine(self):
                logger.warning("Voxel integration restart requested, but pubcast_voxel_integration.py is missing")
                return False

            async def shutdown(self):
                return None

if TYPE_CHECKING:
    from ..core.hub import Hub
    from ..motion.avatar_system import MotionSystem

logger = logging.getLogger("pubcast.pete_enhanced")

@dataclass
class TwinEngineMetrics:
    """Enhanced metrics for the complete twin engine system"""
    # Base system metrics (from your Pete)
    base_metrics: ResourceMetrics = field(default_factory=ResourceMetrics)
    
    # Bridge metrics (commands TO Rust engine)
    bridge_status: BridgeStatus = BridgeStatus.DISCONNECTED
    commands_queued: int = 0
    commands_sent: int = 0
    commands_failed: int = 0
    bridge_latency_ms: float = 0.0
    
    # WebRTC metrics (streaming FROM Rust engine)  
    webrtc_connections: int = 0
    streaming_fps: float = 0.0
    frames_streamed: int = 0
    frames_dropped: int = 0
    webrtc_latency_ms: float = 0.0
    
    # Rust engine health
    rust_engine_alive: bool = False
    rust_engine_fps: float = 0.0
    rust_engine_memory_mb: float = 0.0
    
    # Performance tracking
    total_pipeline_latency: float = 0.0  # Motion → Rust → Browser
    timestamp: float = field(default_factory=time.time)

class TwinEngineHealth(Enum):
    """Health status for the complete twin engine system"""
    PERFECT = "perfect"           # All systems optimal, <16ms total latency
    EXCELLENT = "excellent"       # All systems healthy, <33ms total latency  
    GOOD = "good"                # Minor issues, <50ms total latency
    DEGRADED = "degraded"        # Performance issues, <100ms total latency
    CRITICAL = "critical"        # Major issues, >100ms latency
    EMERGENCY = "emergency"      # System failure imminent

class PeteEnhanced(BasePete):
    """
    Internal e-PETE twin-engine orchestrator.

    This owns technical runtime health and bridge diagnostics only. It is not a
    character slot, not guest-facing, and not a replacement for Jeremy, Bubble
    Stack, Session Runtime, Room Conductor, cameras, recording, or governance.
    """
    
    def __init__(
        self,
        hub: 'Hub',
        bridge: VoxelBridge,
        motion_system: Dict[str, Any],
        data_dir: Path,
        config: Optional[Dict[str, Any]] = None,
        *,
        owns_bridge: bool = True,
    ):
        # Initialize base Pete
        super().__init__(hub, bridge, motion_system, data_dir, config)
        # Standalone PeteEnhanced historically owned its bridge. Full PubCast now
        # shares the same bridge with TwinEngineService, so main.py explicitly
        # sets this False and lets the service close the transport exactly once.
        self._owns_bridge = bool(owns_bridge)
        
        # Enhanced twin engine components
        self.webrtc_bridge: Optional[VoxelWebRTCBridge] = None
        self.voxel_integration: Optional[PubCastVoxelIntegration] = None
        
        # Twin engine state. Start honest and pessimistic until measured.
        # Earlier builds defaulted to PERFECT before runtime checks completed, which
        # could make a fallback-only boot look healthier than it really was.
        self._twin_engine_health = TwinEngineHealth.DEGRADED
        self._twin_metrics = TwinEngineMetrics()
        self._last_twin_engine_check = 0.0
        
        # Performance optimization
        self._adaptive_quality_enabled = True
        self._current_quality_preset = "high"
        self._load_balancing_active = False
        
        # Emergency / fallback protocols
        self._emergency_streaming_fallback = False
        self._rust_engine_restart_count = 0
        self._runtime_mode = "uninitialized"
        self._runtime_activation = "not_started"
        self._runtime_notes: List[str] = []
        self._runtime_components = self._detect_runtime_components()
        
        logger.info("e-PETE internal twin-engine orchestrator initialized")

    def _detect_runtime_components(self) -> Dict[str, Any]:
        """Detect real runtime pieces without starting or pretending anything.

        This is intentionally informational.  Existence of a file is not treated
        as proof that the Rust/WebRTC/voxel runtime is alive.
        """
        project_root = Path.cwd()
        renderer_binary = project_root / "bin" / "ws_renderer"
        renderer_executable = _ensure_executable_if_possible(renderer_binary)
        renderer_source = project_root / "rust_crate" / "src" / "renderer.rs"
        renderer_ws_source = project_root / "rust_crate" / "src" / "ws_renderer.rs"
        cargo_toml = project_root / "rust_crate" / "Cargo.toml"
        posix_ipc_available = importlib.util.find_spec("posix_ipc") is not None
        return {
            "base_pete_module_available": _PETE_BASE_AVAILABLE,
            "webrtc_bridge_module_available": _WEBRTC_BRIDGE_AVAILABLE,
            "renderer_websocket_adapter_available": _WEBRTC_BRIDGE_AVAILABLE,
            "pubcast_voxel_integration_module_available": _PUBCAST_VOXEL_INTEGRATION_AVAILABLE,
            "posix_ipc_available": posix_ipc_available,
            "rust_crate_manifest_exists": cargo_toml.exists(),
            "rust_renderer_source_exists": renderer_source.exists(),
            "rust_ws_renderer_source_exists": renderer_ws_source.exists(),
            "rust_renderer_binary_exists": renderer_binary.exists(),
            "rust_renderer_binary_executable": renderer_executable,
            "rust_renderer_binary_path": str(renderer_binary) if renderer_binary.exists() else None,
            "rust_renderer_websocket_port": int(os.getenv("PUBCAST_WS_PORT", "8765")),
            "bridge_class": type(self.bridge).__name__ if self.bridge is not None else None,
            "bridge_module": type(self.bridge).__module__ if self.bridge is not None else None,
            "shared_memory_path_available": posix_ipc_available,
            "renderer_websocket_path_available": _WEBRTC_BRIDGE_AVAILABLE and renderer_binary.exists(),
            "physics_consequence_hooks_available": False,
        }

    def get_runtime_component_status(self) -> Dict[str, Any]:
        """Return honest e-PETE runtime component availability for diagnostics."""
        status_value = "missing"
        if self.bridge is not None:
            raw_status = (
                self.bridge.status() if hasattr(self.bridge, "status") and callable(self.bridge.status) else
                self.bridge.get_status() if hasattr(self.bridge, "get_status") else
                getattr(self.bridge, "_status", "unknown")
            )
            status_value = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
        components = dict(self._runtime_components)
        components.update({
            "bridge_status": status_value,
            "runtime_mode": self._runtime_mode,
            "runtime_activation": self._runtime_activation,
            "runtime_notes": list(self._runtime_notes),
        })
        return components

    def _set_fallback(self, mode: str, note: str) -> None:
        """Record fallback state without disabling PubCast boot."""
        self._runtime_mode = mode
        self._runtime_activation = "fallback_hardened"
        self._emergency_streaming_fallback = True
        if note and note not in self._runtime_notes:
            self._runtime_notes.append(note)

    def _set_voxel_renderer_connected(self, note: str) -> None:
        """Record honest partial activation of the real Rust WebSocket renderer."""
        self._runtime_mode = "renderer_websocket_runtime"
        self._runtime_activation = "voxel_renderer_connected"
        self._emergency_streaming_fallback = True
        if note and note not in self._runtime_notes:
            self._runtime_notes.append(note)

    async def initialize_twin_engine_system(self) -> bool:
        """
        Initialize the complete twin engine system.
        
        This sets up both your Bridge (Python → Rust) and 
        my WebRTC streaming (Rust → Browser).
        """
        try:
            logger.info("e-PETE: Initializing internal twin-engine diagnostics...")
            self._runtime_components = self._detect_runtime_components()
            
            # Step 1: Initialize the existing Bridge connection/fallback path.
            logger.info("e-PETE: Connecting to renderer bridge...")
            bridge_connected = await self._initialize_bridge_connection()
            
            if not bridge_connected:
                logger.warning("e-PETE: Bridge connection failed; e-PETE remains inactive/fallback.")
                self._set_fallback("inactive_no_bridge", "Bridge could not connect to shared memory, TCP, or file fallback.")
                self._twin_engine_health = TwinEngineHealth.EMERGENCY
                return False
            
            bridge_status_value = self.get_runtime_component_status().get("bridge_status")
            if bridge_status_value == "connected":
                self._runtime_mode = "bridge_connected"
            elif bridge_status_value == "degraded":
                self._set_fallback("tcp_bridge_degraded", "Bridge connected through TCP fallback, not SHM/Rust primary path.")
            elif bridge_status_value == "emergency":
                self._set_fallback("file_bridge_emergency", "Bridge connected through file-system emergency fallback; no proof of live Rust renderer.")
            else:
                self._set_fallback("bridge_not_primary", f"Bridge status is {bridge_status_value}; primary SHM/Rust path is not live.")
            
            # Step 2: Initialize the renderer streaming/transport adapter only if present.
            if not _WEBRTC_BRIDGE_AVAILABLE:
                streaming_ready = False
                self._set_fallback("no_renderer_bridge", "voxel_webrtc_bridge.py is missing; renderer stream was not started.")
                logger.warning("e-PETE: renderer bridge module missing; streaming remains unavailable.")
            else:
                logger.info("e-PETE: Setting up Rust renderer WebSocket adapter...")
                streaming_ready = await self._initialize_webrtc_streaming()
                if not streaming_ready:
                    self._set_fallback("renderer_websocket_not_connected", "Rust renderer WebSocket did not connect; WebRTC/shared-memory remains unavailable.")
                    logger.warning("e-PETE: renderer WebSocket unavailable; continuing with honest fallback status.")
            
            # Step 3: Start monitoring so diagnostics remain current.
            logger.info("e-PETE: Starting internal runtime health monitoring...")
            await self._start_twin_engine_monitoring()
            
            # Step 4: Perform system integration test.
            logger.info("e-PETE: Running bridge/streaming integration check...")
            integration_success = await self._test_complete_pipeline()
            
            renderer_status = self.webrtc_bridge.get_status() if self.webrtc_bridge else {}
            renderer_connected = bool(renderer_status.get("connected")) and renderer_status.get("transport") == "renderer_websocket"

            if integration_success and streaming_ready and self.get_runtime_component_status().get("bridge_status") == "connected":
                self._runtime_activation = "runtime_activated"
                self._runtime_mode = "primary_runtime"
                await self._report_status(
                    "e-PETE: primary runtime activated: bridge + WebRTC streaming are live."
                )
                return True
            elif integration_success and renderer_connected:
                self._set_voxel_renderer_connected(
                    "Real Rust ws_renderer process is connected over WebSocket; full WebRTC/shared-memory command path is still not active."
                )
                await self._report_status(
                    "e-PETE: voxel renderer connected over real Rust WebSocket; full browser WebRTC/SHM remains unavailable."
                )
                return True
            else:
                self._set_fallback("fallback_hardened", "Primary e-PETE runtime not fully active; PubCast continues with internal fallback diagnostics.")
                await self._report_status(
                    "e-PETE: fallback diagnostics active; no fake Rust/WebRTC/physics success reported."
                )
                return True  # Keep diagnostics route available in fallback mode.
                
        except Exception as e:
            logger.error(f"e-PETE: Twin engine initialization failed: {e}")
            return False

    async def _initialize_bridge_connection(self) -> bool:
        """Initialize your existing Bridge connection to Rust engine"""
        try:
            # Use your existing Bridge.connect() method
            success = self.bridge.connect()
            
            if success:
                # Test basic bridge functionality
                test_command_sent = self.bridge.send_command(
                    "HEARTBEAT", 
                    {"test": True, "from": "pete_enhanced"}
                )
                
                if test_command_sent:
                    bridge_status = self.get_runtime_component_status().get("bridge_status", "unknown")
                    if bridge_status == "connected":
                        logger.info("e-PETE: primary bridge connection established and command test passed")
                    else:
                        logger.warning(
                            "e-PETE: bridge fallback path accepted command test; primary bridge not active (status=%s)",
                            bridge_status,
                        )
                    return True
                else:
                    logger.warning("e-PETE: Bridge connected but test command failed")
                    return False
            else:
                logger.error("e-PETE: Bridge connection failed")
                return False
                
        except Exception as e:
            logger.error(f"e-PETE: Bridge initialization error: {e}")
            return False

    async def _initialize_webrtc_streaming(self) -> bool:
        """Initialize WebRTC streaming bridge only when the real module exists."""
        if not _WEBRTC_BRIDGE_AVAILABLE:
            self.webrtc_bridge = None
            return False
        try:
            self.webrtc_bridge = VoxelWebRTCBridge()

            if _PUBCAST_VOXEL_INTEGRATION_AVAILABLE:
                self.voxel_integration = PubCastVoxelIntegration(
                    camera_manager=None,
                    hub=self.hub,
                    bridge=self.bridge,
                    data_dir=self.data_dir,
                )
            else:
                self.voxel_integration = None
                self._set_fallback("no_pubcast_voxel_integration", "pubcast_voxel_integration.py is missing; restart hooks are unavailable.")

            renderer_connect = getattr(self.webrtc_bridge, "connect_renderer_websocket", None)
            if callable(renderer_connect):
                renderer_ready = await renderer_connect()
                if renderer_ready:
                    monitor = self.webrtc_bridge.start_frame_monitoring()
                    if asyncio.iscoroutine(monitor):
                        await monitor
                    logger.info("e-PETE: Rust renderer WebSocket connected")
                    return True

            # Legacy/primary path remains shared memory when a real implementation appears.
            for attempt in range(3):
                if self.webrtc_bridge.connect_shared_memory():
                    logger.info("e-PETE: WebRTC/shared-memory bridge connected")
                    return True
                await asyncio.sleep(0.2)

            logger.warning("e-PETE: renderer/WebRTC/shared-memory bridge did not connect")
            return False
            
        except Exception as e:
            logger.error(f"e-PETE: WebRTC streaming initialization error: {e}")
            return False

    async def _start_twin_engine_monitoring(self):
        """Start enhanced monitoring for the twin engine system"""
        # Start base Pete monitoring
        await super().start_monitoring()
        
        # Add twin engine specific monitoring
        asyncio.create_task(self._twin_engine_monitor_loop())
        
        logger.info("e-PETE: Twin engine monitoring started")

    async def _twin_engine_monitor_loop(self):
        """Enhanced monitoring loop for twin engine health"""
        while self._monitoring_active:
            try:
                # Collect twin engine metrics
                self._twin_metrics = await self._collect_twin_engine_metrics()
                
                # Assess twin engine health
                old_health = self._twin_engine_health
                self._twin_engine_health = self._assess_twin_engine_health(self._twin_metrics)
                
                # Handle health changes
                if self._twin_engine_health != old_health:
                    await self._handle_twin_engine_health_change(old_health, self._twin_engine_health)
                
                # Optimize performance based on current load
                if self._adaptive_quality_enabled:
                    await self._optimize_twin_engine_performance()
                
                # Emergency protocols
                if self._twin_engine_health in [TwinEngineHealth.CRITICAL, TwinEngineHealth.EMERGENCY]:
                    await self._handle_twin_engine_emergency()
                
                self._last_twin_engine_check = time.time()
                await asyncio.sleep(2.0)  # Check every 2 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"e-PETE: Twin engine monitoring error: {e}")
                await asyncio.sleep(5.0)

    async def _collect_twin_engine_metrics(self) -> TwinEngineMetrics:
        """Collect comprehensive metrics from both engines"""
        try:
            # Get base system metrics
            base_metrics = await self._collect_system_metrics()
            
            # Get Bridge metrics (your existing bridge).  Different bridge
            # implementations in this build expose slightly different APIs, so
            # normalize without forcing a duplicate bridge.
            bridge_status = BridgeStatus.DISCONNECTED
            bridge_metrics = None
            if self.bridge:
                raw_status = (
                    self.bridge.get_status() if hasattr(self.bridge, "get_status") else
                    self.bridge.status() if hasattr(self.bridge, "status") and callable(self.bridge.status) else
                    getattr(self.bridge, "status", BridgeStatus.DISCONNECTED)
                )
                if isinstance(raw_status, dict):
                    raw_status = raw_status.get("status", BridgeStatus.DISCONNECTED)
                if isinstance(raw_status, BridgeStatus):
                    bridge_status = raw_status
                else:
                    raw_status_value = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
                    try:
                        bridge_status = BridgeStatus(raw_status_value)
                    except Exception:
                        bridge_status = BridgeStatus.DISCONNECTED

                bridge_metrics = self.bridge.get_metrics() if hasattr(self.bridge, "get_metrics") else None
            
            # Get WebRTC metrics (my streaming bridge)
            webrtc_status = self.webrtc_bridge.get_status() if self.webrtc_bridge else {}
            
            # Calculate total pipeline latency
            if isinstance(bridge_metrics, dict):
                bridge_latency = float(bridge_metrics.get("avg_latency_ms", bridge_metrics.get("latency_ms", 0.0)) or 0.0)
                commands_sent = int(bridge_metrics.get("commands_sent", 0) or 0)
                commands_failed = int(bridge_metrics.get("commands_failed", 0) or 0)
            else:
                bridge_latency = float(getattr(bridge_metrics, "avg_latency_ms", 0.0) or 0.0)
                commands_sent = int(getattr(bridge_metrics, "commands_sent", 0) or 0)
                commands_failed = int(getattr(bridge_metrics, "commands_failed", 0) or 0)
            webrtc_latency = 16.67  # ~1 frame at 60fps, estimated
            total_latency = bridge_latency + webrtc_latency
            
            return TwinEngineMetrics(
                base_metrics=base_metrics,
                
                # Bridge metrics
                bridge_status=bridge_status,
                commands_queued=len(getattr(self.bridge, "_command_queue", [])) if self.bridge else 0,
                commands_sent=commands_sent,
                commands_failed=commands_failed,
                bridge_latency_ms=bridge_latency,
                
                # WebRTC metrics  
                webrtc_connections=webrtc_status.get("webrtc_connections", 0),
                streaming_fps=webrtc_status.get("current_fps", 0.0),
                frames_streamed=webrtc_status.get("frames_read", 0),
                frames_dropped=webrtc_status.get("frames_dropped", 0),
                
                # Rust engine health: SHM bridge is primary, but the current
                # handoff can also prove the real Rust ws_renderer over WebSocket.
                rust_engine_alive=(bridge_status == BridgeStatus.CONNECTED) or bool(webrtc_status.get("connected")),
                rust_engine_fps=webrtc_status.get("current_fps", 0.0),
                
                # Performance
                total_pipeline_latency=total_latency
            )
            
        except Exception as e:
            logger.error(f"e-PETE: Metrics collection error: {e}")
            return TwinEngineMetrics()

    def _assess_twin_engine_health(self, metrics: TwinEngineMetrics) -> TwinEngineHealth:
        """Assess health of the complete twin engine system"""
        
        # Perfect: Everything optimal
        if (metrics.total_pipeline_latency < 16 and 
            metrics.streaming_fps > 55 and
            metrics.bridge_status == BridgeStatus.CONNECTED and
            metrics.base_metrics.cpu_percent < 50):
            return TwinEngineHealth.PERFECT
        
        # Excellent: All systems healthy
        elif (metrics.total_pipeline_latency < 33 and 
              metrics.streaming_fps > 45 and
              metrics.bridge_status == BridgeStatus.CONNECTED and
              metrics.base_metrics.cpu_percent < 70):
            return TwinEngineHealth.EXCELLENT
        
        # Good: Minor issues
        elif (metrics.total_pipeline_latency < 50 and 
              metrics.streaming_fps > 30 and
              metrics.bridge_status != BridgeStatus.ERROR):
            return TwinEngineHealth.GOOD
        
        # Degraded: Performance issues  
        elif (metrics.total_pipeline_latency < 100 and 
              metrics.streaming_fps > 15):
            return TwinEngineHealth.DEGRADED
        
        # Critical: Major issues
        elif metrics.rust_engine_alive and metrics.streaming_fps > 0:
            return TwinEngineHealth.CRITICAL
        
        # Emergency: System failure
        else:
            return TwinEngineHealth.EMERGENCY

    async def _handle_twin_engine_health_change(self, old_health: TwinEngineHealth, new_health: TwinEngineHealth):
        """React to twin engine health changes"""
        
        if new_health == TwinEngineHealth.PERFECT:
            await self._report_status("e-PETE: primary runtime health perfect. "
                                    f"<16ms latency, {self._twin_metrics.streaming_fps:.1f}fps streaming")
        
        elif new_health == TwinEngineHealth.EXCELLENT:
            await self._report_status("e-PETE: primary runtime health excellent. "
                                    f"{self._twin_metrics.total_pipeline_latency:.1f}ms pipeline")
        
        elif new_health == TwinEngineHealth.GOOD:
            await self._report_status("e-PETE: Twin engines nominal. "
                                    f"Latency: {self._twin_metrics.total_pipeline_latency:.1f}ms")
        
        elif new_health == TwinEngineHealth.DEGRADED:
            await self._report_status("e-PETE: Twin engine performance degraded. "
                                    "Activating optimization protocols.")
            await self._optimize_twin_engine_performance()
        
        elif new_health == TwinEngineHealth.CRITICAL:
            await self._report_status("e-PETE: primary runtime incomplete; renderer/fallback diagnostics remain critical.")
            
        elif new_health == TwinEngineHealth.EMERGENCY:
            await self._report_status("e-PETE: runtime emergency/fallback condition detected; recovery limited to real available components.")

    async def _optimize_twin_engine_performance(self):
        """Optimize twin engine performance based on current load"""
        try:
            metrics = self._twin_metrics
            
            # Adjust quality based on system load
            if metrics.base_metrics.cpu_percent > 80:
                await self._reduce_rendering_quality()
            elif metrics.base_metrics.cpu_percent < 40 and self._current_quality_preset == "medium":
                await self._increase_rendering_quality()
            
            # Optimize streaming based on connection count
            if metrics.webrtc_connections > 10:
                await self._enable_streaming_optimization()
            
            # Load balance between engines
            if metrics.bridge_latency_ms > 50:
                await self._enable_load_balancing()
                
        except Exception as e:
            logger.error(f"e-PETE: Performance optimization error: {e}")

    async def _reduce_rendering_quality(self):
        """Reduce Rust engine rendering quality to improve performance"""
        if self._current_quality_preset != "medium":
            logger.info("e-PETE: Reducing rendering quality to stabilize performance")
            
            # Send quality reduction command to Rust engine via your Bridge
            success = self.bridge.send_command("SET_QUALITY", {"quality": "medium", "fps": 30})
            
            if success:
                self._current_quality_preset = "medium"
                await self._report_status("e-PETE: Rendering quality reduced to maintain smooth performance")

    async def _increase_rendering_quality(self):
        """Increase rendering quality when system can handle it"""
        if self._current_quality_preset != "high":
            logger.info("e-PETE: System stable - increasing rendering quality")
            
            success = self.bridge.send_command("SET_QUALITY", {"quality": "high", "fps": 60})
            
            if success:
                self._current_quality_preset = "high"
                await self._report_status("e-PETE: rendering quality increased to high.")

    async def _enable_streaming_optimization(self):
        """Enable streaming optimizations for multiple viewers"""
        if not self._load_balancing_active:
            logger.info("e-PETE: Multiple viewers detected - enabling streaming optimization")
            self._load_balancing_active = True
            
            # Could implement bitrate adaptation, quality scaling, etc.
            await self._report_status("e-PETE: Streaming optimization active for multiple viewers")

    async def _handle_twin_engine_emergency(self):
        """Handle twin engine emergency situations"""
        try:
            # Emergency protocols
            if self._twin_engine_health == TwinEngineHealth.EMERGENCY:
                logger.error("e-PETE: Twin engine system failure - attempting recovery")
                
                # Try to restart the Rust engine
                if self.voxel_integration:
                    await self.voxel_integration._restart_voxel_engine()
                    self._rust_engine_restart_count += 1
                
                # Enable emergency fallback streaming
                self._emergency_streaming_fallback = True
                
                # Report to base Pete for system-level emergency protocols
                await self._activate_emergency_protocols(self._twin_metrics.base_metrics)
                
        except Exception as e:
            logger.error(f"e-PETE: Emergency handling error: {e}")

    async def _test_complete_pipeline(self) -> bool:
        """Test the current available e-PETE transport path honestly."""
        try:
            logger.info("e-PETE: Testing current available renderer pipeline without claiming full WebRTC/SHM...")
            
            # Test 1: Send test command via Bridge
            bridge_test = self.bridge.send_command("LOAD_SCENE", {"scene": "test_scene"})
            if not bridge_test:
                logger.warning("e-PETE: Bridge test failed")
                return False
            
            # Test 2: Check renderer streaming/transport. In this build, the real
            # available path is Rust ws_renderer over WebSocket, not browser WebRTC.
            await asyncio.sleep(0.5)

            webrtc_status = self.webrtc_bridge.get_status() if self.webrtc_bridge else {}
            if webrtc_status.get("current_fps", 0) > 0 or webrtc_status.get("connected"):
                logger.info("e-PETE: renderer transport test passed")
            else:
                logger.warning("e-PETE: renderer transport test failed")
                return False
            
            # Test 3: Measure total latency
            total_latency = self._twin_metrics.total_pipeline_latency
            if total_latency < 100:  # Less than 100ms is acceptable
                logger.info(f"e-PETE: renderer-path latency check passed: {total_latency:.1f}ms")
                return True
            else:
                logger.warning(f"e-PETE: Pipeline latency high: {total_latency:.1f}ms")
                return False
                
        except Exception as e:
            logger.error(f"e-PETE: Pipeline test error: {e}")
            return False

    def get_twin_engine_status(self) -> Dict[str, Any]:
        """Get honest internal e-PETE status.

        `diagnostics_available` means PubCast can inspect the bridge/fallback state.
        `system_operational` means the primary Rust/WebRTC path is live.
        """
        component_status = self.get_runtime_component_status()
        bridge_status = self._twin_metrics.bridge_status.value if hasattr(self._twin_metrics.bridge_status, "value") else str(self._twin_metrics.bridge_status)
        primary_operational = (
            self._runtime_activation == "runtime_activated"
            and bridge_status == "connected"
            and self._twin_metrics.streaming_fps > 0
        )
        voxel_renderer_operational = (
            self._runtime_activation in {"runtime_activated", "voxel_renderer_connected"}
            and self._twin_metrics.streaming_fps > 0
        )
        return {
            "twin_engine_health": self._twin_engine_health.value,
            "system_operational": primary_operational,
            "voxel_renderer_operational": voxel_renderer_operational,
            "diagnostics_available": True,
            "runtime_activation": self._runtime_activation,
            "runtime_mode": self._runtime_mode,
            "guest_visible": False,
            "components": component_status,
            
            # Bridge (Python → renderer/Rust/fallback)
            "bridge": {
                "status": bridge_status,
                "commands_queued": self._twin_metrics.commands_queued,
                "commands_sent": self._twin_metrics.commands_sent,
                "commands_failed": self._twin_metrics.commands_failed,
                "latency_ms": self._twin_metrics.bridge_latency_ms
            },
            
            # WebRTC Streaming (renderer → Browser), if real module is present
            "streaming": {
                "available": _WEBRTC_BRIDGE_AVAILABLE,
                "transport": (self.webrtc_bridge.get_status().get("transport") if self.webrtc_bridge else "missing"),
                "renderer_connected": (self.webrtc_bridge.get_status().get("connected") if self.webrtc_bridge else False),
                "webrtc_signaling_available": (self.webrtc_bridge.get_status().get("webrtc_signaling_available") if self.webrtc_bridge else False),
                "shared_memory_available": (self.webrtc_bridge.get_status().get("shared_memory_available") if self.webrtc_bridge else False),
                "webrtc_connections": self._twin_metrics.webrtc_connections,
                "fps": self._twin_metrics.streaming_fps,
                "frames_streamed": self._twin_metrics.frames_streamed,
                "frames_dropped": self._twin_metrics.frames_dropped
            },
            
            # Rust Engine Health
            "rust_engine": {
                "alive": voxel_renderer_operational,
                "primary_pipeline_alive": primary_operational,
                "renderer_binary_exists": component_status.get("rust_renderer_binary_exists"),
                "renderer_binary_executable": component_status.get("rust_renderer_binary_executable"),
                "fps": self._twin_metrics.rust_engine_fps,
                "restart_count": self._rust_engine_restart_count
            },
            
            # Performance
            "performance": {
                "total_pipeline_latency_ms": self._twin_metrics.total_pipeline_latency,
                "current_quality": self._current_quality_preset,
                "load_balancing_active": self._load_balancing_active,
                "emergency_fallback": self._emergency_streaming_fallback
            }
        }

    async def handle_production_control(self, command: str, params: Dict[str, Any]):
        """Enhanced production control that coordinates both engines"""
        try:
            # Handle camera controls
            if command == "switch_camera":
                # Send to Rust engine via your Bridge
                bridge_success = self.bridge.send_command("SWITCH_PROGRAM", {
                    "camera_id": params.get("camera_id", 1),
                    "transition": params.get("transition", "CUT")
                })
                
                if bridge_success:
                    await self._report_status(f"e-PETE: Switched to camera {params.get('camera_id')}")
                
            # Handle scene changes
            elif command == "load_scene":
                bridge_success = self.bridge.send_command("LOAD_SCENE", {
                    "scene_id": params.get("scene_id"),
                    "transition_time": params.get("transition_time", 1.0)
                })
                
                if bridge_success:
                    await self._report_status(f"e-PETE: Loading scene '{params.get('scene_id')}'")
            
            # Handle recording controls
            elif command.startswith("record_"):
                action = command.replace("record_", "").upper()
                if hasattr(self.bridge, "send_recording_control"):
                    bridge_success = self.bridge.send_recording_control(action, params)
                else:
                    bridge_success = self.bridge.send_command("RECORDING_CONTROL", {"action": action, **params})
                
                if bridge_success:
                    await self._report_status(f"e-PETE: Recording {action.lower()}")
            
            # Handle quality adjustments
            elif command == "set_quality":
                quality = params.get("quality", "high")
                await self._set_rendering_quality(quality)
                
        except Exception as e:
            logger.error(f"e-PETE: Production control error: {e}")

    async def _set_rendering_quality(self, quality: str):
        """Set rendering quality on the Rust engine"""
        quality_settings = {
            "low": {"quality": "low", "fps": 30, "resolution": "1280x720"},
            "medium": {"quality": "medium", "fps": 45, "resolution": "1920x1080"},
            "high": {"quality": "high", "fps": 60, "resolution": "1920x1080"}
        }
        
        settings = quality_settings.get(quality, quality_settings["high"])
        success = self.bridge.send_command("SET_QUALITY", settings)
        
        if success:
            self._current_quality_preset = quality
            await self._report_status(f"e-PETE: Rendering quality set to {quality}")

    async def shutdown_twin_engine_system(self):
        """Graceful shutdown of the complete twin engine system"""
        logger.info("e-PETE: Shutting down twin engine system...")
        
        try:
            # Shutdown renderer/WebRTC adapter first so any child ws_renderer
            # process is not left orphaned after TestClient/app shutdown.
            if self.webrtc_bridge and hasattr(self.webrtc_bridge, "shutdown"):
                shutdown_stream = self.webrtc_bridge.shutdown()
                if asyncio.iscoroutine(shutdown_stream):
                    await shutdown_stream

            if self.voxel_integration:
                await self.voxel_integration.shutdown()
            
            # Standalone PeteEnhanced owns its bridge by default. In the full
            # PubCast host TwinEngineService owns the shared transport lifecycle,
            # so Pete only shuts down its renderer/monitoring side.
            if self.bridge and self._owns_bridge:
                aclose = getattr(self.bridge, "aclose", None)
                shutdown = getattr(self.bridge, "shutdown", None)
                close = getattr(self.bridge, "close", None)
                disconnect = getattr(self.bridge, "disconnect", None)
                if callable(aclose):
                    result = aclose()
                    if asyncio.iscoroutine(result):
                        await result
                elif callable(shutdown):
                    result = shutdown()
                    if asyncio.iscoroutine(result):
                        await result
                elif callable(close):
                    result = close()
                    if asyncio.iscoroutine(result):
                        await result
                elif callable(disconnect):
                    result = disconnect()
                    if asyncio.iscoroutine(result):
                        await result
            
            # Shutdown base Pete
            await super().shutdown()
            
            await self._report_status("e-PETE: twin engine diagnostics shutdown complete.")
            
        except Exception as e:
            logger.error(f"e-PETE: Twin engine shutdown error: {e}")

# Usage example for integration
async def create_enhanced_pete_system(hub, bridge, motion_system, data_dir):
    """Create and initialize the complete e-PETE Enhanced system"""
    
    pete_enhanced = PeteEnhanced(
        hub=hub,
        bridge=bridge,
        motion_system=motion_system,
        data_dir=data_dir
    )
    
    # Initialize the complete twin engine system
    success = await pete_enhanced.initialize_twin_engine_system()
    
    if success:
        logger.info("🎭 e-PETE Enhanced: Internal e-PETE diagnostics operational.")
        return pete_enhanced
    else:
        logger.error("🎭 e-PETE Enhanced: e-PETE diagnostics initialization failed")
        return None

if __name__ == "__main__":
    # Standalone testing
    async def test_enhanced_pete():
        # This would normally come from your main system
        from unittest.mock import Mock
        
        hub = Mock()
        bridge = Mock()
        motion_system = {}
        data_dir = Path("./data")
        
        pete = await create_enhanced_pete_system(hub, bridge, motion_system, data_dir)
        
        if pete:
            print("e-PETE Enhanced test successful")
            
            # Test twin engine status
            status = pete.get_twin_engine_status()
            print(f"Twin Engine Status: {status['twin_engine_health']}")
            
            # Keep running for testing
            try:
                while True:
                    await asyncio.sleep(1.0)
            except KeyboardInterrupt:
                await pete.shutdown_twin_engine_system()
        else:
            print("❌ e-PETE Enhanced test failed")
    
    asyncio.run(test_enhanced_pete())

