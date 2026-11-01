from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from .stage_service import StageService


def create_stage_router(stage: StageService) -> APIRouter:
    r=APIRouter(prefix="/api/stage", tags=["PubWorld Stage"])
    @r.get("/state")
    async def state(): return stage.state()
    @r.get("/scenes")
    async def scenes(): return {"scenes":stage.store.list_scenes()}
    @r.post("/load/{scene_id}")
    async def load(scene_id:str):
        try: stage.load_scene(scene_id)
        except KeyError: raise HTTPException(404,"scene not found")
        return stage.state()
    @r.post("/actor/{actor_id}")
    async def actor(actor_id:str, body:Dict[str,Any]):
        if not body.get("avatar_id"): raise HTTPException(400,"avatar_id required")
        return stage.upsert_actor(actor_id,str(body["avatar_id"]),position=body.get("position"),rotation_deg=body.get("rotation_deg"),visible=body.get("visible",True)).__dict__
    @r.delete("/actor/{actor_id}")
    async def actor_delete(actor_id:str): return {"removed":stage.remove_actor(actor_id)}
    @r.post("/screen/focus")
    async def focus(body:Dict[str,Any]):
        try: stage.focus_screen(body.get("screen_id"), program=bool(body.get("program",False)))
        except KeyError: raise HTTPException(404,"screen not found")
        return stage.state()
    return r
