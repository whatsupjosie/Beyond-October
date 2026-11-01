from __future__ import annotations

import asyncio
import io
import json
import zipfile
from pathlib import Path

import pytest

from modules.cameras import CameraManager, CameraSource, CameraTransport, CameraSwitchEvent
from modules.twin_engine_service import TwinEngineService
from modules.director_engine import AutonomousDirector
from modules.eq_monitoring_recorder import EQMonitoringRecorder
from modules.performance.avatar_adapter import AvatarPerformanceAdapter
from modules.pubworld_stage.manifest_store import ManifestStore, SceneManifest, CameraSetup
from modules.pubworld_stage.perspective_solver import Line2D, PerspectiveSolver
from modules.pubworld_stage.stage_service import StageService


def camera(cid, transport=CameraTransport.VIRTUAL):
    return CameraSource(source_id=cid,name=cid,location="test",description="",transport=transport,endpoint=f"test://{cid}")


def test_camera_authority_events_take_and_idempotence():
    m=CameraManager(); m.register(camera("a")); m.register(camera("b"))
    events=[]; m.subscribe(events.append)
    assert m.set_program_source("a")
    assert m.set_program_source("a") # idempotent: no second event
    assert m.set_preview_source("b")
    assert len([e for e in events if isinstance(e,CameraSwitchEvent)]) == 2
    assert m.take()
    assert m.get_program_source().source_id == "b"
    assert m.get_preview_source().source_id == "a"
    assert len(events) == 4


class Bridge:
    def __init__(self): self.is_connected=True; self.commands=[]
    def status(self): return "connected"
    def send_command(self, cmd, payload): self.commands.append((cmd,payload)); return True
    def close(self): self.is_connected=False


@pytest.mark.asyncio
async def test_full_host_twin_uses_canonical_voxel_camera():
    m=CameraManager(); m.register(camera("vox",CameraTransport.VOXEL_3D)); m.register(camera("physical",CameraTransport.NDI))
    b=Bridge(); service=TwinEngineService(bridge=b,camera_manager=m)
    await service.startup()
    await service.activate_camera("vox")
    await asyncio.sleep(0)
    assert m.get_program_source().source_id == "vox"
    assert any(c[0]=="SWITCH_PROGRAM" and c[1]["input"]=="vox" for c in b.commands)
    b.commands.clear()
    await service.activate_camera("physical")
    await asyncio.sleep(0)
    assert not b.commands, "physical camera must not be mislabeled as voxel renderer input"
    await service.shutdown()


def test_perspective_keeps_off_frame_horizon():
    # Two line pairs with a horizon above frame; result must not be clamped to [0,1].
    r=PerspectiveSolver.solve(Line2D(p1=(0,100),p2=(400,0)),Line2D(p1=(0,200),p2=(800,0)),
                              Line2D(p1=(1000,0),p2=(600,100)),Line2D(p1=(1000,-100),p2=(200,100)),
                              800,600)
    assert r.horizon_y_ratio < 1.0 or r.horizon_y_ratio > 0.0
    assert r.focal_length_px > 0


def test_manifest_zip_slip_and_stage_runtime(tmp_path:Path):
    store=ManifestStore(tmp_path)
    manifest=SceneManifest(scene_id="studio",title="Studio",background_image="plate.png",camera_setup=CameraSetup())
    store.save(manifest); assert store.list_scenes()==["studio"]
    stage=StageService(store); events=[]; tok=stage.subscribe(events.append)
    stage.load_scene("studio"); stage.upsert_actor("a","sheila",position=[1,2,3]); assert stage.state()["actors"]["a"]["position"]==[1.0,2.0,3.0]
    assert stage.unsubscribe(tok)
    bad=io.BytesIO()
    with zipfile.ZipFile(bad,"w") as z: z.writestr("../escape.txt","no")
    with pytest.raises(ValueError): store.import_bundle("studio",bad.getvalue())
    assert not (tmp_path.parent/"escape.txt").exists()


def test_director_debounce_is_deterministic():
    clock=[0.0]
    d=AutonomousDirector(min_hold_duration_sec=0.0,activate_debounce_sec=0.4,release_debounce_sec=0.4,clock=lambda:clock[0])
    d.state.program_camera="wide_shot"
    assert d.evaluate(-10,-80,-80).action=="HOLD"
    clock[0]=0.41
    decision=d.evaluate(-10,-80,-80)
    assert decision.action=="CUT" and decision.target_camera=="medium_shot"


def test_eq_recorder_exact_text_and_separate_affect(tmp_path:Path):
    rec=EQMonitoringRecorder(tmp_path,build_id="test")
    text="Fuck,  exact  spacing — stays."
    rec.record_message({"room":"main","message_id":"m1","user_id":"u","text":text,"t":1.25})
    rec.record_affect("main",user_id="u",message_id="m1",text=text,baseline_before={"n":1},evaluation={"reading":{"state":"steady"}},baseline_after={"n":2})
    t=(tmp_path/"blackbox/dev/EQ/sessions/main/transcript.jsonl").read_text()
    a=(tmp_path/"blackbox/dev/EQ/sessions/main/affect_trace.jsonl").read_text()
    assert json.loads(t)["text"]==text
    assert json.loads(a)["baseline_before"]=={"n":1}


def test_avatar_adapter_capture_is_avatar_independent():
    a=AvatarPerformanceAdapter()
    pkt=a.normalize({"source":"mediapipe","landmarks":[{"x":0,"y":0,"z":0,"visibility":1} for _ in range(33)]},avatar_id="lumen")
    assert pkt.avatar_id=="lumen" and pkt.joints["head"]["y"]==pytest.approx(1.35)
    assert "hips" in pkt.joints

from modules.rust_camera_runtime import RustCameraRuntime

def test_rust_camera_runtime_adds_two_slots_without_changing_program_preview():
    m=CameraManager(); m.register(camera("existing")); m.set_program_source("existing")
    runtime=RustCameraRuntime(m,enabled=False)
    assert m.get_program_source().source_id=="existing"
    assert m.get_preview_source() is None
    voxel=[c for c in m.list_sources() if c.transport==CameraTransport.VOXEL_3D]
    assert len(voxel)>=2
    assert runtime.status()["frame_path_proven"] is False

def test_rust_camera_runtime_requires_token_when_enabled(monkeypatch):
    monkeypatch.delenv("PUBCAST_CAMERA_CONTROL_TOKEN",raising=False)
    m=CameraManager(); m.register(camera("existing"))
    with pytest.raises(RuntimeError): RustCameraRuntime(m,enabled=True,token="")
