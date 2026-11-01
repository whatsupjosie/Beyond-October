from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional
from pydantic import BaseModel

class SwitcherState(BaseModel):
    program_camera: str = "wide_shot"
    preview_camera: Optional[str] = None
    transition_type: str = "cut"
    last_switch_timestamp: float = 0.0
    manual_override: bool = False

class DirectorDecision(BaseModel):
    action: str
    target_camera: Optional[str] = None
    target_screen: Optional[str] = None
    reason: str

@dataclass
class _SpeakerActivity:
    active_since: Optional[float] = None
    inactive_since: Optional[float] = None
    latched: bool = False

class AutonomousDirector:
    """Small deterministic director state machine.

    It owns *decisions*, never camera authority.  CameraManager remains the
    authoritative Program/Preview state owner and the switcher applies decisions.
    """
    def __init__(self, *, min_hold_duration_sec: float=2.5,
                 silence_threshold_sec: float=4.0,
                 activate_debounce_sec: float=0.4,
                 release_debounce_sec: float=0.4,
                 threshold_active_db: float=-24.0,
                 clock: Callable[[],float]=time.monotonic):
        self.min_hold_duration_sec=float(min_hold_duration_sec)
        self.silence_threshold_sec=float(silence_threshold_sec)
        self.activate_debounce_sec=float(activate_debounce_sec)
        self.release_debounce_sec=float(release_debounce_sec)
        self.threshold_active_db=float(threshold_active_db)
        self.clock=clock
        now=self.clock()
        self.state=SwitcherState(last_switch_timestamp=now)
        self._activity={k:_SpeakerActivity() for k in ("anchor_a","anchor_b","guest")}
        self._all_silent_since: Optional[float]=None
        self.camera_for={"anchor_a":"medium_shot","anchor_b":"close_up","guest":"cam_guest_monitor"}
        self.wide_camera="wide_shot"

    def sync_from_camera_manager(self, cameras) -> None:
        p=cameras.get_program_source(); v=cameras.get_preview_source()
        if p: self.state.program_camera=p.source_id
        self.state.preview_camera=v.source_id if v else None

    def manual_cut(self, new_camera:str, *, now:Optional[float]=None) -> dict:
        t=self.clock() if now is None else now
        self.state.program_camera=new_camera; self.state.last_switch_timestamp=t; self.state.transition_type="cut"
        return {"event":"broadcast_tally_change","active_camera_id":new_camera,"transition_type":"cut","timestamp":t}

    def _update(self, name:str, db:float, now:float) -> bool:
        s=self._activity[name]; raw=db > self.threshold_active_db
        if raw:
            s.inactive_since=None
            if s.active_since is None: s.active_since=now
            if not s.latched and now-s.active_since >= self.activate_debounce_sec: s.latched=True
        else:
            s.active_since=None
            if s.inactive_since is None: s.inactive_since=now
            if s.latched and now-s.inactive_since >= self.release_debounce_sec: s.latched=False
        return s.latched

    def evaluate(self, anchor_a_energy_db:float, anchor_b_energy_db:float,
                 guest_energy_db:float, current_time:Optional[float]=None) -> DirectorDecision:
        now=self.clock() if current_time is None else float(current_time)
        if self.state.manual_override: return DirectorDecision(action="HOLD",reason="Manual override active")
        active={
            "anchor_a":self._update("anchor_a",anchor_a_energy_db,now),
            "anchor_b":self._update("anchor_b",anchor_b_energy_db,now),
            "guest":self._update("guest",guest_energy_db,now),
        }
        names=[k for k,v in active.items() if v]
        if names: self._all_silent_since=None
        elif self._all_silent_since is None: self._all_silent_since=now
        if now-self.state.last_switch_timestamp < self.min_hold_duration_sec:
            return DirectorDecision(action="HOLD",reason="Minimum hold duration not met")
        if len(names)>1:
            if self.state.program_camera != self.wide_camera:
                return DirectorDecision(action="CUT",target_camera=self.wide_camera,reason="Overlapping sustained speakers")
            return DirectorDecision(action="HOLD",reason="Holding wide on overlapping speech")
        if len(names)==1:
            target=self.camera_for[names[0]]
            if target != self.state.program_camera:
                return DirectorDecision(action="CUT",target_camera=target,reason=f"Sustained speaker: {names[0]}")
            return DirectorDecision(action="HOLD",reason=f"Holding sustained speaker: {names[0]}")
        if self._all_silent_since is not None and now-self._all_silent_since >= self.silence_threshold_sec:
            if self.state.program_camera != self.wide_camera:
                return DirectorDecision(action="CUT",target_camera=self.wide_camera,reason="Sustained silence; return wide")
        return DirectorDecision(action="HOLD",reason="Conversation state stable")
