"""Reconstructed 2026-09-13 Stage-1 Rust camera-control coordinator.

This is intentionally *not* camera authority. CameraManager owns desired state;
this runtime mirrors canonical VOXEL_3D state to the authenticated Rust receiver.
ACKs prove control-plane application only, never GPU/frame output.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import Any, Optional

from modules.cameras import CameraManager, CameraPoseEvent, CameraSource, CameraSwitchEvent, CameraTransport

PROTOCOL = "pubcast.camera.control.v1"

class RustCameraRuntime:
    def __init__(self, cameras:CameraManager, *, url:Optional[str]=None, token:Optional[str]=None, enabled:Optional[bool]=None):
        self.cameras=cameras
        self.url=url or os.getenv("PUBCAST_RUST_CAMERA_CONTROL_URL","ws://127.0.0.1:8765")
        self.enabled=(os.getenv("PUBCAST_ENABLE_RUST_CAMERA_CONTROL","0")=="1") if enabled is None else bool(enabled)
        self.token=token if token is not None else os.getenv("PUBCAST_CAMERA_CONTROL_TOKEN","")
        if self.enabled and not self.token:
            raise RuntimeError("PUBCAST_CAMERA_CONTROL_TOKEN is required when Rust camera control is enabled")
        self._ws=None; self._lock=asyncio.Lock(); self._sub=None; self._last_revision=0
        self.last_ack:Optional[dict]=None; self.last_error:Optional[str]=None
        self.ensure_minimum_voxel_cameras()

    def ensure_minimum_voxel_cameras(self, minimum:int=2)->None:
        existing=[c for c in self.cameras.list_sources() if c.transport==CameraTransport.VOXEL_3D]
        idx=1
        while len(existing)<minimum:
            cid=f"rust_cam_{idx}"; idx+=1
            if self.cameras.get(cid): continue
            src=CameraSource(source_id=cid,name=f"Rust Camera {len(existing)+1}",location="pubworld",description="Canonical Rust renderer camera slot",transport=CameraTransport.VOXEL_3D,endpoint=f"rust://{cid}",position=[0.0,1.65,4.0+len(existing)],rotation=[0.0,180.0,0.0],fov=50.0,tags=["voxel","rust","canonical-slot"])
            self.cameras.register(src); existing.append(src)

    def _revision(self)->int:
        candidate=time.time_ns() & ((1<<63)-1)
        self._last_revision=max(candidate,self._last_revision+1)
        return self._last_revision

    async def start(self)->dict:
        if not self.enabled: return self.status()
        import websockets
        self._ws=await websockets.connect(self.url)
        ack=await self._request("hello")
        if not ack.get("ok"): raise RuntimeError(ack.get("error") or "camera hello rejected")
        for source in self.cameras.list_sources():
            if source.transport==CameraTransport.VOXEL_3D:
                await self._register(source)
        if self._sub is None: self._sub=self.cameras.subscribe(self._on_camera_event)
        return self.status()

    async def stop(self)->None:
        if self._sub is not None: self.cameras.unsubscribe(self._sub); self._sub=None
        if self._ws is not None: await self._ws.close(); self._ws=None

    def _on_camera_event(self,event:Any)->None:
        if not self.enabled: return
        try: asyncio.get_running_loop().create_task(self._mirror(event))
        except RuntimeError: pass

    async def _mirror(self,event:Any)->None:
        source=self.cameras.get(getattr(event,"source_id",""))
        if source is None or source.transport!=CameraTransport.VOXEL_3D: return
        if isinstance(event,CameraSwitchEvent):
            mode="Program" if event.destination=="program" else "Preview"
            await self._request("set_mode",camera_id=source.source_id,revision=self._revision(),mode=mode,
                                position=source.position,rotation=source.rotation,fov=source.fov)
        elif isinstance(event,CameraPoseEvent):
            await self._request("update_pose",camera_id=source.source_id,revision=self._revision(),
                                position=event.position,rotation=event.rotation,fov=event.fov)

    async def _register(self,source:CameraSource)->dict:
        return await self._request("register",camera_id=source.source_id,revision=self._revision(),name=source.name,
                                   position=source.position,rotation=source.rotation,fov=source.fov)

    async def _request(self,action:str,**payload)->dict:
        if self._ws is None: raise RuntimeError("Rust camera control is not connected")
        request_id=uuid.uuid4().hex
        envelope={"protocol":PROTOCOL,"token":self.token,"request_id":request_id,"action":action,"timestamp":time.time(),**payload}
        async with self._lock:
            await self._ws.send(json.dumps(envelope,separators=(",",":")))
            raw=await self._ws.recv()
        ack=json.loads(raw)
        if ack.get("protocol")!=PROTOCOL or ack.get("request_id")!=request_id:
            self.last_error="mismatched camera-control ACK"
            await self._ws.close(); self._ws=None
            raise RuntimeError(self.last_error)
        self.last_ack=ack
        if not ack.get("ok"):
            self.last_error=str(ack.get("error") or "camera command rejected")
        return ack

    def status(self)->dict:
        return {"enabled":self.enabled,"connected":self._ws is not None,"url":self.url,
                "protocol":PROTOCOL,"stage":1,"frame_path_proven":False,
                "voxel_camera_count":sum(c.transport==CameraTransport.VOXEL_3D for c in self.cameras.list_sources()),
                "last_ack":self.last_ack,"last_error":self.last_error}
