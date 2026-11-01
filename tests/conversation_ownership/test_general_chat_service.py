from types import SimpleNamespace

import pytest

from modules.ai_runtime import AIProfile, AIRuntimeConfig
from modules.conversation_archive import ConversationArchive
from modules.general_chat_service import GeneralChatProviderError, run_general_chat_turn


def config(tmp_path):
    return AIRuntimeConfig(
        config_path=tmp_path / "ai_runtime.json",
        active_profile="test",
        default_options={},
        profiles={
            "test": AIProfile(
                name="test", backend="echo", model="test-model", enabled=True,
                capabilities={"chat": True}
            )
        },
    )


@pytest.mark.asyncio
async def test_turn_preserves_exact_user_and_provider_text(tmp_path, monkeypatch):
    archive = ConversationArchive(tmp_path / "archive.sqlite3")
    cid = archive.create_conversation(title="Exact turn")
    cfg = config(tmp_path)
    seen = {}

    monkeypatch.setattr("modules.general_chat_service.load_ai_runtime_config", lambda _root=None: cfg)
    monkeypatch.setattr("modules.general_chat_service.validate_ai_runtime_config", lambda value: value)

    async def fake_generate(_cfg, profile, prompt, *, system, overrides):
        seen.update(prompt=prompt, system=system, overrides=overrides)
        return SimpleNamespace(text="  exact reply\nline two  ", backend="echo", model=profile.model, provider=profile.name)

    monkeypatch.setattr("modules.general_chat_service.generate_with_profile", fake_generate)
    original = "  exact user text\nline two  "
    turn = await run_general_chat_turn(
        archive=archive, conversation_id=cid, exact_user_text=original,
        options={"temperature": 0.2},
    )

    assert seen["prompt"] == original
    assert turn.user_message.exact_text == original
    assert turn.assistant_message.exact_text == "  exact reply\nline two  "
    loaded = archive.get_conversation(cid)["messages"]
    assert [m["exact_text"] for m in loaded] == [original, "  exact reply\nline two  "]
    assert loaded[1]["parent_message_id"] == loaded[0]["message_id"]


@pytest.mark.asyncio
async def test_provider_failure_keeps_user_work_without_fake_assistant(tmp_path, monkeypatch):
    archive = ConversationArchive(tmp_path / "archive.sqlite3")
    cid = archive.create_conversation(title="Failure custody")
    cfg = config(tmp_path)
    monkeypatch.setattr("modules.general_chat_service.load_ai_runtime_config", lambda _root=None: cfg)
    monkeypatch.setattr("modules.general_chat_service.validate_ai_runtime_config", lambda value: value)

    async def fail(*args, **kwargs):
        raise ConnectionError("model host unavailable")

    monkeypatch.setattr("modules.general_chat_service.generate_with_profile", fail)

    with pytest.raises(GeneralChatProviderError, match="model host unavailable"):
        await run_general_chat_turn(
            archive=archive, conversation_id=cid, exact_user_text="Do not lose this."
        )

    messages = archive.get_conversation(cid)["messages"]
    assert len(messages) == 1
    assert messages[0]["exact_text"] == "Do not lose this."
    assert messages[0]["speaker"] == "User"
