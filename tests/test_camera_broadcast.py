"""Camera changes reach the stage pages, whichever route made them.

Regressions covered:
- Only some camera routes broadcast `camera_switch`; cuts from /api/switcher/* and
  the director console's studio actions changed the backend and nothing on screen.
- The stage pages' default room "studio" made them open /ws/studio, which belongs
  to the studio desk protocol, so they received no Hub traffic at all.
"""
from __future__ import annotations

import asyncio
import threading

import pytest

from modules.camera_broadcast import CameraBroadcastBridge
from modules.cameras import create_default_cameras


class FakeHub:
    def __init__(self):
        self.events = []

    async def broadcast_system_event(self, event):
        self.events.append(event)


def program_events(hub):
    return [e["payload"]["source_id"] for e in hub.events if e["payload"]["target"] == "program"]


def test_every_program_and_preview_change_is_broadcast_once():
    async def run():
        cams, hub = create_default_cameras(), FakeHub()
        bridge = CameraBroadcastBridge(cams, hub)
        bridge.start()
        assert hub.camera_events_bridged is True
        cams.set_program_source("close_up")
        cams.set_program_source("close_up")          # idempotent: no event
        cams.set_preview_source("overhead")
        cams.set_program_source("no_such_camera")    # invalid: no event
        await asyncio.sleep(0)
        await bridge.stop()
        return hub

    hub = asyncio.run(run())
    assert [(e["type"], e["payload"]["target"], e["payload"]["source_id"]) for e in hub.events] == [
        ("camera_switch", "program", "close_up"), ("camera_switch", "preview", "overhead")]
    last = hub.events[-1]["payload"]
    assert last["program"] == "close_up" and last["preview"] == "overhead"
    assert hub.camera_events_bridged is False


def test_stopped_bridge_sends_nothing_and_restarts_cleanly():
    async def run():
        cams, hub = create_default_cameras(), FakeHub()
        bridge = CameraBroadcastBridge(cams, hub)
        bridge.start(); bridge.start()              # double start must not double-subscribe
        cams.set_program_source("close_up")
        await asyncio.sleep(0)
        await bridge.stop()
        cams.set_program_source("overhead")          # after stop: silent
        bridge.start()
        cams.set_program_source("medium_shot")
        await asyncio.sleep(0)
        await bridge.stop()
        return hub

    assert program_events(asyncio.run(run())) == ["close_up", "medium_shot"]


def test_change_from_a_worker_thread_is_delivered_on_the_loop():
    async def run():
        cams, hub = create_default_cameras(), FakeHub()
        bridge = CameraBroadcastBridge(cams, hub)
        bridge.start()
        worker = threading.Thread(target=cams.set_program_source, args=("overhead",))
        worker.start(); worker.join()
        for _ in range(50):
            if hub.events:
                break
            await asyncio.sleep(0.01)
        await bridge.stop()
        return hub

    assert program_events(asyncio.run(run())) == ["overhead"]


def test_a_failing_hub_never_rolls_back_camera_state():
    class BrokenHub(FakeHub):
        async def broadcast_system_event(self, event):
            raise RuntimeError("socket gone")

    async def run():
        cams = create_default_cameras()
        bridge = CameraBroadcastBridge(cams, BrokenHub())
        bridge.start()
        cams.set_program_source("close_up")
        await asyncio.sleep(0)
        await bridge.stop()
        return cams.get_program_source().source_id

    assert asyncio.run(run()) == "close_up"


# ── through the real app ───────────────────────────────────────────────────

def _drain_until_camera(ws, limit=40):
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == "camera_switch" and msg["payload"]["target"] == "program":
            return msg["payload"]["source_id"]
    raise AssertionError("no camera_switch received")


@pytest.mark.parametrize("cut", [
    lambda c: c.post("/api/switcher/cut/overhead"),
    lambda c: (c.post("/api/switcher/preview/overhead"), c.post("/api/switcher/cut"))[-1],
    lambda c: c.post("/api/cameras/program/overhead"),
    lambda c: c.post("/api/cameras/switch", json={"target": "program", "source_id": "overhead"}),
    lambda c: c.post("/api/studio/actions/camera.switch.program", json={"source_id": "overhead"}),
], ids=["switcher-cut-camera", "switcher-preview-then-cut", "cameras-program", "cameras-switch", "studio-action"])
def test_stage_room_socket_receives_each_kind_of_cut(client, cut):
    client.post("/api/cameras/program/wide_shot")
    with client.websocket_connect("/ws/room/studio") as ws:
        response = cut(client)
        assert response.status_code < 400, response.text
        assert _drain_until_camera(ws) == "overhead"


def test_ws_studio_still_belongs_to_the_studio_desk(client):
    with client.websocket_connect("/ws/studio") as ws:
        first = ws.receive_json()
    assert first.get("type") in {"initial_state", "error"}   # studio desk protocol, not a Hub room


def test_stage_pages_use_the_room_safe_socket_path():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for page, var in (("stage_panoramic.html", "ROOM"), ("stage.html", "ROOM"),
                      ("stage_3d.html", "ROOM"), ("avatar_controls.html", "room")):
        text = (root / "static" / page).read_text(encoding="utf-8")
        assert f"websocketURL(`/ws/room/${{encodeURIComponent({var})}}`)" in text, page
        assert f"websocketURL(`/ws/${{{var}}}`)" not in text, page
