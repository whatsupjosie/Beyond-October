from __future__ import annotations
from fastapi import APIRouter, Depends
from .route_security import require_role

def create_rust_camera_router(runtime):
    r=APIRouter(prefix="/api/camera/rust-control",tags=["Rust Camera Control"])
    @r.get("/status")
    async def status(identity=Depends(require_role("crew"))):
        return runtime.status()
    return r
