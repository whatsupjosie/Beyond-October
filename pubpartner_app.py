"""Canonical PubPartner application entry point.

This boots the persistent friend layer plus the minimum control plane required
for Alex, Jeremy, Pub Manager, Governance, authentication, and provider
interchangeability to work together. Heavy PubCast studio systems (camera,
renderer, recording, voxel, e-PETE) remain off unless the full ``main.py`` app
is deliberately launched.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from modules import alex_routes, auth as auth_module
from modules import auth_routes, dressing_room_security as dr_security
from modules import pubpartner_routes, userdb
from modules.alex_core import AlexCore
from modules.alex_jeremy_bridge import AlexJeremyBridge
from modules.governance import GovernanceEngine
from modules.governance_routes import create_governance_router
from modules.pub_manager_authority import (
    PubManagerAuthorityStore,
    create_pub_manager_authority_router,
    create_pub_manager_control_router,
)
from modules.pubpartner_backup import create_friend_backup
from modules.pubpartner_vessel import PubPartnerVesselRuntime

try:
    from modules.byok_manager import BYOKManager
except ImportError:  # pragma: no cover - optional partial build
    BYOKManager = None  # type: ignore

try:
    from modules.jeremy_cricket import CricketKeeper
except ImportError:  # pragma: no cover - optional partial build
    CricketKeeper = None  # type: ignore

logger = logging.getLogger("pubpartner.app")
ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATA_DIR = Path(
    os.environ.get("PUBPARTNER_DATA_DIR")
    or os.environ.get("PUBCAST_DATA_DIR")
    or ROOT / "data"
).expanduser().resolve()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the friend layer and its non-negotiable authority path."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # userdb resolves its path at import time; keep it aligned when tests or an
    # embedding host replace DATA_DIR before startup.
    userdb._DB_PATH = DATA_DIR / "users.db"
    await userdb.init_db()
    await userdb.create_owner_if_not_exists()
    auth_routes.set_auth_instance(auth_module)

    governance = GovernanceEngine(DATA_DIR)
    spine_holder: dict[str, Any] = {}

    async def execute_engineering_action(row: dict[str, Any]) -> dict[str, Any]:
        """Execute only actions the minimal runtime can prove it performed."""
        action = str(row.get("action") or "")
        if action == "emergency_save":
            user_id = str(row.get("target_user_id") or row.get("packet_user_id") or "anon")
            result = create_friend_backup(DATA_DIR, user_id=user_id, friend_id="alex")
            return {"executor": "pubpartner_only", "action": action, "backup": result}
        if action == "reduce_performance":
            # The minimal app already omits all heavy studio systems. Recording
            # that state is honest; pretending to throttle absent hardware is not.
            app.state.performance_mode = "minimal"
            return {
                "executor": "pubpartner_only",
                "action": action,
                "changed": False,
                "state": "already_minimal",
                "studio_systems_started": False,
            }
        if action == "stop_recording":
            return {
                "executor": "pubpartner_only",
                "action": action,
                "changed": False,
                "recording_active": False,
                "studio_systems_started": False,
            }
        if action == "select_recovery_path":
            selected = str((row.get("metadata") or {}).get("recovery_path") or "").strip()
            if not selected:
                raise RuntimeError("no explicit recovery_path supplied")
            return {"executor": "pubpartner_only", "action": action, "selected": selected}
        raise RuntimeError(f"no minimal-runtime executor for {action}")

    pub_manager = PubManagerAuthorityStore(
        DATA_DIR,
        blackbox_logger=dr_security.log_black_box_event,
        executor=execute_engineering_action,
    )
    alex_bridge = AlexJeremyBridge(
        DATA_DIR,
        authority_reviewer=pub_manager.reviewer,
        blackbox_logger=dr_security.log_black_box_event,
    )
    alex_core = AlexCore(user_id="default", data_dir=DATA_DIR / "alex")
    alex_routes.set_alex_instance(alex_core)
    alex_routes.set_alex_provider(alex_bridge.alex_for)

    cricket: Any = None
    if CricketKeeper is not None:
        try:
            cricket = CricketKeeper(data_dir=DATA_DIR / "jeremy")
            await cricket.init()
        except Exception as exc:  # continuity aid; control plane still remains
            logger.warning("Jeremy memory unavailable; continuing without it: %s", exc)
            cricket = None

    vessel = PubPartnerVesselRuntime.open_or_create(
        DATA_DIR / "pubpartner" / "vessels" / "alex.pubpartner"
    )
    spine = pubpartner_routes.configure_pubpartner_spine(
        data_dir=DATA_DIR,
        alex_bridge=alex_bridge,
        cricket_keeper=cricket,
        vessel_runtime=vessel,
    )
    spine_holder["spine"] = spine

    if BYOKManager is not None:
        try:
            byok = BYOKManager(DATA_DIR / "byok")
            pubpartner_routes.configure_pubpartner_byok(byok)
            app.state.byok_manager = byok
        except Exception as exc:
            logger.warning("BYOK unavailable; local/offline friend loop remains usable: %s", exc)

    # Register the object-bound routers once. This happens before lifespan
    # yields, so the control plane is live before the first request is served.
    if not getattr(app.state, "control_plane_routes_registered", False):
        app.include_router(alex_routes.router)
        app.include_router(create_pub_manager_authority_router(pub_manager, alex_bridge))
        app.include_router(create_pub_manager_control_router(pub_manager, alex_bridge))
        app.include_router(
            create_governance_router(
                governance,
                hub=None,
                authority_bridge=alex_bridge,
                authority_store=pub_manager,
            )
        )
        app.state.control_plane_routes_registered = True

    app.state.alex_core = alex_core
    app.state.alex_bridge = alex_bridge
    app.state.pub_manager_authority = pub_manager
    app.state.governance = governance
    app.state.pubpartner_spine = spine
    app.state.pubpartner_vessel = vessel
    app.state.cricket_keeper = cricket
    logger.info(
        "PubPartner runtime ready: Alex + Jeremy + Pub Manager + Governance active; "
        "optional PubCast studio systems were not started"
    )
    try:
        yield
    finally:
        alex_bridge.shutdown()
        if cricket is not None:
            try:
                await cricket.close_all()
            except AttributeError:
                try:
                    await cricket.close()
                except Exception:
                    logger.exception("Failed to close Jeremy memory")
            except Exception:
                logger.exception("Failed to close Jeremy memory")


app = FastAPI(
    title="PubPartner",
    version="0.1.0-prebeta.9-character-audit",
    lifespan=lifespan,
)

_allowed = os.environ.get("PUBCAST_ALLOWED_ORIGINS", "http://127.0.0.1:8000")
origins = [item.strip() for item in _allowed.split(",") if item.strip() and item.strip() != "*"]
if not origins:
    origins = ["http://127.0.0.1:8000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Client-Id"],
)

# Stateless/global routers can be mounted immediately. Object-bound control
# routers are mounted in lifespan after their stores and bridges exist.
app.include_router(auth_routes.router)
app.include_router(pubpartner_routes.router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/pubpartner")


@app.get("/pubpartner", include_in_schema=False)
async def pubpartner_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "pubpartner.html")


@app.get("/api/pubpartner/app-health")
async def app_health() -> dict[str, Any]:
    return {
        "ok": True,
        "runtime": "pubpartner_only",
        "friend_layer": "ready",
        "control_plane": "alex_jeremy_pub_manager_governance",
        "optional_pubcast_studio_started": False,
        "default_friend": "alex",
    }
