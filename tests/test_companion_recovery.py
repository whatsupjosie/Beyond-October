"""Recovered Friday contracts and current-spine integration, offline only."""
import importlib
import json
from unittest.mock import AsyncMock

import pytest

from modules.companion_advisory import CompanionAdvisor
from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_provider import ProviderResult
from modules.wired.contradiction_tracker import ContradictionTracker
from modules.wired.observation_engine import ObservationEngine


def _prepare(advisor, message, **overrides):
    args = dict(user_id="u", session_id="s", friend_id="alex", project_id="p",
                room_id="pubpartner", audience="private")
    args.update(overrides)
    return advisor.prepare(message, **args)


@pytest.mark.parametrize("name", ["companion_core", "pubcast_runtime", "conversation_state",
                                  "eq_integration_layer", "companion_runner", "response_composer"])
def test_recovered_stack_imports_as_a_package_without_sys_path_aliases(name):
    module = importlib.import_module("modules.wired." + name)
    assert module.__package__ == "modules.wired"


@pytest.mark.parametrize("message", ['My friend is sad.', 'She said "I am sad."',
                                     "I am not tired.", "I retired yesterday.",
                                     "I'm tired of this bug.", 'The script says: "I am afraid."'])
def test_observation_does_not_invent_self_emotion_from_other_negated_or_quoted_text(message):
    result = ObservationEngine().observe(message)
    assert not result.emotions
    assert result.raw_text == message


def test_explicit_emotion_goals_and_quoted_code_remain_distinct():
    message = 'I am frustrated. I want to finish the project. ```I am sad.```'
    result = ObservationEngine().observe(message)
    assert [e.label for e in result.emotions] == ["frustrated"]
    assert result.goals[0].description == "finish the project"
    assert result.goals[0].stated is True
    assert result.raw_text == message


def test_unconfigured_deep_observation_fails_without_calling_a_provider():
    with pytest.raises(RuntimeError, match="explicitly configured"):
        ObservationEngine().observe("hello", use_llm=True)


def test_statement_differences_are_provisional_bounded_and_session_scoped():
    tracker = ContradictionTracker("u", capacity=2)
    tracker.ingest("I like coffee.", "s")
    tracker.ingest("I do not like coffee.", "different-session")
    assert tracker.open_contradictions() == []
    tracker.ingest("I do not like coffee.", "s")
    item = tracker.open_contradictions()[0]
    assert item.requires_confirmation
    assert item.claim_a.text == "I like coffee"
    assert "growth" not in tracker.generate_growth_observation().lower()
    tracker.resolve(item.id, "The preference changed.")
    assert tracker.open_contradictions() == []
    assert tracker.summary()["claims"] <= 2


def test_legacy_guided_runtime_and_companion_execute_with_real_recovered_helpers():
    from modules.wired.companion_core import CompanionCore
    from modules.wired.pubcast_runtime import PubCastRuntime
    companion = CompanionCore("u", "s")
    companion.process_incoming("I want to finish the project.")
    turn = companion.process_outgoing("I want to finish the project.", "Compare the three implementation choices.")
    assert turn.response_text
    assert companion.full_portrait()["contradiction_summary"]["claims"] == 1
    runtime = PubCastRuntime("u", "s")
    prompt = runtime.process_to_prompt("I want to finish the project. Can you help me plan?")
    output = runtime.record_response(prompt, "We can compare the three implementation choices.")
    assert output.turn_index == 1
    summary = runtime.end_session()
    assert summary  # actual end-of-session meaning path, not a placeholder object


def test_explicit_help_request_overrides_old_indefinite_hold_without_canned_resources():
    advisor = CompanionAdvisor()
    packet = _prepare(advisor, "I am devastated. Can you help me make a plan?")
    assert packet["pacing"] == "ready"
    guidance = json.dumps(packet["guidance"]).lower()
    assert "practical help" in guidance
    assert "988" not in guidance
    assert "hotline" not in guidance
    assert packet["advisory_only"] is True


def test_shared_turns_do_not_replay_private_history_or_learn_it():
    history = [{"role": "user", "content": "I know I always abandon projects."}] * 50
    packet = _prepare(CompanionAdvisor(), "Hello.", audience="shared", history=history)
    assert packet["history_rows_used"] == 0
    assert packet["known_patterns"] == []
    private = _prepare(CompanionAdvisor(), "Hello.", history=history)
    assert private["history_rows_used"] == 16
    assert len(private["known_patterns"]) <= 4


def test_quality_review_flags_echo_without_modifying_response():
    advisor = CompanionAdvisor()
    text = "I know I always abandon difficult projects."
    _prepare(advisor, text)
    response = "It sounds like " + text
    result = advisor.review(text, response)
    assert result["response_modified"] is False
    assert result["parroting_risk"] in {"moderate", "high", "critical"}


@pytest.mark.asyncio
async def test_actual_spine_feeds_guidance_to_provider_and_records_review_once(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    reply = "We can compare three concrete choices."
    dispatch = AsyncMock(return_value=ProviderResult(ok=True, provider="ollama", raw_response=reply))
    spine.provider_dispatcher.dispatch = dispatch
    result = await spine.run_turn(user_id="u", session_id="s",
        message="I am frustrated. Can you help me plan?", provider={"provider": "mock"})
    assert dispatch.await_count == 1
    packet = dispatch.call_args.args[0]
    assert any(g.get("source") == "companion_advisory" for g in packet["fcp1"]["guide"])
    assert result["companion_advisory"]["pacing"] == "ready"
    assert result["companion_review"]["response_modified"] is False
    assert result["friend_response"] == reply
    assert result["receipt"]["companion_review"] == result["companion_review"]
    assert spine.verify_receipts(user_id="u", session_id="s")["ok"]


@pytest.mark.asyncio
async def test_restart_replays_existing_permitted_history_without_a_new_memory_store(tmp_path):
    first = PubPartnerSpine(tmp_path)
    first.provider_dispatcher.dispatch = AsyncMock(return_value=ProviderResult(
        ok=True, provider="ollama", raw_response="Let's compare next steps."))
    await first.run_turn(user_id="u", session_id="s",
        message="I know I always abandon difficult projects.", provider={"provider": "mock"})
    restarted = PubPartnerSpine(tmp_path)
    turn = await restarted.build_turn_packet(user_id="u", session_id="s", message="What can I try?")
    assert turn["companion_advisory"]["known_patterns"]
    other = await restarted.build_turn_packet(user_id="different-user", session_id="s", message="Hello.")
    assert other["companion_advisory"]["known_patterns"] == []
    other_session = await restarted.build_turn_packet(user_id="u", session_id="different-session", message="Hello.")
    assert other_session["companion_advisory"]["known_patterns"] == []


@pytest.mark.asyncio
async def test_protected_writing_and_legacy_bypass_do_not_receive_new_analysis(tmp_path):
    spine = PubPartnerSpine(tmp_path / "enabled")
    exact = 'Original poem\n"I am sad"\nNo rewriting.\n'
    result = await spine.run_turn(user_id="u", session_id="s", message=exact,
                                  content_kind="lyrics", provider={"provider": "mock"})
    assert result["companion_advisory"]["applied"] is False
    restored = spine.restore_source(user_id="u", session_id="s", source_id=result["source"]["id"])
    assert restored["text"] == exact
    disabled = PubPartnerSpine(tmp_path / "disabled", companion_advisory_enabled=False)
    old = await disabled.run_turn(user_id="u", session_id="s", message="Hello.", provider={"provider": "mock"})
    assert "companion_advisory" not in old
    assert "companion_review" not in old


@pytest.mark.asyncio
async def test_large_message_retains_source_without_forcing_analysis(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    message = "original " * 2000
    turn = await spine.build_turn_packet(user_id="u", session_id="s", message=message)
    assert turn["companion_advisory"]["applied"] is False
    restored = spine.restore_source(user_id="u", session_id="s", source_id=turn["source"]["id"])
    assert restored["text"] == message
