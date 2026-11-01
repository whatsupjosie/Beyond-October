from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from modules.pete_enhanced import PeteEnhanced
from modules.twin_engine_service import TwinEngineService


class BridgeStub:
    def __init__(self, connected: bool = False):
        self.is_connected = connected
        self.connect_calls = 0
        self.close_calls = 0

    def connect(self):
        self.connect_calls += 1
        self.is_connected = True
        return True

    def close(self):
        self.close_calls += 1
        self.is_connected = False

    def status(self):
        return "connected" if self.is_connected else "disconnected"

    def send_command(self, *_args, **_kwargs):
        return True


class HubStub:
    async def broadcast_system_event(self, _payload):
        return None


@pytest.mark.asyncio
async def test_twin_service_reuses_an_already_connected_shared_bridge():
    bridge = BridgeStub(connected=True)
    service = TwinEngineService(bridge=bridge)
    await service.startup()
    assert bridge.connect_calls == 0
    assert service.health()["bridge_connected"] is True
    await service.shutdown()
    assert bridge.close_calls == 1


@pytest.mark.asyncio
async def test_pete_enhanced_does_not_close_shared_bridge_when_not_owner(tmp_path: Path):
    bridge = BridgeStub(connected=True)
    pete = PeteEnhanced(HubStub(), bridge, {}, tmp_path, owns_bridge=False)
    await pete.shutdown_twin_engine_system()
    assert bridge.close_calls == 0


@pytest.mark.asyncio
async def test_pete_enhanced_standalone_still_closes_owned_bridge(tmp_path: Path):
    bridge = BridgeStub(connected=True)
    pete = PeteEnhanced(HubStub(), bridge, {}, tmp_path, owns_bridge=True)
    await pete.shutdown_twin_engine_system()
    assert bridge.close_calls == 1
