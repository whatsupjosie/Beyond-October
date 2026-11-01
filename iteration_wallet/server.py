"""Local FastAPI route surface for Iteration Wallet.

The server exposes custody operations only. It does not execute custodied files,
does not delete, and does not call external services.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from iteration_wallet.blackbox import BlackBox
from iteration_wallet.ceremony import CeremonyLedger
from iteration_wallet.gatekeeper import ProtectedActionError, require_protected_action
from iteration_wallet.notification_manager import ActorKind, NotificationManager
from iteration_wallet.vault_v21 import VaultEngine, VaultError

APP_ROOT = Path.cwd() / ".iteration_wallet_runtime"
blackbox21 = BlackBox(APP_ROOT)
ceremony_ledger = CeremonyLedger()
human_access = NotificationManager(APP_ROOT, blackbox=blackbox21)
vault21 = VaultEngine(APP_ROOT, blackbox=blackbox21, ceremony_ledger=ceremony_ledger, strict_ceremony_tokens=False)

app = FastAPI(title="Iteration Wallet", version="2.1-standalone")


class ProjectRequest(BaseModel):
    name: str
    root_path: str = ""


class SectionRequest(BaseModel):
    name: str
    description: str = ""


class FileRequest(BaseModel):
    path: str
    notes: str = ""


class ProtectedMoveRequest(BaseModel):
    ceremony_token: Optional[str] = None
    reason: str = ""
    actor_kind: str = ActorKind.HUMAN.value
    human_ceremony_passed: bool = True


class RestoreRequest(BaseModel):
    target_state: str = "candidate"


@app.get("/api/v21/status")
def status_view():
    return {
        "status": "local",
        "product_laws": {"no_delete": True, "no_execute": True, "ai_stays_outside_yard": True},
        "projects": len(vault21.list_projects()),
        "blackbox": blackbox21.verify_chain(),
    }


@app.post("/api/v21/ceremony-tokens")
def issue_ceremony_token(actor_id: str = "local-human", scope: str = "promote_to_prime"):
    token = ceremony_ledger.issue(actor_id=actor_id, scope=scope)
    return {"token": token, "scope": scope, "raw_token_visibility": "shown once to local human caller only"}


@app.post("/api/v21/projects", status_code=status.HTTP_201_CREATED)
def create_project(req: ProjectRequest):
    try:
        return vault21.create_project(req.name, req.root_path)
    except VaultError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v21/projects")
def list_projects():
    return {"projects": vault21.list_projects()}


@app.post("/api/v21/projects/{project_id}/sections", status_code=status.HTTP_201_CREATED)
def create_section(project_id: str, req: SectionRequest):
    try:
        return vault21.create_section(project_id, req.name, req.description)
    except VaultError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v21/projects/{project_id}/sections/{section_id}")
def section_view(project_id: str, section_id: str):
    try:
        return vault21.get_section_view(project_id, section_id)
    except VaultError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v21/projects/{project_id}/sections/{section_id}/closed-catalog")
def closed_catalog(project_id: str, section_id: str):
    try:
        return vault21.get_closed_catalog_view(project_id, section_id)
    except VaultError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v21/projects/{project_id}/sections/{section_id}/raw-sources", status_code=status.HTTP_201_CREATED)
def add_raw_source(project_id: str, section_id: str, req: FileRequest):
    try:
        return vault21.add_raw_source(project_id, section_id, req.path, req.notes)
    except VaultError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v21/projects/{project_id}/sections/{section_id}/candidates", status_code=status.HTTP_201_CREATED)
def add_candidate(project_id: str, section_id: str, req: FileRequest):
    try:
        return vault21.add_candidate(project_id, section_id, req.path, req.notes)
    except VaultError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v21/projects/{project_id}/sections/{section_id}/candidates/{candidate_id}/promote")
def promote_candidate(project_id: str, section_id: str, candidate_id: str, req: ProtectedMoveRequest):
    try:
        require_protected_action("promote_candidate_to_prime", req.actor_kind, human_ceremony_passed=req.human_ceremony_passed, cradle_unlocked=True, gate=human_access)
        return vault21.promote_to_prime(project_id, section_id, candidate_id, req.ceremony_token, req.reason)
    except (VaultError, ProtectedActionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v21/projects/{project_id}/sections/{section_id}/files/{file_id}/remove")
def move_to_removed(project_id: str, section_id: str, file_id: str, req: ProtectedMoveRequest):
    try:
        require_protected_action("remove_from_active", req.actor_kind, human_ceremony_passed=req.human_ceremony_passed, gate=human_access)
        return vault21.move_to_removed(project_id, section_id, file_id, req.ceremony_token, req.reason)
    except (VaultError, ProtectedActionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v21/projects/{project_id}/sections/{section_id}/files/{file_id}/quarantine")
def quarantine(project_id: str, section_id: str, file_id: str, req: ProtectedMoveRequest):
    try:
        require_protected_action("quarantine", req.actor_kind, human_ceremony_passed=req.human_ceremony_passed, gate=human_access)
        return vault21.quarantine_file(project_id, section_id, file_id, req.reason)
    except (VaultError, ProtectedActionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v21/projects/{project_id}/sections/{section_id}/files/{file_id}/restore")
def restore(project_id: str, section_id: str, file_id: str, req: RestoreRequest):
    try:
        return vault21.restore_file(project_id, section_id, file_id, req.target_state)
    except VaultError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v21/integrity")
def integrity():
    return vault21.verify_custody_integrity()


@app.get("/api/v21/blackbox")
def blackbox_report():
    return blackbox21.build_report()
