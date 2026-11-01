from __future__ import annotations

import io
import struct
import time

import pytest

from modules.bridge_bulletproof import BridgeStatus, VoxelBridge, _HEADER_FMT
from modules.pubpartner_provider import PubPartnerProviderDispatcher


@pytest.mark.asyncio
async def test_pubpartner_ollama_status_reuses_canonical_adapter(monkeypatch):
    import modules.llm_framework as framework

    class FakeOllamaAdapter:
        def __init__(self, host: str = "http://default-ollama:11434") -> None:
            self.host = host.rstrip("/")

        async def ping(self) -> bool:
            return True

        async def list_local_models(self):
            return ["gemma3:4b", "ministral:3b"]

    monkeypatch.setattr(framework, "OllamaBotAdapter", FakeOllamaAdapter)
    monkeypatch.setitem(
        framework.PROVIDER_REGISTRY,
        "ollama",
        FakeOllamaAdapter("http://registry-ollama:11434"),
    )

    status = await PubPartnerProviderDispatcher().status(
        "ollama",
        {
            "host": "http://custom-ollama:11434/",
            "model": "gemma3:4b",
        },
    )

    assert status["ok"] is True
    assert status["alive"] is True
    assert status["available"] is True
    assert status["host"] == "http://custom-ollama:11434"
    assert status["models"] == ["gemma3:4b", "ministral:3b"]
    assert status["selected_model"] == "gemma3:4b"
    assert status["model_available"] is True
    assert status["error"] is None


@pytest.mark.asyncio
async def test_pubpartner_ollama_status_reports_unreachable_without_type_error(monkeypatch):
    import modules.llm_framework as framework

    class DeadOllamaAdapter:
        def __init__(self, host: str = "http://dead:11434") -> None:
            self.host = host.rstrip("/")

        async def ping(self) -> bool:
            return False

        async def list_local_models(self):  # pragma: no cover - must not be called
            raise AssertionError("model discovery must not run when Ollama is down")

    monkeypatch.setattr(framework, "OllamaBotAdapter", DeadOllamaAdapter)
    monkeypatch.setitem(framework.PROVIDER_REGISTRY, "ollama", DeadOllamaAdapter())

    status = await PubPartnerProviderDispatcher().status(
        "ollama", {"model": "gemma3:4b"}
    )

    assert status["ok"] is True
    assert status["alive"] is False
    assert status["available"] is False
    assert status["models"] == []
    assert status["selected_model"] == "gemma3:4b"
    assert status["model_available"] is False
    assert "TypeError" not in str(status.get("error"))


def test_bridge_irm_does_not_turn_monitor_interval_into_fake_frame(tmp_path):
    bridge = VoxelBridge(tmp_path)
    assert bridge._irm_sensor.fps_history == []

    # The old implementation converted elapsed wall-clock time between health
    # checks into a frame sample (~0.1 FPS for a 10 second monitor loop).
    bridge._update_irm()

    assert bridge._irm_sensor.fps_history == []
    assert bridge._irm_actuator.emergency_mode is False
    assert bridge.get_metrics()["irm"]["emergency"] is False


@pytest.mark.asyncio
async def test_bridge_irm_records_real_shared_renderer_fps(tmp_path):
    bridge = VoxelBridge(tmp_path)
    bridge._status = BridgeStatus.CONNECTED

    # _update_performance_metrics reads fields[6]=fps and fields[7]=gpu_health.
    header = struct.pack(
        _HEADER_FMT,
        b"PCB2",
        2,
        0,
        0,
        0,
        0,
        30.0,
        88.0,
        0,
        0,
        time.time(),
    )
    bridge._shm_header = io.BytesIO(header)

    await bridge._update_performance_metrics()
    bridge._update_irm()

    health = bridge._irm_sensor.health()
    assert bridge.get_metrics()["fps"] == pytest.approx(30.0)
    assert health["fps"] == pytest.approx(30.0)
    # 30 FPS is genuine renderer telemetry and may legitimately cause the
    # adaptive bridge to back off; it is no longer derived from scheduler time.
    assert health["is_stable"] is False


def test_reach_node_test_dependency_authority_declares_jsdom():
    """The editor/phone DOM harnesses must have an installable dependency authority."""
    import json
    from pathlib import Path

    package = json.loads((Path(__file__).resolve().parents[1] / "package.json").read_text(encoding="utf-8"))
    assert package.get("private") is True
    # 22.1.0 was the original pin, but tests/test_reach_editor.cjs asserts a computed
    # custom-property font size that jsdom 22.1.0 reports as '' (verified 2026-10-25);
    # 26.1.0 passes it and every other Node harness. Exact pin kept on purpose.
    assert package.get("devDependencies", {}).get("jsdom") == "26.1.0"
