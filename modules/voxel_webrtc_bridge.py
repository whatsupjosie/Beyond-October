#!/usr/bin/env python3
# PubCast AI — voxel_webrtc_bridge.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""
Internal renderer WebSocket adapter for e-PETE.

Historical e-PETE code expects a module named ``voxel_webrtc_bridge``. The real
artifact currently present in the v5.6 handoff is not a browser WebRTC bridge;
it is a Rust ``ws_renderer`` process that accepts avatar motion frames over a
WebSocket on port 8765. This adapter connects e-PETE to that real renderer
without pretending that full browser WebRTC or shared memory is active.

Responsibilities:
- locate and optionally start ``bin/ws_renderer``
- connect to its WebSocket endpoint
- send valid PubCast motion-frame probes
- expose honest status for internal diagnostics
- report WebRTC/signaling as unavailable until a real WebRTC bridge arrives
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("pubcast.voxel_webrtc_bridge")


def _ensure_executable_if_possible(path: Path) -> bool:
    """Best-effort POSIX permission repair for packaged renderer binary."""
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


class VoxelWebRTCBridge:
    """Compatibility adapter around the real Rust ``ws_renderer`` WebSocket.

    Despite the legacy class name, this is currently a renderer WebSocket bridge,
    not full browser WebRTC. Status fields make that distinction explicit.
    """

    def __init__(
        self,
        renderer_binary: Optional[Path] = None,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        auto_start: bool = True,
        probe_avatar_id: str = "__epete_probe__",
        **_: Any,
    ) -> None:
        self.host = host
        self.port = int(port or os.getenv("PUBCAST_WS_PORT", "8765"))
        self.auto_start = auto_start
        self.probe_avatar_id = probe_avatar_id
        self.renderer_binary = Path(renderer_binary) if renderer_binary else self._find_renderer_binary()
        self.available = self.renderer_binary.exists() if self.renderer_binary else False

        self._process: Optional[subprocess.Popen] = None
        self._owns_process = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._last_probe_at = 0.0
        self._last_error: Optional[str] = None
        self._connected = False
        self._frames_read = 0
        self._frames_dropped = 0
        self._last_latency_us = 0
        self._current_fps = 0.0
        self._start_time = time.time()
        self._transport = "renderer_websocket"

    def _find_renderer_binary(self) -> Path:
        cwd = Path.cwd()
        candidates = [
            cwd / "bin" / "ws_renderer",
            Path(__file__).resolve().parents[1] / "bin" / "ws_renderer",
            Path("/mnt/data/bin/ws_renderer"),
        ]
        for candidate in candidates:
            if candidate.exists():
                _ensure_executable_if_possible(candidate)
                return candidate
        return candidates[0]

    def _port_open(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=0.25):
                return True
        except OSError:
            return False

    async def _wait_for_port(self, timeout_s: float = 3.0) -> bool:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self._port_open():
                return True
            await asyncio.sleep(0.05)
        return self._port_open()

    def _build_probe_payload(self) -> Dict[str, Any]:
        # The Rust ws_renderer currently accepts BridgeMotionPayload:
        # {avatar_id, motion_data, timestamp}. motion_data is a map of bone name
        # to BridgeBoneData: {position, rotation, scale, confidence, parent_idx}.
        return {
            "avatar_id": self.probe_avatar_id,
            "motion_data": {
                "Pelvis": {
                    "position": [0.0, 0.0, 0.0],
                    "rotation": [0.0, 0.0, 0.0, 1.0],
                    "scale": [1.0, 1.0, 1.0],
                    "confidence": 1.0,
                    "parent_idx": None,
                }
            },
            "timestamp": time.time(),
        }

    async def _send_probe(self) -> bool:
        if not self.available:
            self._last_error = f"renderer binary missing: {self.renderer_binary}"
            return False
        try:
            import websockets
        except ImportError as exc:
            self._last_error = f"websockets dependency missing: {exc}"
            return False

        uri = f"ws://{self.host}:{self.port}"
        try:
            async with websockets.connect(uri, open_timeout=1.0, close_timeout=0.5) as ws:
                await ws.send(json.dumps(self._build_probe_payload()))
                response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            data = json.loads(response) if isinstance(response, str) else {}
            if data.get("ok") is True:
                self._frames_read += 1
                self._last_probe_at = time.time()
                self._last_latency_us = int(data.get("latency_us", 0) or 0)
                elapsed = max(0.001, time.time() - self._start_time)
                # This is adapter probe throughput, not the renderer's internal
                # render-loop FPS. It proves live request/response only.
                self._current_fps = min(60.0, self._frames_read / elapsed)
                self._connected = True
                self._last_error = None
                return True
            self._frames_dropped += 1
            self._last_error = str(data.get("error") or data)
            self._connected = False
            return False
        except Exception as exc:
            self._frames_dropped += 1
            self._last_error = str(exc)
            self._connected = False
            return False

    async def connect_renderer_websocket(self) -> bool:
        """Start/connect to the real Rust renderer WebSocket and prove a frame."""
        if not self.available:
            self._last_error = f"renderer binary missing: {self.renderer_binary}"
            return False

        if not self._port_open() and self.auto_start:
            try:
                env = os.environ.copy()
                env.setdefault("PUBCAST_WS_PORT", str(self.port))
                self._process = subprocess.Popen(
                    [str(self.renderer_binary)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=str(self.renderer_binary.parent.parent),
                    env=env,
                )
                self._owns_process = True
            except Exception as exc:
                self._last_error = f"failed to start renderer: {exc}"
                return False

        if not await self._wait_for_port():
            self._last_error = f"renderer websocket not listening on {self.host}:{self.port}"
            return False

        return await self._send_probe()

    async def start_frame_monitoring(self) -> None:
        """Keep a low-rate internal probe active for diagnostics.

        The monitor proves that the renderer process still accepts PubCast motion
        payloads. It intentionally does not claim browser WebRTC output.
        """
        if self._monitor_task and not self._monitor_task.done():
            return None

        async def _loop() -> None:
            while True:
                try:
                    await self._send_probe()
                    await asyncio.sleep(1.0)
                except asyncio.CancelledError:
                    break
                except Exception as exc:  # pragma: no cover - defensive loop guard
                    self._last_error = str(exc)
                    await asyncio.sleep(1.0)

        self._monitor_task = asyncio.create_task(_loop())
        return None

    def connect_shared_memory(self) -> bool:
        """Shared memory is not active in this adapter."""
        return False

    async def send_motion_frame(self, avatar_id: str, motion_data: Dict[str, Any]) -> bool:
        """Send a normalized motion payload to the Rust WebSocket renderer."""
        payload = {
            "avatar_id": avatar_id,
            "motion_data": motion_data,
            "timestamp": time.time(),
        }
        try:
            import websockets
            async with websockets.connect(f"ws://{self.host}:{self.port}", open_timeout=1.0, close_timeout=0.5) as ws:
                await ws.send(json.dumps(payload))
                response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            data = json.loads(response) if isinstance(response, str) else {}
            ok = data.get("ok") is True
            if ok:
                self._frames_read += 1
                self._last_latency_us = int(data.get("latency_us", 0) or 0)
                self._connected = True
            else:
                self._frames_dropped += 1
                self._last_error = str(data.get("error") or data)
            return ok
        except Exception as exc:
            self._frames_dropped += 1
            self._last_error = str(exc)
            self._connected = False
            return False

    def get_status(self) -> Dict[str, Any]:
        process_alive = self._process.poll() is None if self._process else None
        if self._process is None and self._port_open():
            process_alive = True
        return {
            "available": self.available,
            "connected": self._connected,
            "transport": self._transport,
            "renderer_binary": str(self.renderer_binary) if self.renderer_binary else None,
            "renderer_process_alive": process_alive,
            "renderer_websocket_url": f"ws://{self.host}:{self.port}",
            "webrtc_signaling_available": False,
            "shared_memory_available": False,
            "reason": None if self._connected else self._last_error,
            "webrtc_connections": 0,
            "current_fps": float(self._current_fps if self._connected else 0.0),
            "frames_read": self._frames_read,
            "frames_dropped": self._frames_dropped,
            "last_latency_us": self._last_latency_us,
            "last_probe_at": self._last_probe_at,
        }

    async def shutdown(self) -> None:
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        if self._process and self._owns_process:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._connected = False
