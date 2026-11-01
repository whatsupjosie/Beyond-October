"""Regression tests for the recovered E-Pete worker/deadline protections."""
import asyncio
from types import SimpleNamespace

import pytest

from modules.evo.epete import EPete, InferenceModel, InferenceTask, TaskType
from modules.evo.evo_integration import EVOOrchestrator


def _task():
    return InferenceTask("deadline-probe", TaskType.CONVERSATION, "Local test.", force_model=InferenceModel.STUDIO)


@pytest.mark.asyncio
async def test_start_is_idempotent_and_stop_allows_one_new_worker():
    engine = EPete()
    await engine.start()
    original = engine._worker_task
    try:
        await engine.start()
        assert engine._worker_task is original
    finally:
        await engine.stop()
    assert original.done()
    await engine.start()
    replacement = engine._worker_task
    try:
        assert replacement is not original
        assert not replacement.done()
    finally:
        await engine.stop()
    assert replacement.done()


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["studio", "architect"])
@pytest.mark.parametrize("method", ["generate", "chat"])
async def test_deadline_cancels_stalled_backend_call(model, method):
    cancelled = asyncio.Event()
    async def stalled(**_kwargs):
        try:
            await asyncio.Future()
        finally:
            cancelled.set()
    backend = SimpleNamespace(**{method: stalled})
    engine = EPete(llm_backend=backend, studio_timeout_s=0.01, architect_timeout_s=0.02)
    model_id = engine.studio_model_id if model == "studio" else engine.architect_model_id
    expected = "0.01s" if model == "studio" else "0.02s"
    with pytest.raises(RuntimeError, match=f"LLM timeout after {expected}"):
        await asyncio.wait_for(engine._execute_model(_task(), model_id), timeout=1)
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_timed_out_execute_returns_failure_and_releases_inference_slot():
    class Backend:
        calls = 0
        async def generate(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                await asyncio.Future()
            return "recovered"
    engine = EPete(llm_backend=Backend(), studio_timeout_s=0.01)
    result = await asyncio.wait_for(engine.execute(_task()), timeout=1)
    assert result.success is False
    assert "LLM timeout" in result.error
    assert result.output == ""
    next_result = await asyncio.wait_for(engine.execute(_task()), timeout=1)
    assert next_result.success is True
    assert next_result.output == "recovered"
    assert engine._failures == 1


@pytest.mark.asyncio
async def test_external_cancellation_is_not_converted_to_a_normal_failure():
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    async def stalled(**_kwargs):
        entered.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()
    engine = EPete(llm_backend=SimpleNamespace(generate=stalled))
    running = asyncio.create_task(engine.execute(_task()))
    await asyncio.wait_for(entered.wait(), timeout=1)
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running
    assert cancelled.is_set()
    assert not engine._inference_semaphore.locked()


@pytest.mark.asyncio
async def test_chat_backend_output_and_model_configuration_are_preserved():
    calls = []
    async def chat(**kwargs):
        calls.append(kwargs)
        return {"message": {"content": "local response"}}
    engine = EPete(studio_model_id="custom-local-model", llm_backend=SimpleNamespace(chat=chat))
    result = await engine.execute(_task())
    assert result.success
    assert result.output == "local response"
    assert calls[0]["model"] == "custom-local-model"


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
@pytest.mark.parametrize("parameter", ["studio_timeout_s", "architect_timeout_s"])
def test_deadlines_must_be_positive_and_finite(value, parameter):
    with pytest.raises(ValueError, match="finite and positive"):
        EPete(**{parameter: value})


def test_orchestrator_exposes_deadline_configuration_without_changing_defaults():
    engine = EVOOrchestrator(studio_timeout_s=90, architect_timeout_s=240).epete
    assert engine._studio_timeout_s == 90
    assert engine._architect_timeout_s == 240
    default = EPete()
    assert default._studio_timeout_s == 180
    assert default._architect_timeout_s == 180
