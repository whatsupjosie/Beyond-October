"""Alex must remain Alex across real PubPartner disk reopenings.

Provider mocks are deliberately labeled: these tests prove prompt, personality,
archive, audience, and ownership contracts, NOT real model inference.
"""
import pytest

from modules.alex_jeremy_bridge import AlexJeremyBridge
from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_provider import ProviderResult, _friend_generation_contract
from modules.pubpartner_vessel.runtime import PubPartnerVesselRuntime


@pytest.mark.asyncio
async def test_restart_restores_actual_conversation_and_personality(tmp_path, monkeypatch):
    vessel = PubPartnerVesselRuntime.open_or_create(tmp_path / "vessel")
    bridge = AlexJeremyBridge(tmp_path)
    first = PubPartnerSpine(tmp_path, vessel_runtime=vessel, alex_bridge=bridge)

    async def generated(turn, provider_config):
        assert "Generate the next conversational reply in Alex's established voice" in _friend_generation_contract(turn)
        assert "generic_assistant" in str(turn["fcp1"]["f"]["avoid"])
        assert "Do not pretend to be Alex" not in _friend_generation_contract(turn)
        return ProviderResult(ok=True, provider="ollama", model="fake-protocol-test", raw_response="I heard about the cobalt lantern. I'll remember you telling me.")
    monkeypatch.setattr(first.provider_dispatcher, "dispatch", generated)
    result = await first.run_turn(user_id="one", session_id="session-one", message="I named the garden lamp cobalt lantern.",
                                  provider={"provider": "ollama", "model": "fake"}, allow_fallback=False)
    assert result["provider_result"]["ok"]
    assert result["fcp1"]["f"]["id"] == "alex"
    assert "Be present before trying to solve anything" in result["fcp1"]["f"]["law"]
    assert "continuing PubPartner" in result["fcp1"]["f"]["identity"]
    bridge.shutdown()

    # New objects emulate closing the app and starting it again.
    bridge2 = AlexJeremyBridge(tmp_path)
    reopened = PubPartnerSpine(tmp_path, alex_bridge=bridge2, vessel_runtime=PubPartnerVesselRuntime.open(tmp_path / "vessel"))
    prompts = []
    async def followup(turn, provider_config):
        prompts.append(turn)
        return ProviderResult(ok=True, provider="ollama", model="fake-protocol-test", raw_response="The cobalt lantern you named. Yes.")
    monkeypatch.setattr(reopened.provider_dispatcher, "dispatch", followup)
    result2 = await reopened.run_turn(user_id="one", session_id="session-one", message="What do you remember about the lamp?",
                                      provider={"provider": "ollama", "model": "fake"}, allow_fallback=False)
    history = prompts[0]["fcp1"]["history"]
    assert len(history) == 2
    assert "cobalt lantern" in history[0]["content"]
    assert "cobalt lantern" in history[1]["content"]
    assert "cobalt lantern" in result2["llm_prompt_text"]
    assert "Be present before trying" in result2["llm_prompt_text"]
    bridge2.shutdown()


@pytest.mark.asyncio
async def test_private_chat_not_exposed_to_other_user_or_shared_room(tmp_path, monkeypatch):
    spine = PubPartnerSpine(tmp_path)
    async def generated(turn, provider_config):
        return ProviderResult(ok=True, provider="ollama", model="fake-protocol-test", raw_response="Understood about marigold comet.")
    monkeypatch.setattr(spine.provider_dispatcher, "dispatch", generated)
    await spine.run_turn(user_id="one", session_id="s", message="Private: marigold comet secret.",
                         friend="alex", provider={"provider": "ollama"}, allow_fallback=False)
    private = await spine.build_turn_packet(user_id="one", session_id="s", message="What did I tell you?", friend="alex")
    assert any("marigold comet" in row["content"] for row in private["fcp1"]["history"])
    stranger = await spine.build_turn_packet(user_id="two", session_id="s", message="What did they tell you?", friend="alex")
    assert "marigold comet" not in str(stranger["fcp1"]["history"])
    shared = await spine.build_turn_packet(user_id="one", session_id="s", room_id="lobby", message="Hello room!", friend="alex")
    assert not shared["fcp1"]["history"]
    # The browser can deliberately opt out of auto-history by supplying []
    explicit_empty = await spine.build_turn_packet(user_id="one", session_id="s", message="New topic", friend="alex", history=[])
    assert not explicit_empty["fcp1"]["history"]


@pytest.mark.asyncio
async def test_only_real_successful_replies_are_resumed(tmp_path, monkeypatch):
    spine = PubPartnerSpine(tmp_path)
    async def failed(turn, config):
        return ProviderResult(ok=False, provider="ollama", model="fake", error="model down")
    monkeypatch.setattr(spine.provider_dispatcher, "dispatch", failed)
    await spine.run_turn(user_id="one", session_id="s", message="Do not treat a failed reply as a conversation.",
                         friend="alex", provider={"provider": "ollama"}, allow_fallback=False)
    turn = await spine.build_turn_packet(user_id="one", session_id="s", message="Anything to remember?", friend="alex")
    assert not turn["fcp1"]["history"]


def test_provider_personality_contract_bound_to_selected_friend():
    alex = {"fcp1": {"f": {"id": "alex", "name": "Alex"}}}
    craig = {"fcp1": {"f": {"id": "craig", "name": "Craig"}}}
    assert "Alex's established voice" in _friend_generation_contract(alex)
    assert "Craig's established voice" in _friend_generation_contract(craig)
    assert "Alex's established voice" not in _friend_generation_contract(craig)

@pytest.mark.asyncio
async def test_owner_explicitly_asking_what_alex_remembers_survives_restart(tmp_path):
    original = AlexJeremyBridge(tmp_path)
    await original.process_user_turn(user_id="one", session_id="s1", text="My red notebook is named Atlas Seven.")
    original.shutdown()
    reopened = AlexJeremyBridge(tmp_path)
    # No keyword overlap with the remembered object's name.
    recalled = reopened.recalled_for_speaker(user_id="one", query="What do you remember about me?")
    # After lazy loading on a private turn, Alex's diary becomes available.
    if not recalled:
        reopened.alex_for("one")
        recalled = reopened.recalled_for_speaker(user_id="one", query="What do you remember about me?")
    assert any("Atlas Seven" in r["text"] for r in recalled)
    assert reopened.recalled_for_speaker(user_id="one", query="How do I grow bonsai trees?") == []
    reopened.shutdown()


@pytest.mark.asyncio
async def test_cannot_mark_shared_room_private_to_inject_personal_memories(tmp_path):
    bridge = AlexJeremyBridge(tmp_path)
    spine = PubPartnerSpine(tmp_path, alex_bridge=bridge)
    await spine.build_turn_packet(user_id="one", session_id="s", message="The oracle riddle is blue stapler.", friend="alex")
    query = await spine.build_turn_packet(
        user_id="one", session_id="s", room_id="lobby", message="Tell me about oracle riddle",
        friend="alex", task={"audience": "private"},
    )
    assert not any(m.get("src") == "alex_memory" for m in query["fcp1"]["m"])
    assert query["fcp1"]["history"] == []
    bridge.shutdown()

@pytest.mark.asyncio
async def test_edited_voice_is_persistent_across_reopen_and_explicit_friend_selection(tmp_path):
    vessel = PubPartnerVesselRuntime.open_or_create(tmp_path / "vessel")
    spine = PubPartnerSpine(tmp_path, vessel_runtime=vessel)
    profile = spine.profiles.load_profile("friend", "alex", fallback_id="alex")
    profile["tone"] = ["quiet", "wry", "reassuring_without_overpromising"]
    spine.profiles.save_profile("friend", "alex", profile)
    await spine.create_session(user_id="one", session_id="chosen", friend="alex")
    reloaded = PubPartnerSpine(tmp_path, vessel_runtime=PubPartnerVesselRuntime.open(tmp_path / "vessel"))
    turn = await reloaded.build_turn_packet(user_id="one", session_id="chosen", message="Hello Alex", friend="alex")
    assert "wry" in turn["fcp1"]["f"]["tone"]
    assert "reassuring_without_overpromising" in turn["llm_prompt_text"]
    assert "continuing PubPartner" in turn["fcp1"]["f"]["identity"]


def test_pubpartner_defaults_to_real_model_without_disguised_fallback():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "static" / "pubpartner.html").read_text()
    js = (Path(__file__).resolve().parents[1] / "static" / "pubpartner.js").read_text()
    assert '<option value="ollama" selected>' in html
    assert 'id="allowFallback" type="checkbox" checked' not in html
    assert "Diagnostic response (not a real AI)" in js
    assert "No live reply:" in js

@pytest.mark.asyncio
async def test_ollama_capacity_preserves_personality_and_memory(monkeypatch):
    from modules.pubpartner_provider import PubPartnerProviderDispatcher
    import modules.ollama_provider as op
    captured = {}
    async def check(provider, config):
        return {"ok": True, "alive": True, "models": ["local-3b"], "selected_model": "local-3b", "model_available": True}
    async def call(prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return "I remember what you told me."
    monkeypatch.setattr(op, "call_ollama", call)
    d = PubPartnerProviderDispatcher()
    monkeypatch.setattr(d, "status", check)
    turn = {
        "fcp1": {"f": {"id": "alex", "name": "Alex"}},
        "llm_prompt_text": "f={alex voice and shared memories}",
        "token_estimate": {"estimated_tokens": 3800},
    }
    result = await d._ollama(turn, model="local-3b", config={"model": "local-3b", "max_tokens": 500})
    assert result.ok
    assert captured["num_ctx"] >= 5120
    assert "Alex's established voice" in captured["prompt"]
    assert "f={alex voice" in captured["prompt"]
