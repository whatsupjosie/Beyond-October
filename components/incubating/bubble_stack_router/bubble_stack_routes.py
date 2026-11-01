"""
modules/bubble_stack_routes.py — Bubble Stack PIKPC API Routes
════════════════════════════════════════════════════════════════

The upstream bubble_stack_pikpc/routes.py builds its own standalone
FastAPI() app via make_app() — inconsistent with every other PubCast
route module, which exposes a create_X_router(...) -> APIRouter that
main.py mounts onto the single shared app (see production_routes.py,
governance_routes.py, byok_routes.py).

This file is that adapter: same three real endpoints (frame ingest,
summary, point query) from the original routes.py, wrapped as a
mountable router instead of a second app. No behavior changed —
engine.step()/jeremy_room_summary()/query_point() calls are identical
to the original.

Usage in main.py:
    from modules.bubble_stack_routes import create_bubble_stack_router
    app.include_router(create_bubble_stack_router(bubble_stack_engine))

Rear View Foresight LLC — Feic Mo Chroí
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from modules.bubble_stack_pikpc.core import AABB, Vec3
from modules.bubble_stack_pikpc.engine import BubbleStackEngine, FrameObject
from modules.scene_contract import Scene, Engine as PhysicsEngine, Builder, Contact
from modules.streaming_chain_resolver import StreamingChainResolver, spawn_chain_from_contact

logger = logging.getLogger("pubcast.bubble_stack")


# ─── Request models ────────────────────────────────────────────────────────

class FrameObjectIn(BaseModel):
    object_id: str
    bounds: Dict[str, List[float]] = Field(..., description="{'min': [x,y,z], 'max': [x,y,z]}")
    semantic_tags: List[str] = Field(default_factory=list)


class FrameIngestRequest(BaseModel):
    dt: float | None = None
    objects: List[FrameObjectIn] = Field(default_factory=list)


# ─── Router factory ─────────────────────────────────────────────────────────

class ImpactRequest(BaseModel):
    attacker_id: str
    target_id: str
    relative_velocity: float = 5.0
    contact_point: List[float] | None = None
    props_dir: str | None = None


def create_bubble_stack_router(
    engine: BubbleStackEngine,
    props_dir: str | None = None,
) -> APIRouter:
    """
    Create the Bubble Stack API router bound to a live engine instance.
    Mirrors bubble_stack_pikpc/routes.py's three endpoints exactly,
    just mounted as a router instead of a standalone app.

    Also exposes /impact, wiring the physics chain
    (scene_contract.Scene/Engine/Builder + streaming_chain_resolver +
    deformation_math) that sandbox.py proved out on 5 hardcoded objects
    and scene_contract.py generalized to arbitrary ones. This uses
    Scene.demo_scene() as the active scene until a real scene-authority
    hookup replaces it — same caveat scene_contract.py states about itself.
    """
    router = APIRouter(prefix="/api/bubble-stack", tags=["Bubble Stack"])

    # Physics chain resolver state — separate from the BubbleStackEngine
    # spatial-attention system above; see scene_contract.py's own docstring
    # for why these are two different engines under one router.
    physics_scene = Scene.demo_scene()
    physics_engine = PhysicsEngine()
    physics_engine.bind_scene(physics_scene)
    physics_builder = Builder(props_dir=props_dir)
    active_chains: Dict[str, Any] = {}

    @router.post("/impact")
    async def trigger_impact(payload: ImpactRequest) -> Dict[str, Any]:
        """Trigger a physics impact chain between two objects in the demo scene."""
        if payload.target_id not in physics_scene.objects:
            return {"ok": False, "error": f"unknown target_id '{payload.target_id}'. "
                                           f"known: {list(physics_scene.objects.keys())}"}
        contact_point = tuple(payload.contact_point) if payload.contact_point else \
            tuple(physics_scene.objects[payload.target_id].position.tolist())
        contact = Contact(
            attacker_id=payload.attacker_id,
            target_id=payload.target_id,
            relative_velocity=payload.relative_velocity,
            contact_point=contact_point,
        )
        cid = await spawn_chain_from_contact(
            contact, physics_scene, physics_engine, physics_builder, active_chains
        )
        if cid is None:
            return {"ok": False, "error": "chain spawn failed"}
        task = active_chains.get(cid)
        chain = await task if task is not None else None
        if chain is None:
            return {"ok": True, "chain_id": cid, "status": "pending"}
        return {
            "ok": True,
            "chain_id": cid,
            "objects_affected": chain.objects_affected,
            "initial_energy_joules": round(chain.initial_energy_joules, 2),
            "remaining_energy_joules": round(chain.remaining_energy_joules, 2),
            "levels": [
                {
                    "depth": lvl.depth,
                    "object_states_after": lvl.object_states_after,
                }
                for lvl in chain.levels
            ],
        }

    @router.post("/frame")
    def ingest_frame(payload: FrameIngestRequest) -> Dict[str, Any]:
        objects: List[FrameObject] = []
        for item in payload.objects:
            mn = item.bounds["min"]
            mx = item.bounds["max"]
            objects.append(FrameObject(
                object_id=item.object_id,
                bounds=AABB(Vec3(*mn), Vec3(*mx)),
                semantic_tags=tuple(item.semantic_tags),
            ))
        result = engine.step(objects, dt=payload.dt)
        return {
            "time_seconds": result.time_seconds,
            "events": [engine._event_dict(e) for e in result.events],
            "transfer_pulses": [asdict(t) for t in result.transfer_pulses],
            "refined": result.refined,
            "collapsed": result.collapsed,
            "active_bubbles": result.active_bubbles,
        }

    @router.get("/summary")
    def summary() -> Dict[str, Any]:
        return engine.jeremy_room_summary()

    @router.get("/query")
    def query(x: float, y: float, z: float) -> Dict[str, Any]:
        return engine.query_point(Vec3(x, y, z))

    logger.info("[BubbleStack] Router created — /api/bubble-stack/*")
    return router


__all__ = ["create_bubble_stack_router"]
