"""General Chat / Conversation Ownership HTTP routes.

This router owns conversation transcripts and portable exports. It deliberately
owns neither 2i manuscript state nor PubPartner/System Alex memory.
"""
from __future__ import annotations

import re
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .character_service import CharacterTranscriptStore
from .conversation_archive import ConversationArchive
from .general_chat_service import GeneralChatProviderError, run_general_chat_turn
from .package_service import PackageService
from .route_security import current_identity


class ConversationCreate(BaseModel):
    title: str = Field(default="Untitled", max_length=200)
    discussion_type: str = Field(default="chat", pattern=r"^(chat|build|project)$")
    project_id: Optional[str] = Field(default=None, max_length=200)
    build_id: Optional[str] = Field(default=None, max_length=200)


class GeneralChatTurnRequest(BaseModel):
    exact_text: str
    profile: Optional[str] = Field(default=None, max_length=200)
    options: dict[str, Any] = Field(default_factory=dict)


class MessageAppend(BaseModel):
    speaker: str = Field(min_length=1, max_length=120)
    exact_text: str
    parent_message_id: Optional[str] = None
    character_id: Optional[str] = Field(default=None, max_length=200)
    model: Optional[str] = Field(default=None, max_length=200)
    provider: Optional[str] = Field(default=None, max_length=200)
    room: Optional[str] = Field(default="general-chat", max_length=200)
    program: Optional[str] = Field(default="general-chat", max_length=200)
    build_id: Optional[str] = Field(default=None, max_length=200)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,160}$")


def _id(value: str, label: str = "id") -> str:
    if not _SAFE_ID.fullmatch(value or ""):
        raise HTTPException(400, f"invalid {label}")
    return value


def create_conversation_router(data_dir: Path) -> APIRouter:
    root = Path(data_dir) / "conversation_archive"
    archive = ConversationArchive(root / "conversations.sqlite3")
    packager = PackageService(archive)
    export_root = Path(data_dir) / "exports" / "conversation_ownership"
    export_root.mkdir(parents=True, exist_ok=True)

    router = APIRouter(prefix="/api/conversations", tags=["conversation-ownership"])

    @router.get("/config")
    async def config(identity=Depends(current_identity)):
        return {
            "ok": True,
            "user_id": identity["user_id"],
            "authority": "conversation-archive",
            "program": "general-chat",
            "manuscript_authority": False,
            "exports": ["txt", "md", "json", "jsonl", "html", "zip"],
        }

    @router.post("")
    async def create(body: ConversationCreate, identity=Depends(current_identity)):
        conversation_id = archive.create_conversation(
            title=body.title,
            discussion_type=body.discussion_type,
            project_id=body.project_id,
            build_id=body.build_id,
            metadata={"owner": identity["user_id"]},
        )
        return {"ok": True, "conversation_id": conversation_id}

    @router.get("")
    async def list_all(identity=Depends(current_identity)):
        owner = identity["user_id"]
        return {"ok": True, "conversations": archive.list_conversations_for_owner(owner)}

    @router.get("/search")
    async def search(q: str, limit: int = 50, identity=Depends(current_identity)):
        try:
            results = archive.search_for_owner(q, identity["user_id"], limit=limit)
        except sqlite3.OperationalError as exc:
            # SQLite FTS5 rejects malformed user queries; these are client
            # validation errors, not application failures.
            raise HTTPException(400, "invalid search expression") from exc
        return {"ok": True, "results": results}

    def owned_conversation_ids(owner: str) -> list[str]:
        return [row["conversation_id"] for row in archive.list_conversations_for_owner(owner)]

    def _private_character_export(owner: str) -> dict[str, bytes]:
        store = CharacterTranscriptStore(data_dir)
        records = store.owner_export(owner)
        return {'PrivateCharacters/transcripts.json':
                (json.dumps(records, ensure_ascii=False, indent=2) + '\n').encode('utf-8')}

    @router.post("/exports/all/raw")
    async def export_all_raw(identity=Depends(current_identity)):
        owner = identity["user_id"]
        ids = owned_conversation_ids(owner)
        result = packager.save_library_raw(ids, export_root / "Library", owner_id=owner,
                                           extra_files=_private_character_export(owner))
        return {
            "ok": True,
            "format": "raw",
            "conversation_count": result["conversation_count"],
            "verified": result["verified"],
            "export_name": result["root"].name,
        }

    @router.post("/exports/all/zip")
    async def export_all_zip(identity=Depends(current_identity)):
        owner = identity["user_id"]
        ids = owned_conversation_ids(owner)
        result = packager.save_library_zip(ids, export_root, owner_id=owner,
                                           extra_files=_private_character_export(owner))
        path = result["zip"]
        return FileResponse(
            path,
            filename=path.name,
            media_type="application/zip",
            headers={"X-PubCast-SHA256": result["sha256"]},
        )

    @router.get("/{conversation_id}")
    async def get_one(conversation_id: str, identity=Depends(current_identity)):
        conversation_id = _id(conversation_id, "conversation id")
        try:
            conversation = archive.get_conversation(conversation_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        if conversation.get("metadata", {}).get("owner") != identity["user_id"]:
            raise HTTPException(404, "conversation not found")
        return {"ok": True, "conversation": conversation}

    @router.post("/{conversation_id}/turns")
    async def turn(conversation_id: str, body: GeneralChatTurnRequest, identity=Depends(current_identity)):
        conversation_id = _id(conversation_id, "conversation id")
        try:
            conversation = archive.get_conversation(conversation_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        if conversation.get("metadata", {}).get("owner") != identity["user_id"]:
            raise HTTPException(404, "conversation not found")
        try:
            result = await run_general_chat_turn(
                archive=archive,
                conversation_id=conversation_id,
                exact_user_text=body.exact_text,
                requested_profile=body.profile,
                options=body.options,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except GeneralChatProviderError as exc:
            # A provider outage must not trick the client into resubmitting text
            # that was already durably archived.
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": "provider_unavailable",
                    "detail": str(exc),
                    "user_saved": exc.user_message is not None,
                    "user_message": exc.user_message.__dict__ if exc.user_message else None,
                },
            )
        return {
            "ok": True,
            "user_message": result.user_message.__dict__,
            "assistant_message": result.assistant_message.__dict__,
            "profile": result.profile,
            "backend": result.backend,
            "model": result.model,
        }

    @router.post("/{conversation_id}/messages")
    async def append(conversation_id: str, body: MessageAppend, identity=Depends(current_identity)):
        conversation_id = _id(conversation_id, "conversation id")
        try:
            conversation = archive.get_conversation(conversation_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        if conversation.get("metadata", {}).get("owner") != identity["user_id"]:
            raise HTTPException(404, "conversation not found")
        try:
            saved = archive.append_message(
                conversation_id,
                speaker=body.speaker,
                exact_text=body.exact_text,
                parent_message_id=body.parent_message_id,
                character_id=body.character_id,
                model=body.model,
                provider=body.provider,
                room=body.room,
                program=body.program,
                build_id=body.build_id,
                attachments=body.attachments,
                metadata=body.metadata,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"ok": True, "message": saved.__dict__}

    @router.post("/{conversation_id}/exports/{format_name}")
    async def export(conversation_id: str, format_name: str, identity=Depends(current_identity)):
        conversation_id = _id(conversation_id, "conversation id")
        try:
            conversation = archive.get_conversation(conversation_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        if conversation.get("metadata", {}).get("owner") != identity["user_id"]:
            raise HTTPException(404, "conversation not found")

        if format_name == "zip":
            result = packager.save_conversation_zip(conversation_id, export_root)
            path = result["zip"]
        elif format_name in {"txt", "md", "json", "jsonl", "html"}:
            paths = archive.export_documents(conversation_id, export_root / "Files")
            path = paths[format_name]
        else:
            raise HTTPException(400, "unsupported export format")
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")

    # Expose service handles for focused tests/integration without making them global authorities.
    router.archive = archive  # type: ignore[attr-defined]
    router.packager = packager  # type: ignore[attr-defined]
    return router


__all__ = ["create_conversation_router"]
