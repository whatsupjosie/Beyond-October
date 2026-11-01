from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from .manifest_store import ManifestStore, SceneManifest

@dataclass
class ActorState:
    actor_id: str
    avatar_id: str
    position: list[float] = field(default_factory=lambda:[0.0,0.0,0.0])
    rotation_deg: list[float] = field(default_factory=lambda:[0.0,0.0,0.0])
    visible: bool = True
    updated_at: float = field(default_factory=time.time)

class StageService:
    """Authoritative mutable stage state; manifests remain portable authored state."""
    def __init__(self, store: ManifestStore):
        self.store = store
        self.scene: Optional[SceneManifest] = None
        self.actors: Dict[str, ActorState] = {}
        self.local_focus_screen: Optional[str] = None
        self.program_focus_screen: Optional[str] = None
        self.revision = 0
        self._subs: dict[int, Callable[[dict], Any]] = {}
        self._next_sub = 1

    def subscribe(self, callback: Callable[[dict], Any]) -> int:
        token=self._next_sub; self._next_sub += 1; self._subs[token]=callback; return token
    def unsubscribe(self, token: int) -> bool:
        return self._subs.pop(token, None) is not None
    def _emit(self, kind: str, payload: dict) -> None:
        self.revision += 1
        event={"type":kind,"revision":self.revision,"timestamp":time.time(),"payload":payload}
        for cb in list(self._subs.values()):
            try: cb(copy.deepcopy(event))
            except Exception: pass

    def load_scene(self, scene_id: str) -> SceneManifest:
        manifest=self.store.load(scene_id)
        if manifest is None: raise KeyError(scene_id)
        self.scene=manifest; self.actors.clear(); self.local_focus_screen=None; self.program_focus_screen=None
        self._emit("stage.scene_loaded", {"scene_id":scene_id})
        return manifest

    def save_scene(self) -> None:
        if self.scene is None: raise RuntimeError("no scene loaded")
        self.store.save(self.scene)

    def upsert_actor(self, actor_id: str, avatar_id: str, *, position=None, rotation_deg=None, visible=True) -> ActorState:
        actor=self.actors.get(actor_id) or ActorState(actor_id=actor_id, avatar_id=avatar_id)
        actor.avatar_id=avatar_id
        if position is not None: actor.position=[float(x) for x in position]
        if rotation_deg is not None: actor.rotation_deg=[float(x) for x in rotation_deg]
        actor.visible=bool(visible); actor.updated_at=time.time(); self.actors[actor_id]=actor
        self._emit("stage.actor", actor.__dict__.copy()); return actor

    def remove_actor(self, actor_id: str) -> bool:
        removed=self.actors.pop(actor_id,None)
        if removed: self._emit("stage.actor_removed", {"actor_id":actor_id})
        return removed is not None

    def focus_screen(self, screen_id: Optional[str], *, program: bool=False) -> None:
        if screen_id is not None:
            if self.scene is None or screen_id not in {s.screen_id for s in self.scene.interactive_screens}:
                raise KeyError(screen_id)
        if program: self.program_focus_screen=screen_id
        else: self.local_focus_screen=screen_id
        self._emit("stage.screen_focus", {"screen_id":screen_id,"program":program})

    def state(self) -> dict:
        return {"revision":self.revision,"scene":None if self.scene is None else self.scene.model_dump(by_alias=True),
                "actors":{k:v.__dict__.copy() for k,v in self.actors.items()},
                "local_focus_screen":self.local_focus_screen,"program_focus_screen":self.program_focus_screen}
