"""New PubPartner cartridges, made from PubPartner and kept on the Reach host.

A cartridge is the portable character format in ``pubpartner/cartridge.py``: a folder with ``character.yaml``,
``voice_profile.yaml``, ``appearance.yaml`` and ``memories.jsonl``. ``init_cartridge`` writes it, and ``load_cartridge``
reads it back, so every new cartridge is proved loadable before it is announced. Each one is also registered as a
PubPartner friend profile with the same id, so it shows in the Friend list and can be talked to straight away.

    data/pubpartner/cartridges/<id>/        the cartridge (portable: copy the folder, or zip it)
    data/pubpartner/profiles/friends/<id>.json   its friend profile, which notes the cartridge and its avatar

An avatar from the avatar library (``modules/avatar_imports.py``) can be given to a cartridge. It is recorded in both
the friend profile and ``appearance.yaml`` (``avatar_id``), and the Bella Faux Pas Studio can wear the same avatar.

The built-in friends (alex, craig, friend) cannot be created or overwritten here. In particular the canonical Alex
vessel (``data/pubpartner/vessels/alex.pubpartner``) is never read or written by this module.
"""
from __future__ import annotations

import re
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request

from pubpartner.cartridge import CartridgeValidationError, init_cartridge, load_cartridge

from .avatar_imports import AvatarImportStore
from .pubpartner_profiles import DEFAULT_FRIENDS, PubPartnerProfileStore
from .route_security import current_identity, require_role

RESERVED = frozenset(DEFAULT_FRIENDS) | {"default", "new", "none"}
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,47}$")
LIMITS = {"name": 80, "summary": 480, "cadence": 200, "vocabulary": 200}


def slug_for(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:48].strip("_")
    return s


def _text(body: Dict[str, Any], key: str, *, required: bool) -> str:
    v = body.get(key, "")
    if not isinstance(v, str):
        raise HTTPException(400, f"{key} must be text")
    v = v.strip()
    if required and not v:
        raise HTTPException(400, f"{key} is required")
    if len(v) > LIMITS[key]:
        raise HTTPException(400, f"{key} must be at most {LIMITS[key]} characters")
    return v


def _owner(identity: Dict[str, Any]) -> str:
    return str(identity.get("user_id") or identity.get("sub") or "local")


class CartridgeStudio:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.root = self.data_dir / "pubpartner" / "cartridges"
        self.profiles = PubPartnerProfileStore(self.data_dir)
        self.avatars = AvatarImportStore(self.data_dir)
        self._lock = threading.Lock()

    def path_for(self, cartridge_id: str) -> Path:
        if not _ID.match(cartridge_id) or cartridge_id in RESERVED:
            raise HTTPException(404, "no such cartridge")
        return self.root / cartridge_id

    def describe(self, cartridge_id: str) -> Optional[Dict[str, Any]]:
        folder = self.root / cartridge_id
        if not (folder / "character.yaml").exists():
            return None
        try:
            character = yaml.safe_load((folder / "character.yaml").read_text(encoding="utf-8")) or {}
            voice = yaml.safe_load((folder / "voice_profile.yaml").read_text(encoding="utf-8")) or {}
            appearance_path = folder / "appearance.yaml"
            appearance = yaml.safe_load(appearance_path.read_text(encoding="utf-8")) if appearance_path.exists() else {}
        except (OSError, yaml.YAMLError):
            return {"id": cartridge_id, "error": "unreadable"}
        appearance = appearance or {}
        return {"id": cartridge_id, "friend_id": cartridge_id, "name": character.get("name"), "summary": character.get("summary"),
                "cadence": voice.get("cadence"), "vocabulary": voice.get("vocabulary"), "avatar_id": appearance.get("avatar_id"),
                "created_by": appearance.get("created_by") or None}

    def list(self) -> List[Dict[str, Any]]:
        if not self.root.exists():
            return []
        out = []
        for folder in sorted(self.root.iterdir()):
            if folder.is_dir() and _ID.match(folder.name) and folder.name not in RESERVED:
                d = self.describe(folder.name)
                if d:
                    out.append(d)
        return out

    def _check_avatar(self, avatar_id: Optional[str]) -> Optional[str]:
        if avatar_id in (None, ""):
            return None
        if not isinstance(avatar_id, str) or not self.avatars.get(avatar_id):
            raise HTTPException(400, "that avatar is not in the avatar library")
        return avatar_id

    def _write_appearance(self, folder: Path, **fields: Any) -> None:
        path = folder / "appearance.yaml"
        data = (yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None) or {"description": "", "details": []}
        data.update({k: v for k, v in fields.items()})
        if data.get("avatar_id") is None:
            data.pop("avatar_id", None)
        tmp = path.with_suffix(".yaml.tmp")
        tmp.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        tmp.replace(path)

    def _profile(self, cid: str, name: str, summary: str, cadence: str, vocabulary: str, avatar_id: Optional[str], owner: str) -> Dict[str, Any]:
        cad = [c for c in (cadence, ("vocabulary: " + vocabulary) if vocabulary else "") if c]
        profile = {"id": cid, "display_name": name, "role": ["ai_friend", "collaborator"], "tone": ["warm", "direct"],
                   "cadence": cad or ["plain"], "avoid": ["generic_assistant", "fake_memory"],
                   "boundaries": ["no_fake_done", "preserve_exact_text"], "self_concept": summary,
                   "memory_policy": {"use_memory_refs": True, "do_not_fake_memories": True},
                   "cartridge": {"id": cid, "format": "pubpartner-cartridge", "path": f"pubpartner/cartridges/{cid}", "created_by": owner}}
        if avatar_id:
            profile["avatar_id"] = avatar_id
        return profile

    def create(self, body: Dict[str, Any], owner: str) -> Dict[str, Any]:
        name = _text(body, "name", required=True)
        summary = _text(body, "summary", required=True)
        cadence = _text(body, "cadence", required=False) or "natural"
        vocabulary = _text(body, "vocabulary", required=False) or "everyday"
        cid = body.get("id") or slug_for(name)
        if not isinstance(cid, str) or not _ID.match(cid):
            raise HTTPException(400, "the cartridge needs a name made of letters or numbers")
        if cid in RESERVED:
            raise HTTPException(409, f"{cid} is a built-in friend and cannot be replaced")
        avatar_id = self._check_avatar(body.get("avatar_id"))
        with self._lock:
            folder = self.root / cid
            if folder.exists() or (self.profiles.friend_dir / f"{cid}.json").exists():
                raise HTTPException(409, f"a cartridge or friend called {cid} already exists")
            self.root.mkdir(parents=True, exist_ok=True)
            staging = self.root / f".{cid}.creating"
            shutil.rmtree(staging, ignore_errors=True)
            try:
                init_cartridge(staging, name=name, summary=summary, cadence=cadence, vocabulary=vocabulary)
                self._write_appearance(staging, avatar_id=avatar_id, created_by=owner)
                cartridge = load_cartridge(staging)            # proves the new cartridge loads before it exists
                cartridge.memory.close()
                staging.replace(folder)
            except CartridgeValidationError as exc:
                shutil.rmtree(staging, ignore_errors=True)
                raise HTTPException(400, f"the cartridge did not load: {exc}") from None
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise
            try:
                self.profiles.save_profile("friend", cid, self._profile(cid, name, summary, cadence, vocabulary, avatar_id, owner))
            except Exception:
                shutil.rmtree(folder, ignore_errors=True)          # no half-made cartridge left behind
                raise
        return self.describe(cid)

    def set_avatar(self, cid: str, avatar_id: Optional[str]) -> Dict[str, Any]:
        folder = self.path_for(cid)
        if not folder.exists():
            raise HTTPException(404, "no such cartridge")
        avatar_id = self._check_avatar(avatar_id)
        with self._lock:
            self._write_appearance(folder, avatar_id=avatar_id)
            profile = self.profiles.load_profile("friend", cid, fallback_id=cid)
            profile.pop("avatar_id", None)
            if avatar_id:
                profile["avatar_id"] = avatar_id
            self.profiles.save_profile("friend", cid, profile)
        return self.describe(cid)


def create_pubpartner_cartridge_router(data_dir: Path) -> APIRouter:
    studio = CartridgeStudio(data_dir)
    router = APIRouter(prefix="/api/pubpartner/cartridges", tags=["pubpartner"])
    router.studio = studio  # type: ignore[attr-defined]

    async def _body(request: Request) -> Dict[str, Any]:
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "body must be JSON") from None
        if not isinstance(body, dict):
            raise HTTPException(400, "body must be an object")
        return body

    @router.get("")
    async def list_cartridges(identity: Dict[str, Any] = Depends(current_identity)):
        return {"ok": True, "cartridges": studio.list()}

    @router.post("", status_code=201)
    async def create_cartridge(request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        return {"ok": True, "cartridge": studio.create(await _body(request), _owner(identity))}

    @router.get("/{cartridge_id}")
    async def read_cartridge(cartridge_id: str, identity: Dict[str, Any] = Depends(current_identity)):
        studio.path_for(cartridge_id)
        d = studio.describe(cartridge_id)
        if not d:
            raise HTTPException(404, "no such cartridge")
        return {"ok": True, "cartridge": d}

    @router.put("/{cartridge_id}/avatar")
    async def set_cartridge_avatar(cartridge_id: str, request: Request, identity: Dict[str, Any] = Depends(require_role("mod"))):
        body = await _body(request)
        return {"ok": True, "cartridge": studio.set_avatar(cartridge_id, body.get("avatar_id"))}

    return router


__all__ = ["create_pubpartner_cartridge_router", "CartridgeStudio", "RESERVED", "slug_for"]
