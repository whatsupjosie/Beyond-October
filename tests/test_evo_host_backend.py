from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest

from modules.evo_host import EVOInferenceBackend
from modules.evo.epete import EPete, InferenceTask, InferenceModel, TaskType


@pytest.mark.asyncio
@pytest.mark.parametrize("alias,route", [("gemma-studio", "studio"), ("gemma-architect", "architect")])
async def test_adapter_uses_real_host_api_and_preserves_context(alias, route):
    manager = SimpleNamespace(generate_text=AsyncMock(return_value={"text": "  Exact response.\n", "error": ""}))
    backend = EVOInferenceBackend(manager)
    context = {"room_id": "studio", "character_name": "Pete", "custom": "retain me"}
    assert await backend.generate(model=alias, prompt="Input", context=context) == "  Exact response.\n"
    args = manager.generate_text.call_args
    assert args.args == ("Input",)
    assert args.kwargs["requested_route"] == route
    assert args.kwargs["allow_fallback"] is False
    assert args.kwargs["context"].room_id == "studio"
    assert args.kwargs["context"].metadata["evo_task_context"]["custom"] == "retain me"
    assert context == {"room_id": "studio", "character_name": "Pete", "custom": "retain me"}


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [{"error": "local model unavailable", "text": "placeholder"},
    {"text": "Fallback reply", "fallback_occurred": True}, {"text": "  "}])
async def test_adapter_does_not_report_model_failure_or_fallback_as_assigned_model_success(result):
    manager = SimpleNamespace(generate_text=AsyncMock(return_value=result))
    with pytest.raises(RuntimeError):
        await EVOInferenceBackend(manager).generate(model="gemma-studio", prompt="Input", context={})


@pytest.mark.asyncio
async def test_unknown_routing_alias_cannot_silently_use_studio():
    manager = SimpleNamespace(generate_text=AsyncMock())
    with pytest.raises(ValueError, match="routing alias"):
        await EVOInferenceBackend(manager).generate(model="unknown", prompt="Input", context={})
    assert manager.generate_text.await_count == 0


@pytest.mark.asyncio
async def test_actual_epete_task_reaches_generate_text_through_adapter():
    manager = SimpleNamespace(generate_text=AsyncMock(return_value={"text": "Host response."}))
    engine = EPete(llm_backend=EVOInferenceBackend(manager))
    result = await engine.execute(InferenceTask("host-task", TaskType.CONVERSATION, "Input",
        force_model=InferenceModel.STUDIO))
    assert result.success
    assert result.output == "Host response."
    assert manager.generate_text.await_count == 1
