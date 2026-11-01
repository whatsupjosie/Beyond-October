from __future__ import annotations

import asyncio

import pytest

from modules.evo.distributed_engine import (
    DistributedEngineNode,
    EngineConfig,
    EngineMetrics,
    EngineRole,
)
from modules.evo.switchblade_governor import PriorityVector, SwitchbladeGovernor
from modules.irm import IRMController


def test_irm_explicit_batch_target_is_bounded():
    irm = IRMController(initial_batch_size=2500, min_batch_size=500, max_batch_size=10000)
    assert irm.get_batch_size() == 2500
    assert irm.set_batch_size(1) == 500
    assert irm.set_batch_size(999999) == 10000
    assert irm.set_batch_size(1700) == 1700


def test_evo_distributed_node_constructs_against_current_irm():
    node = DistributedEngineNode(
        EngineConfig(
            engine_id="round9-probe",
            min_batch_size=500,
            default_batch_size=2500,
            max_batch_size=10000,
        )
    )
    assert node.irm.get_batch_size() == 2500
    assert node.metrics.health_score == 100.0
    assert node.metrics.fps == 60.0


def test_switchblade_uses_public_irm_batch_api_without_faking_health_emergency():
    node = DistributedEngineNode(
        EngineConfig(
            engine_id="round9-switchblade",
            min_batch_size=500,
            default_batch_size=2500,
            max_batch_size=10000,
        )
    )
    vector = PriorityVector(
        voxel_batch_primary=1700,
        e4_assist=True,
        e3_tex_quality=0.42,
    )

    SwitchbladeGovernor().apply(vector, node)

    assert node.irm.get_batch_size() == 1700
    assert node.config.quality_level == 42
    assert not hasattr(node.irm.actuator, "emergency_mode")


@pytest.mark.asyncio
async def test_evo_health_loop_calls_current_zero_argument_irm_tick():
    node = DistributedEngineNode(
        EngineConfig(engine_id="round9-health", health_check_interval=0.0)
    )

    class FakeIRM:
        def __init__(self):
            self.calls = 0

        def tick(self):
            self.calls += 1
            node._running = False

    fake = FakeIRM()
    node.irm = fake
    node._running = True
    await node._health_check_loop()
    assert fake.calls == 1


def test_evo_heartbeat_accepts_bridge_raw_nested_metrics():
    node = DistributedEngineNode(EngineConfig(engine_id="primary"))

    from modules.bridge_raw import BridgeMessage, MessageType

    msg = BridgeMessage(
        type=MessageType.HEARTBEAT,
        sender_id="camera_3",
        payload={
            "metrics": {
                "engine_id": "camera_3",
                "health_score": 87.0,
                "processing_load": 31.0,
                "role": EngineRole.STANDBY.value,
            }
        },
    )
    node._handle_heartbeat(msg)

    assert "camera_3" in node._connected_nodes
    peer = node._connected_nodes["camera_3"]
    assert peer.health_score == 87.0
    assert peer.processing_load == 31.0

@pytest.mark.asyncio
async def test_evo_primary_and_camera_exchange_real_udp_heartbeat_and_typed_command():
    import socket
    from modules.bridge_raw import MessageType
    from modules.evo.distributed_engine import EngineMode

    def free_udp_port():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    primary_port = free_udp_port()
    camera_port = free_udp_port()
    primary = DistributedEngineNode(
        EngineConfig(
            engine_id="round9-primary",
            mode=EngineMode.TWIN,
            primary_host="127.0.0.1",
            primary_port=primary_port,
            listen_port=camera_port,
            heartbeat_interval=0.03,
            health_check_interval=0.03,
        )
    )
    camera = DistributedEngineNode(
        EngineConfig(
            engine_id="round9-camera",
            mode=EngineMode.CAMERA,
            primary_host="127.0.0.1",
            primary_port=primary_port,
            listen_port=camera_port,
            heartbeat_interval=0.03,
            health_check_interval=0.03,
        )
    )

    try:
        await primary.start()
        await camera.start()
        for _ in range(20):
            if "round9-camera" in primary._connected_nodes:
                break
            await asyncio.sleep(0.02)
        assert "round9-camera" in primary._connected_nodes

        assert primary.bridge is not None
        primary.bridge.send(
            MessageType.SET_ROLE,
            {"target": "round9-camera", "role": EngineRole.BACKUP_50.value},
        )
        for _ in range(20):
            if camera.role == EngineRole.BACKUP_50:
                break
            await asyncio.sleep(0.02)
        assert camera.role == EngineRole.BACKUP_50
    finally:
        await camera.stop()
        await primary.stop()
