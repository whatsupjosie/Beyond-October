from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from modules.route_security import require_role
from .avatar_adapter import AvatarPerformanceAdapter

def create_performance_router(adapter:AvatarPerformanceAdapter, manager:Any)->APIRouter:
    r=APIRouter(prefix="/api/performance",tags=["Avatar Performance"])
    @r.post("/avatar/{avatar_id}/frame")
    async def frame(avatar_id:str, body:Dict[str,Any], identity=Depends(require_role("crew"))):
        try:
            packet=await adapter.route_to_manager(body.get("frame",body),manager,avatar_id=avatar_id,preset=str(body.get("preset") or "MANNY"),source=str(body.get("source") or "auto"))
        except (ValueError,RuntimeError) as exc:
            raise HTTPException(409,str(exc))
        return {"ok":True,"avatar_id":avatar_id,"source":packet.source,"joint_count":len(packet.joints),"blendshape_count":len(packet.blendshapes),"confidence":packet.global_confidence}
    return r
