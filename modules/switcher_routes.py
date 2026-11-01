from __future__ import annotations

import math
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from .route_security import require_role
from .cameras import CameraManager
from .director_engine import AutonomousDirector

class SwitcherService:
    def __init__(self, cameras:CameraManager, *, director:Optional[AutonomousDirector]=None, recording:Any=None):
        self.cameras=cameras; self.director=director or AutonomousDirector(); self.recording=recording
        self.transition={"type":"cut","duration_ms":0}
        self.scenes: Dict[str,dict]={}
        self.director.sync_from_camera_manager(cameras)

    def state(self)->dict:
        p=self.cameras.get_program_source(); v=self.cameras.get_preview_source()
        return {"program":getattr(p,"source_id",None),"preview":getattr(v,"source_id",None),
                "transition":dict(self.transition),"sources":[{"id":c.source_id,"name":c.name,"transport":c.transport.value,"endpoint":c.endpoint} for c in self.cameras.list_sources()]}
    def preview(self,camera_id:str)->bool: return self.cameras.set_preview_source(camera_id)
    def select(self, program: str, preview: str) -> bool:
        """Set a pair of confirmed, registered sources in one checked operation.

        Prevents the 2.5D stage from leaving only Program switched if Preview
        selection fails during package activation.
        """
        if not self.cameras.get(program) or not self.cameras.get(preview):
            return False
        if not self.cameras.set_program_source(program):
            return False
        if not self.cameras.set_preview_source(preview):
            return False
        self.transition = {"type":"cut","duration_ms":0}
        self.director.manual_cut(program)
        return True
    def cut(self,camera_id:Optional[str]=None, *, retain_transition:bool=False)->bool:
        # A take without an explicit source is an actual Program/Preview exchange,
        # not setting Program while leaving Preview stuck on the same camera.
        if camera_id is None:
            ok=self.cameras.take()
            target=self.cameras.get_program_source().source_id if ok else None
        else:
            ok=self.cameras.set_program_source(camera_id)
            target=camera_id if ok else None
        if ok and target: self.director.manual_cut(target)
        if ok and not retain_transition: self.transition={"type":"cut","duration_ms":0}
        return bool(ok)
    def auto(self, camera_id:Optional[str]=None, *, transition:str="dissolve", duration_ms:int=350)->bool:
        if transition not in {"cut","dissolve"}: raise ValueError("unsupported transition")
        if not isinstance(duration_ms,int) or isinstance(duration_ms,bool) or not 0<=duration_ms<=4000:
            raise ValueError("transition duration must be 0 to 4000 ms")
        previous=dict(self.transition)
        self.transition={"type":transition,"duration_ms":duration_ms}
        if transition == "dissolve":
            self.transition["started_at"] = time.time()
        try: ok=self.cut(camera_id,retain_transition=True)
        except Exception:
            self.transition=previous
            raise
        if not ok: self.transition=previous
        return ok


def _checked_pose(body:Dict[str,Any])->Dict[str,Any]:
    """Only finite numbers in range get through; anything else is a 400 before any camera is touched."""
    def nums(key,n,limit):
        v=body.get(key)
        if v is None: return None
        if not (isinstance(v,list) and len(v)==n and all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and abs(x)<=limit for x in v)):
            raise HTTPException(400,f"{key} must be {n} finite numbers between -{limit:g} and {limit:g}")
        return [float(x) for x in v]
    def one(key):
        v=body.get(key)
        if v is None: return None
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v): raise HTTPException(400,f"{key} must be a finite number")
        return float(v)
    return {"position":nums("position",3,10000),"rotation":nums("rotation",3,3600),"fov":one("fov"),"focus":one("focus")}


def create_switcher_router(service:SwitcherService)->APIRouter:
    r=APIRouter(prefix="/api/switcher",tags=["Director Switcher"])
    @r.get("/state")
    async def state(): return service.state()
    @r.post("/select")
    async def select_pair(body:Dict[str,Any], identity:Dict[str,Any]=Depends(require_role("mod"))):
        program, preview = body.get("program"), body.get("preview")
        if not isinstance(program,str) or not isinstance(preview,str) or not program or not preview:
            raise HTTPException(400,"program and preview camera IDs are required")
        if not service.select(program,preview): raise HTTPException(404,"one or both cameras not registered")
        return service.state()
    @r.post("/preview/{camera_id}")
    async def preview(camera_id:str, identity:Dict[str,Any]=Depends(require_role("mod"))):
        if not service.preview(camera_id): raise HTTPException(404,"camera not found")
        return service.state()
    @r.post("/cut")
    async def cut_preview(identity:Dict[str,Any]=Depends(require_role("mod"))):
        if not service.cut(): raise HTTPException(409,"no preview camera")
        return service.state()
    @r.post("/cut/{camera_id}")
    async def cut(camera_id:str, identity:Dict[str,Any]=Depends(require_role("mod"))):
        if not service.cut(camera_id): raise HTTPException(404,"camera not found")
        return service.state()
    @r.post("/transition")
    async def transition(body:Dict[str,Any], identity:Dict[str,Any]=Depends(require_role("mod"))):
        camera_id=body.get("camera_id")
        raw_duration=body.get("duration_ms",350)
        if isinstance(raw_duration,bool) or not isinstance(raw_duration,int): raise HTTPException(400,"duration_ms must be an integer")
        try:
            ok=service.auto(camera_id,transition=str(body.get("type") or "dissolve"),duration_ms=raw_duration)
        except ValueError as exc: raise HTTPException(400,str(exc)) from None
        if not ok: raise HTTPException(409,"camera not found or preview unset")
        return service.state()
    @r.post("/ptz/{camera_id}")
    async def ptz(camera_id:str,body:Dict[str,Any],identity:Dict[str,Any]=Depends(require_role("mod"))):
        """Move a camera: position [x,y,z] metres (y up), rotation [tilt,pan,roll] degrees, fov degrees, focus metres.
        Any of them may be sent alone. Every number is checked here, so a bad request changes nothing."""
        pose=_checked_pose(body)
        try: ok=service.cameras.update_pose(camera_id,**pose)
        except ValueError as exc: raise HTTPException(400,str(exc)) from None
        if not ok: raise HTTPException(404,"camera not found")
        src=service.cameras.get(camera_id)
        return {**service.state(),"pose":{"position":list(src.position),"rotation":list(src.rotation),"fov":src.fov,"focus":getattr(src,"focus",None)}}
    @r.get("/pose/{camera_id}")
    async def pose(camera_id:str):
        src=service.cameras.get(camera_id)
        if src is None: raise HTTPException(404,"camera not found")
        return {"camera_id":camera_id,"position":list(src.position),"rotation":list(src.rotation),"fov":src.fov,"focus":getattr(src,"focus",None)}
    @r.get("/scenes")
    async def scenes(): return {"scenes":service.scenes}
    return r
