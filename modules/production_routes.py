"""
modules/production_routes.py — Camera + Recording REST API
==============================================================================
Wires CameraManager and RecordingService into FastAPI.
Also provides WebSocket broadcast helpers so the control room
console receives live updates on camera switches and recording state.

Usage in main.py:
    from modules.cameras import create_default_cameras
    from modules.recording import create_recording_service
    from modules.production_routes import create_production_router

    cameras = create_default_cameras()
    recording = create_recording_service(DATA_DIR, cameras)
    app.include_router(create_production_router(cameras, recording, hub))

Rear View Foresight LLC — Feic Mo Chroí — 2026-03-24T08:00Z
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from zipfile import BadZipFile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse

from modules.capture import SessionCapture
from modules.cameras import CameraManager, CameraSource, CameraTransport
from modules.recording import (
    RecordingService,
    RecordingState,
    ContainerFormat,
)
from modules.route_security import bound_actor, require_role, current_identity, security
from modules.persistence import sanitize_filename, unique_child_path
from modules.runtime_control_routes import create_runtime_control_router
from modules.stage_compat_routes import create_stage_compat_router
from modules.blackbox_runtime import BlackBoxRuntimeWitness
from modules.studio_camera_preflight import all_camera_visibility, camera_visibility_report, recording_preflight, studio_readiness
from modules.program_audio import ProgramAudioState, apply_audio_event
from modules.program_audio_routes import create_program_audio_router
from modules.participant_audio import create_participant_audio_router
from starlette.requests import HTTPConnection
from modules.studio_console_actions import confirmed_stop_session_id, execute_studio_action, list_studio_actions

logger = logging.getLogger("pubcast.production")


async def _json_dict(request: Request) -> Dict[str, Any]:
    """Parse a request body as a JSON object with clean 400s."""
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Malformed JSON body: {exc.msg}")
    except Exception as exc:
        raise HTTPException(400, f"Invalid JSON body: {exc}")
    if not isinstance(body, dict):
        raise HTTPException(400, "JSON body must be an object")
    return body


def _string_field(body: Dict[str, Any], key: str, *, default: str = "", required: bool = False,
                  max_length: int = 256) -> str:
    value = body.get(key, default)
    if value is None:
        value = default
    if not isinstance(value, str):
        raise HTTPException(400, f"{key} must be a string")
    value = value.strip()
    if required and not value:
        raise HTTPException(400, f"{key} required")
    if len(value) > max_length:
        raise HTTPException(400, f"{key} must be <= {max_length} characters")
    return value


def _bool_field(body: Dict[str, Any], key: str, *, default: bool = False) -> bool:
    value = body.get(key, default)
    if not isinstance(value, bool):
        raise HTTPException(400, f"{key} must be a boolean")
    return value


def _numeric_field(body: Dict[str, Any], key: str, *, default: float | int, minimum: float | None = None) -> float:
    value = body.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(400, f"{key} must be numeric")
    value = float(value)
    if minimum is not None and value < minimum:
        raise HTTPException(400, f"{key} must be >= {minimum}")
    return value


def _vector3(body: Dict[str, Any], key: str) -> List[float]:
    value = body.get(key, [0.0, 0.0, 0.0])
    if not isinstance(value, list) or len(value) != 3:
        raise HTTPException(400, f"{key} must be a 3-item array")
    try:
        vector = [float(v) for v in value]
    except (TypeError, ValueError):
        raise HTTPException(400, f"{key} must contain only numeric values")
    return vector


def _string_list(body: Dict[str, Any], key: str, *, required: bool = False) -> List[str]:
    value = body.get(key, [])
    if value in (None, ""):
        value = []
    if not isinstance(value, list):
        raise HTTPException(400, f"{key} must be an array")
    cleaned: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise HTTPException(400, f"{key} items must be strings")
        item = item.strip()
        if not item:
            raise HTTPException(400, f"{key} items must not be blank")
        cleaned.append(item)
    if required and not cleaned:
        raise HTTPException(400, f"{key} must contain at least one value")
    return cleaned


def create_production_router(
    cameras: CameraManager,
    recording: RecordingService,
    hub: Any,
    blackbox: Optional[BlackBoxRuntimeWitness] = None,
    program_audio_state: Optional[ProgramAudioState] = None,
    include_overlapping_compat_routes: bool = True,
    capture: Optional[SessionCapture] = None,
) -> APIRouter:
    """Create the production API router."""
    async def protect_encoded_take(request: HTTPConnection):
        session_id = request.path_params.get("session_id")
        if request.url.path.startswith("/api/studio/actions/recording."):
            try:
                body = await request.json()
                session_id = body.get("session_id") if isinstance(body, dict) else None
            except ValueError:
                pass
        if not isinstance(session_id, str):
            return
        try:
            session = recording.get_session(session_id)
        except KeyError:
            return
        if getattr(session, "ingest", None):
            identity = await current_identity(request, await security(request))
            if not identity.get("authenticated") or identity.get("user_id") != session.operator:
                raise HTTPException(404, "Take not found")
            if request.method != "GET" and not request.url.path.endswith("/export"):
                raise HTTPException(409, "Encoded take originals are immutable; use their upload controls")
    router = APIRouter(tags=["Production"], dependencies=[Depends(protect_encoded_take)])
    program_audio_state = program_audio_state or ProgramAudioState()
    capture = capture or SessionCapture(cameras, recording)

    # Compatibility bridge routes are mounted here because main.py already mounts
    # production_routes after the core runtime managers exist. These bridge routers
    # do not own the systems; they delegate to existing managers and return explicit
    # unavailable payloads instead of letting the panoramic/control-room UI hit 404s.
    router.include_router(create_runtime_control_router(include_overlapping_routes=include_overlapping_compat_routes))
    router.include_router(create_stage_compat_router(hub=hub, cameras=cameras, recording=recording, include_overlapping_routes=include_overlapping_compat_routes))
    router.include_router(create_program_audio_router(program_audio_state, blackbox=blackbox, hub=hub))
    router.include_router(create_participant_audio_router())

    def _blackbox_event(event_type: str, *, source: str, actor: str = "SYS", data: Optional[Dict[str, Any]] = None) -> None:
        if blackbox is not None:
            blackbox.record_event(event_type, source=source, actor=actor, data=data or {})

    # —
    # CAMERAS
    # —

    @router.get("/api/cameras")
    async def list_cameras():
        """List all registered camera sources with status."""
        sources = cameras.list_sources()
        statuses = {s.source_id: s for s in cameras.list_status()}
        pgm = cameras.get_program_source()
        pvw = cameras.get_preview_source()

        return {
            "cameras": [
                {
                    "source_id": cam.source_id,
                    "name": cam.name,
                    "location": cam.location,
                    "transport": cam.transport.value,
                    "endpoint": cam.endpoint,
                    "position": cam.position,
                    "rotation": cam.rotation,
                    "fov": cam.fov,
                    "tags": cam.tags,
                    "status": {
                        "online": statuses.get(cam.source_id, None)
                                  and statuses[cam.source_id].online,
                        "latency_ms": getattr(statuses.get(cam.source_id), "latency_ms", None),
                        "frame_rate": getattr(statuses.get(cam.source_id), "frame_rate", None),
                    },
                }
                for cam in sources
            ],
            "program": pgm.source_id if pgm else None,
            "preview": pvw.source_id if pvw else None,
        }

    @router.get("/api/cameras/program")
    async def get_program_camera():
        """Current program (live/on-air) camera source, if any."""
        pgm = cameras.get_program_source()
        return {"source_id": pgm.source_id if pgm else None}

    @router.get("/api/cameras/preview")
    async def get_preview_camera():
        """Current preview (next-up) camera source, if any."""
        pvw = cameras.get_preview_source()
        return {"source_id": pvw.source_id if pvw else None}

    @router.get("/api/cameras/visibility")
    async def camera_visibility_all(identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Check whether registered cameras are plausibly visible and recordable."""
        report = all_camera_visibility(cameras)
        _blackbox_event(
            "camera.visibility",
            source="recorder",
            actor=str(identity.get("user_id") or "director"),
            data={"camera_count": len(report["cameras"]), "program": report.get("program"), "ok": report.get("ok")},
        )
        return report

    @router.get("/api/cameras/{source_id}/visibility")
    async def camera_visibility_one(source_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Check one camera source before switching or recording it."""
        camera = cameras.get(source_id)
        if camera is None:
            raise HTTPException(404, f"Camera source '{source_id}' not found.")
        report = camera_visibility_report(camera, cameras.status(source_id))
        _blackbox_event(
            "camera.visibility",
            source="recorder",
            actor=str(identity.get("user_id") or "director"),
            data={"source_id": source_id, "visible": report.get("visible"), "recordable": report.get("recordable")},
        )
        return report
    @router.post("/api/cameras/switch")
    async def switch_camera(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Switch program or preview camera. Broadcasts to all control rooms."""
        body = await _json_dict(request)
        target = _string_field(body, "target", default="program", max_length=32) or "program"
        source_id = _string_field(body, "source_id", required=True, max_length=128)

        if target == "program":
            ok = cameras.set_program_source(source_id)
        elif target == "preview":
            ok = cameras.set_preview_source(source_id)
        else:
            raise HTTPException(400, f"Invalid target '{target}'. Use 'program' or 'preview'.")

        if not ok:
            raise HTTPException(404, f"Camera source '{source_id}' not found.")

        _blackbox_event("broadcast.program_frame", source="recorder", actor=str(identity.get("user_id") or "director"), data={"camera_action": "switch", "target": target, "source_id": source_id})

        if hub and not getattr(hub, "camera_events_bridged", False):
            pgm = cameras.get_program_source()
            pvw = cameras.get_preview_source()
            await hub.broadcast_system_event({
                "type": "camera_switch",
                "payload": {
                    "target": target,
                    "source_id": source_id,
                    "program": pgm.source_id if pgm else None,
                    "preview": pvw.source_id if pvw else None,
                    "timestamp": time.time(),
                },
            })

        return {"ok": True, "target": target, "source_id": source_id}

    @router.post("/api/cameras/cut")
    async def cut_cameras(identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Swap program and preview (standard broadcast CUT transition)."""
        pgm = cameras.get_program_source()
        pvw = cameras.get_preview_source()

        if not pgm or not pvw:
            raise HTTPException(400, "Both program and preview must be set to cut.")

        if not cameras.take():
            raise HTTPException(409, "Camera cut could not complete")

        _blackbox_event("broadcast.program_frame", source="recorder", actor=str(identity.get("user_id") or "director"), data={"camera_action": "cut", "program": pvw.source_id, "preview": pgm.source_id})

        if hub:
            await hub.broadcast_system_event({
                "type": "camera_cut",
                "payload": {
                    "new_program": pvw.source_id,
                    "new_preview": pgm.source_id,
                    "timestamp": time.time(),
                },
            })

        return {"ok": True, "program": pvw.source_id, "preview": pgm.source_id}

    @router.post("/api/cameras/register")
    async def register_camera(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Register a new camera source."""
        body = await _json_dict(request)
        try:
            source_id = _string_field(body, "source_id", required=True, max_length=128)
            source = CameraSource(
                source_id=source_id,
                name=_string_field(body, "name", default=source_id, max_length=128),
                location=_string_field(body, "location", default="virtual", max_length=128) or "virtual",
                description=_string_field(body, "description", default="", max_length=512),
                transport=CameraTransport(_string_field(body, "transport", default="virtual", max_length=64) or "virtual"),
                endpoint=_string_field(body, "endpoint", default=f"virtual://{source_id}", max_length=512),
                position=_vector3(body, "position"),
                rotation=_vector3(body, "rotation"),
                fov=_numeric_field(body, "fov", default=60.0, minimum=1.0),
                tags=_string_list(body, "tags"),
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))

        cameras.register(source)
        _blackbox_event("broadcast.program_frame", source="recorder", actor=str(identity.get("user_id") or "director"), data={"camera_action": "register", "source_id": source.source_id, "transport": source.transport.value})
        return {"ok": True, "source_id": source.source_id}

    # —
    # RECORDING
    # —

    @router.get("/api/recording/profiles")
    async def list_profiles():
        """List available encoding profiles."""
        profiles = [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "container": p.container.value,
                "video_codec": p.video_codec,
                "audio_codec": p.audio_codec,
                "resolution": p.resolution,
                "description": p.description,
            }
            for p in recording.list_profiles()
        ]
        return {"profiles": profiles, "count": len(profiles)}

    @router.get("/api/recording/sessions")
    async def list_sessions(identity: Dict[str, Any] = Depends(current_identity)):
        """List all recording sessions."""
        return [s.to_dict() for s in recording.list_sessions()
                if not getattr(s, "ingest", None) or (identity.get("authenticated") and identity.get("user_id") == s.operator)]

    @router.post("/api/recording/preflight")
    async def recording_preflight_route(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Validate camera visibility, source policy, and profile availability before recording."""
        body = await _json_dict(request)
        sources = _string_list(body, "sources")
        profile_id = _string_field(body, "profile_id", default="broadcast_mp4", max_length=128) or "broadcast_mp4"
        host_override = _bool_field(body, "host_override", default=False)
        report = recording_preflight(cameras, recording, sources=sources, profile_id=profile_id, host_override=host_override)
        _blackbox_event(
            "recording.preflight",
            source="recording",
            actor=str(identity.get("user_id") or "director"),
            data={"ready": report.get("ready"), "sources": ",".join(report.get("sources", [])), "profile_id": profile_id, "issue_count": len(report.get("issues", []))},
        )
        return report

    @router.get("/api/studio/readiness")
    async def studio_readiness_route(identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Aggregate the current camera and recording readiness for the studio."""
        report = studio_readiness(cameras, recording, audio_status=program_audio_state.status())
        _blackbox_event(
            "studio.readiness",
            source="recording",
            actor=str(identity.get("user_id") or "director"),
            data={"ready": report.get("ready"), "program": report.get("program"), "camera_count": report.get("camera_count"), "recording_profiles": report.get("recording_profiles")},
        )
        return report

    @router.get("/api/studio/actions")
    async def studio_actions_manifest(identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Return stable action IDs that future studio-console hotspots can call."""
        return {"actions": list_studio_actions()}

    @router.post("/api/studio/actions/{action_id}")
    async def studio_action_execute(action_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Execute a stable studio action by ID for console art or hotspot overlays."""
        body = await _json_dict(request)
        actor = str(identity.get("user_id") or "director")
        try:
            if action_id == "recording.stop":
                await capture.finish(confirmed_stop_session_id(body))
            response = execute_studio_action(
                action_id,
                body,
                cameras=cameras,
                recording=recording,
                audio_state=program_audio_state,
                actor=actor,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

        if response.get("ok") and action_id == "recording.start":
            session_data = response.get("result", {})
            session_id = session_data.get("session_id")
            if session_id:
                session = recording.get_session(session_id)
                capture_paths = await capture.start(session)
                if capture_paths:
                    session_data["capture_paths"] = capture_paths
        _blackbox_event(
            "studio.action",
            source="recording",
            actor=actor,
            data={"action_id": action_id, "ok": bool(response.get("ok"))},
        )
        if hub:
            await hub.broadcast_system_event({
                "type": "studio_action",
                "payload": {
                    "action_id": action_id,
                    "ok": bool(response.get("ok")),
                    "actor": actor,
                    "result": response.get("result", {}),
                    "timestamp": time.time(),
                },
            })
        return response
    @router.post("/api/recording/start")
    async def start_recording(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Start a new recording session."""
        body = await _json_dict(request)
        sources = _string_list(body, "sources")
        if not sources:
            pgm = cameras.get_program_source()
            if pgm:
                sources = [pgm.source_id]
            else:
                raise HTTPException(400, "No sources specified and no program source set.")

        profile_id = _string_field(body, "profile_id", default="broadcast_mp4", max_length=128) or "broadcast_mp4"
        operator = bound_actor(request=request, identity=identity, explicit_value=body.get("operator"), field_name="operator") or "director"
        session_id = _string_field(body, "session_id", default="", max_length=128) or None
        countdown = int(_numeric_field(body, "countdown_seconds", default=5, minimum=0))
        host_override = _bool_field(body, "host_override", default=False)

        try:
            session = recording.start_session(
                session_id=session_id,
                sources=sources,
                profile_id=profile_id,
                operator=operator,
                countdown_seconds=countdown,
                host_override=host_override,
            )
        except (ValueError, PermissionError, KeyError) as exc:
            raise HTTPException(400, str(exc))

        capture_paths = await capture.start(session)

        if hub:
            await hub.broadcast_system_event({
                "type": "recording_started",
                "payload": {
                    "session_id": session.session_id,
                    "sources": session.sources,
                    "profile_id": session.profile_id,
                    "state": session.state.value,
                    "countdown": countdown,
                    "capture_paths": capture_paths,
                },
            })

        response = session.to_dict()
        if capture_paths:
            response["capture_paths"] = capture_paths
        return response

    @router.post("/api/recording/{session_id}/activate")
    async def activate_recording(session_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Activate a recording session (transition from countdown to active)."""
        try:
            session = recording.activate_session(session_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))

        capture_paths = await capture.start(session)

        if hub:
            await hub.broadcast_system_event({
                "type": "recording_active",
                "payload": {"session_id": session_id, "capture_paths": capture_paths},
            })

        response = session.to_dict()
        if capture_paths:
            response["capture_paths"] = capture_paths
        return response

    @router.post("/api/recording/{session_id}/stop")
    async def stop_recording(session_id: str, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Stop a recording session."""
        try:
            artifacts = await capture.finish(session_id)
            session = recording.stop_session(session_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

        if hub:
            await hub.broadcast_system_event({
                "type": "recording_stopped",
                "payload": {
                    "session_id": session_id,
                    "duration": (session.ended_at or time.time()) - session.started_at,
                    "artifacts": artifacts,
                    "capture_errors": session.capture_errors,
                },
            })

        return session.to_dict()

    @router.post("/api/recording/{session_id}/pause")
    async def pause_recording(session_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Pause or resume a recording session."""
        body = await _json_dict(request)
        paused = _bool_field(body, "paused", default=True)
        try:
            session = await capture.set_paused(session_id, paused)
        except (RuntimeError, ProcessLookupError) as exc:
            raise HTTPException(409, str(exc)) from exc
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))
        return session.to_dict()

    @router.post("/api/recording/{session_id}/marker")
    async def add_marker(session_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Add a timestamp marker to a recording session."""
        body = await _json_dict(request)
        label = _string_field(body, "label", required=True, max_length=256)
        operator = bound_actor(request=request, identity=identity, explicit_value=body.get("operator"), field_name="operator") if body.get("operator") else identity.get("user_id")
        try:
            marker = recording.mark_moment(session_id, label, operator)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        return {"ok": True, "timestamp": marker.timestamp, "label": marker.label}

    @router.post("/api/recording/{session_id}/export")
    async def export_recording(session_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Export a recording session as a zip bundle."""
        body = await _json_dict(request)
        container = _string_field(body, "format", default="mp4", max_length=16) or "mp4"
        try:
            fmt = ContainerFormat(container)
        except ValueError:
            raise HTTPException(400, f"Invalid format '{container}'. Use: mp4, webm, wav, mov")

        try:
            export_path = await asyncio.to_thread(
                recording.export_session, session_id, container=fmt
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))

        return FileResponse(
            export_path,
            media_type="application/zip",
            filename=export_path.name,
        )

    @router.post("/api/recording/import")
    async def import_recording(file: UploadFile = File(...), identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Import a recording session from a zip bundle."""
        import_dir = recording.imports_dir
        filename = sanitize_filename(file.filename or "")
        if not filename:
            raise HTTPException(400, "Uploaded file must have a filename")
        if not filename.lower().endswith(".zip"):
            raise HTTPException(400, "Recording import requires a .zip bundle")
        limit = int(os.environ.get("PUBCAST_RECORDING_IMPORT_MAX_BYTES", str(64 * 1024 ** 3)))
        # Reserve atomically: two uploads with the same name must not clobber
        # one another between path selection and opening the file.
        while True:
            import_path = unique_child_path(import_dir, filename)
            try:
                upload_target = open(import_path, "xb")
                break
            except FileExistsError:
                continue
        try:
            size = 0
            with upload_target as f:
                while chunk := await file.read(1 << 20):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(413, "Recording upload exceeds the import storage budget")
                    f.write(chunk)
            session = await asyncio.to_thread(recording.import_session, import_path, operator=str(identity["user_id"]))
        except (ValueError, FileNotFoundError, BadZipFile) as exc:
            raise HTTPException(400, str(exc)) from exc
        return session.to_dict()

    @router.get("/api/recording/storage")
    async def storage_status():
        """Get recording storage usage."""
        return recording.storage_status()

    @router.get("/api/recording/privacy")
    async def privacy_matrix():
        """Get recording privacy rules per room."""
        return recording.privacy_matrix()

    # —
    # PANIC / Emergency
    # —

    @router.post("/api/production/video-cue")
    async def video_cue(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Shared, acknowledged black/preview-bars state for the actual 2.5D renderer."""
        body = await _json_dict(request)
        cue = body.get("cue")
        enabled = body.get("enabled")
        if cue not in {"blackout", "preview_bars"} or not isinstance(enabled, bool):
            raise HTTPException(400, "cue must be blackout/preview_bars and enabled must be boolean")
        if hub is None:
            raise HTTPException(503, "Production state hub unavailable")
        now = time.time()
        patch = {cue: enabled, cue + "_seq": now}
        hub.update_production_state(patch)
        await hub.broadcast_system_event({"type": "production_video_cue", "payload": {**patch, "cue": cue, "actor": str(identity.get("user_id") or "director")}})
        _blackbox_event("production.video_cue", source="system",
                        actor=str(identity.get("user_id") or "director"), data=patch)
        return {"ok": True, **patch}

    @router.post("/api/production/panic")
    async def production_panic(identity: Dict[str, Any] = Depends(require_role("mod"))):
        """Emergency: stop active captures, silence program audio, cue black.

        Reports partial failures explicitly; changing an indicator is not proof
        that FFmpeg and other capture workers actually stopped.
        """
        now = time.time()
        stopped, capture_errors = [], []
        apply_audio_event(program_audio_state, {"action": "stop_all"})
        program_audio_state.publish({"action": "stop_all"})
        apply_audio_event(program_audio_state, {"action": "set_volume", "bus": "master", "volume": 0})
        program_audio_state.publish({"action": "set_volume", "bus": "master", "volume": 0})
        if hub:
            hub.update_production_state({
                "on_air": False,
                "camera": "black",
                "lower_third": "",
                "panic_seq": now,
                "blackout": True,
                "blackout_seq": now,
            })

        async def stop_take(session):
            try:
                await capture.finish(session.session_id)
                capture_errors.extend({"session_id": session.session_id, "source": source, "error": message}
                                      for source, message in session.capture_errors.items())
            except Exception as exc:
                capture_errors.append({"session_id": session.session_id, "error": str(exc)})
            try:
                recording.stop_session(session.session_id)
                stopped.append(session.session_id)
            except Exception as exc:
                capture_errors.append({"session_id": session.session_id, "error": str(exc)})

        active_states = (RecordingState.ACTIVE, RecordingState.COUNTDOWN, RecordingState.PAUSED)
        await asyncio.gather(*(stop_take(session) for session in recording.list_sessions()
                               if session.state in active_states))
        if hub:
            await hub.broadcast_system_event({
                "type": "production_panic",
                "payload": {
                    "timestamp": now,
                    "sessions_stopped": stopped,
                    "capture_errors": capture_errors,
                    "message": "PANIC — capture stop requested, program audio silenced, black video cued",
                },
            })
        _blackbox_event("production.panic", source="system",
                        actor=str(identity.get("user_id") or "director"),
                        data={"sessions_stopped": stopped, "capture_errors": capture_errors, "panic_seq": now})
        return {"ok": not capture_errors, "sessions_stopped": stopped,
                "capture_errors": capture_errors, "audio_muted": True,
                "blackout_cued": bool(hub), "panic_seq": now}

    return router







