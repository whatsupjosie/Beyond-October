# PubCast AI — test_choreo_controller.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
from __future__ import annotations

import asyncio

from modules.choreography_controller import AvatarSim, ChoreoController


class _FakeHub:
    def __init__(self) -> None:
        self.events = []

    async def broadcast_system_event(self, event):
        self.events.append(event)


def test_cue_action_emits_event():
    hub = _FakeHub()
    controller = ChoreoController(hub, tick_hz=20)

    async def _run():
        payload = await controller.cue_action(
            room="studio",
            avatar_id="pete",
            action="walk",
            intensity=1.2,
            duration=1.8,
        )
        return payload

    payload = asyncio.run(_run())
    assert payload["action"] == "walk"
    assert payload["avatar_id"] == "pete"
    assert hub.events
    assert hub.events[-1]["type"] == "avatar_action_cue"


def test_unknown_action_rejected():
    hub = _FakeHub()
    controller = ChoreoController(hub)

    async def _run():
        try:
            await controller.cue_action(room="studio", avatar_id="pete", action="moonwalk_rocket")
        except ValueError as exc:
            return str(exc)
        return ""

    err = asyncio.run(_run())
    assert "Unknown action" in err


def test_motion_constraints_bound_position():
    hub = _FakeHub()
    controller = ChoreoController(hub)
    avatar = AvatarSim(id="pete", position=[0.0, 0.0, 0.0], rotation=[0.0, 0.0, 0.0])
    controller._avatars = [avatar]
    previous = {"pete": {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}}
    avatar.position = [9.0, 9.0, 9.0]
    avatar.rotation = [0.0, 720.0, 0.0]

    controller._apply_constraints(previous, dt=0.1)

    c = controller.get_constraints()
    assert c["x_min"] <= avatar.position[0] <= c["x_max"]
    assert c["y_min"] <= avatar.position[1] <= c["y_max"]
    assert c["z_min"] <= avatar.position[2] <= c["z_max"]
    assert abs(avatar.rotation[1]) <= c["max_turn_rate_deg"] * 0.1 + 1e-6


def test_constraints_can_be_disabled():
    hub = _FakeHub()
    controller = ChoreoController(hub)
    controller.set_constraints({"enabled": False})
    avatar = AvatarSim(id="pete", position=[0.0, 0.0, 0.0], rotation=[0.0, 0.0, 0.0])
    controller._avatars = [avatar]
    previous = {"pete": {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}}
    avatar.position = [9.0, 9.0, 9.0]
    avatar.rotation = [0.0, 720.0, 0.0]

    controller._apply_constraints(previous, dt=0.1)

    assert avatar.position == [9.0, 9.0, 9.0]
    assert avatar.rotation == [0.0, 720.0, 0.0]

