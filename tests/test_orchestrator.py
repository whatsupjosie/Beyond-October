"""
tests/test_orchestrator.py — Wave A Gate Tests
════════════════════════════════════════════════

Five tests that must all pass before candidate build is released:

  1. Boot succeeds with Architect off (no GGUF, no llama_cpp)
  2. Studio path returns text
  3. Architect path falls back to Studio gracefully when unavailable
  4. Circuit breaker opens after threshold failures and closes after cooldown
  5. Two-pass falls back to Studio-only when Architect unavailable

Run: python -m pytest tests/test_orchestrator.py -v

Rear View Foresight LLC — Feic Mo Chroí — 2026
"""
from __future__ import annotations

import asyncio
import time
import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────

def fresh_orchestrator(**kwargs):
    """Return a new LLMOrchestrator with env overrides applied."""
    import importlib
    import sys
    # Patch env before import so module-level constants pick up changes
    import os
    for k, v in kwargs.items():
        os.environ[k] = str(v)

    # Force reimport so constants re-read env
    for mod in list(sys.modules.keys()):
        if "llm_orchestrator" in mod:
            del sys.modules[mod]

    from modules.llm_orchestrator import LLMOrchestrator
    return LLMOrchestrator()


# ── Test 1: Boot with Architect off ──────────────────────────────────────────

def test_boot_architect_off():
    """
    LLMOrchestrator.startup() must complete without raising even when
    Architect is not configured and Ollama may not be running.
    """
    import os
    os.environ["PUBCAST_ARCHITECT_MODEL"] = ""

    from modules.llm_orchestrator import LLMOrchestrator
    orch = LLMOrchestrator()

    async def _run():
        await orch.startup()   # must not raise

    asyncio.run(_run())
    # Studio may be offline in CI — that's fine. We just need no exception.
    assert True


# ── Test 2: Studio path returns structure ────────────────────────────────────

def test_studio_result_shape(monkeypatch):
    """
    Studio path must return OrchestratorResult with correct fields.
    Mock the httpx call so test doesn't need Ollama running.
    """
    import httpx
    from modules.llm_orchestrator import LLMOrchestrator, ContextPacket

    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"message": {"content": "Hello, Sancho."}}

    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return MockResponse()
        async def post(self, *a, **kw): return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: MockClient())

    orch = LLMOrchestrator()
    orch._studio_ok = True

    ctx = ContextPacket(character_name="Sir Purfluous")

    async def _run():
        return await orch.generate("Greet the guest.", role="studio", context=ctx)

    result = asyncio.run(_run())

    assert result.text == "Hello, Sancho."
    assert result.role_used == "studio"
    assert result.mind_used == "studio"
    assert result.ok is True
    assert result.fallback_occurred is False


# ── Test 3: Architect unavailable → Studio fallback ──────────────────────────

def test_architect_fallback_to_studio(monkeypatch):
    """
    When Architect is unavailable, role='architect' must fall back to Studio
    silently and set fallback_occurred=True.
    """
    import httpx
    from modules.llm_orchestrator import LLMOrchestrator, ContextPacket
    import modules.llm_orchestrator as _mod

    # Force Architect unavailable
    monkeypatch.setattr(_mod, "_arch_available", False)
    monkeypatch.setattr(_mod, "_arch_llm", None)

    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"message": {"content": "Studio fallback text."}}

    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return MockResponse()
        async def post(self, *a, **kw): return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: MockClient())

    orch = LLMOrchestrator()
    orch._studio_ok = True

    async def _run():
        return await orch.generate("Plan something.", role="architect", context=ContextPacket())

    result = asyncio.run(_run())

    assert result.text == "Studio fallback text."
    assert result.fallback_occurred is True
    assert result.fallback_reason == "architect_unavailable"
    assert result.mind_used == "studio"


# ── Test 4: Circuit breaker opens and closes ──────────────────────────────────

def test_circuit_breaker():
    """
    After BREAKER_THRESHOLD failures, breaker opens.
    After cooldown, breaker closes automatically.
    """
    from modules.llm_orchestrator import CircuitBreaker

    breaker = CircuitBreaker("test", threshold=3, cooldown_s=0.1)

    assert not breaker.is_open

    breaker.record_failure()
    breaker.record_failure()
    assert not breaker.is_open   # not yet at threshold

    breaker.record_failure()
    assert breaker.is_open       # threshold hit

    # Wait for cooldown
    time.sleep(0.15)
    assert not breaker.is_open   # should auto-close

    # Success resets failures
    breaker.record_failure()
    breaker.record_success()
    assert breaker._failures == 0


# ── Test 5: Two-pass falls back to Studio-only ───────────────────────────────

def test_two_pass_studio_fallback(monkeypatch):
    """
    architect_then_studio with Architect unavailable must still return
    a valid Studio response with fallback_occurred=True.
    """
    import httpx
    from modules.llm_orchestrator import LLMOrchestrator, ContextPacket
    import modules.llm_orchestrator as _mod

    monkeypatch.setattr(_mod, "_arch_available", False)
    monkeypatch.setattr(_mod, "_arch_llm", None)

    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"message": {"content": "Studio-only two-pass."}}

    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return MockResponse()
        async def post(self, *a, **kw): return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: MockClient())

    orch = LLMOrchestrator()
    orch._studio_ok = True
    ctx = ContextPacket(character_name="Pete")

    async def _run():
        return await orch.generate(
            "What do you think of the lighting?",
            role="architect_then_studio",
            context=ctx,
        )

    result = asyncio.run(_run())

    assert result.text == "Studio-only two-pass."
    assert result.role_requested == "architect_then_studio"
    assert result.fallback_occurred is True
    assert result.architect_draft is None
    assert result.ok is True
