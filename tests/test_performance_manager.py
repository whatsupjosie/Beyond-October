# PubCast AI — test_performance_manager.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from modules.performance_manager import PerformanceManager, init_performance_manager


def test_profile_switch(monkeypatch):
    monkeypatch.setattr(PerformanceManager, "_save_state", lambda self: None)
    mgr = PerformanceManager(
        policy_path=Path("system_policy.json"),
        state_path=Path("data") / "global" / "performance_profile.test.json",
    )
    assert mgr.active_profile in {"medium", "low", "high"}
    snapshot = mgr.set_profile("low")
    assert snapshot["profile"] == "low"
    assert mgr.get("architect_enabled", True) is False


def test_orchestrator_honors_low_profile_architect_disable(monkeypatch):
    monkeypatch.setattr(PerformanceManager, "_save_state", lambda self: None)
    mgr = init_performance_manager(
        data_dir=Path("data"),
        policy_path=Path("system_policy.json"),
    )
    mgr.active_profile = "low"

    from modules.llm_orchestrator import ContextPacket, LLMOrchestrator

    class MockResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "Studio response from low profile."}}

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return MockResponse()

        async def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())

    orch = LLMOrchestrator()
    orch._studio_ok = True

    async def _run():
        return await orch.generate(
            "Plan this response.",
            role="architect",
            context=ContextPacket(character_name="Pete"),
        )

    result = asyncio.run(_run())
    assert result.mind_used == "studio"
    assert result.fallback_occurred is True
    assert result.fallback_reason == "profile_architect_disabled"
