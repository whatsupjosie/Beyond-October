"""Offline Base/Horizon integration using real stores, sync and cartridges."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import json

import pytest

from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_provider import ProviderResult
from pubpartner.cartridge import init_cartridge, load_cartridge
from pubpartner.portable_runtime import PortableRuntime
from pubpartner.sequence_controller import SequenceController
from pubpartner.pubpartner_federation.docking import DockingNode


@pytest.fixture
def pair(tmp_path):
    horizon = DockingNode(tmp_path / "horizon", owner_id="u", role="portable")
    base = DockingNode(tmp_path / "base", owner_id="u", role="resident")
    yield horizon, base
    horizon.close()
    base.close()


def runtime(tmp_path, node=None, **options):
    path = tmp_path / "cartridge"
    init_cartridge(path, name="Alex", summary="Steady, curious and attentive.",
                   cadence="short sentences", vocabulary="plain and warm")
    cartridge = load_cartridge(path)
    client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=SimpleNamespace(
        content=[SimpleNamespace(type="text", text="We can compare practical choices.")]))))
    result = PortableRuntime(cartridge, llm_client=client,
        sequencer=SequenceController(debounce_seconds=0), docking_node=node,
        subject_id="u", friend_id="alex", **options)
    return result, client, path


def test_dock_exchanges_knowledge_both_ways_and_is_idempotent_after_restart(tmp_path):
    h = DockingNode(tmp_path / "h", owner_id="u", role="portable")
    b = DockingNode(tmp_path / "b", owner_id="u", role="resident")
    try:
        h.record_knowledge("one", text="Lantern workshop opens Monday", friend_id="alex",
                           source_ref="owner:one", confirmed=True)
        b.record_knowledge("two", text="Lantern workshop closes Friday", friend_id="alex",
                           source_ref="owner:two", confirmed=True)
        first = h.dock(b)
        assert first["status"] == "synced"
        assert first["sent"] == first["received"] == 1
        assert all(x["status"] == "healthy" for x in first["before"] + first["after"])
        assert len(h.recall(owner_id="u", friend_id="alex", query="Lantern")["items"]) == 2
        h.close()
        h = DockingNode(tmp_path / "h", owner_id="u", role="portable")
        again = h.dock(b)
        assert again["sent"] == again["received"] == 0
        assert len(h.recall(owner_id="u", friend_id="alex", query="Lantern")["items"]) == 2
    finally:
        h.close()
        b.close()


def test_candidates_and_other_companions_are_not_recalled(pair):
    h, b = pair
    h.record_knowledge("same", text="Lantern may be green", friend_id="alex", source_ref="hypothesis")
    h.record_knowledge("same", text="Lantern is blue", friend_id="jeremy", source_ref="owner", confirmed=True)
    h.dock(b)
    assert b.recall(owner_id="u", friend_id="alex", query="Lantern")["items"] == []
    assert b.recall(owner_id="someone-else", friend_id="jeremy", query="Lantern")["items"] == []
    assert len(b.recall(owner_id="u", friend_id="jeremy", query="Lantern")["items"]) == 1


def test_concurrent_knowledge_changes_keep_conflicts_visible_on_repeat_dock(pair):
    h, b = pair
    for node, text in [(h, "Lantern is red"), (b, "Lantern is blue")]:
        node.record_knowledge("shared", text=text, friend_id="alex", source_ref="owner", confirmed=True)
    first = h.dock(b)
    assert first["status"] == "synced_with_conflicts"
    assert h.store.conflicts() and b.store.conflicts()
    assert h.dock(b)["status"] == "synced_with_conflicts"
    assert h.recall(owner_id="u", friend_id="alex", query="Lantern")["items"][0]["text"] == "Lantern is red"
    assert b.recall(owner_id="u", friend_id="alex", query="Lantern")["items"][0]["text"] == "Lantern is blue"


@pytest.mark.parametrize("difference", ["owner", "role", "identity", "protocol", "health"])
def test_invalid_docking_pairs_are_rejected_before_exchange(tmp_path, difference):
    h = DockingNode(tmp_path / "h", owner_id="u", role="portable", node_id="h")
    b = DockingNode(tmp_path / "b", owner_id="other" if difference == "owner" else "u",
        role="portable" if difference == "role" else "resident",
        node_id="h" if difference == "identity" else "b")
    try:
        if difference == "protocol":
            b.engine.PROTOCOL = "unsupported"
        if difference == "health":
            b.health = Mock(return_value={"status": "unhealthy"})
        with pytest.raises((ValueError, RuntimeError)):
            h.dock(b)
        assert not h.store.all_entities() and not b.store.all_entities()
    finally:
        h.close()
        b.close()


def test_storage_owner_cannot_be_reassigned(tmp_path):
    h = DockingNode(tmp_path, owner_id="u", role="portable")
    h.close()
    with pytest.raises(ValueError, match="another owner"):
        DockingNode(tmp_path, owner_id="other", role="portable")


def test_post_exchange_health_failure_is_reported(pair):
    h, b = pair
    healthy = b.health()
    b.health = Mock(side_effect=[healthy, {**healthy, "status": "unhealthy"}])
    assert h.dock(b)["status"] == "health_failed_after_sync"


def test_recall_reports_incomplete_when_result_or_scan_budget_is_hit(pair):
    h, _ = pair
    for i in range(25):
        h.record_knowledge(str(i), text=f"Lantern {i}", friend_id="alex", source_ref="owner", confirmed=True)
    result = h.recall(owner_id="u", friend_id="alex", query="Lantern", limit=100)
    assert len(result["items"]) == 20 and not result["complete"]
    result = h.recall(owner_id="u", friend_id="alex", query="Lantern", max_scan=1)
    assert len(result["items"]) == 1 and not result["complete"]


@pytest.mark.asyncio
async def test_real_horizon_and_base_turns_exchange_memories_knowledge_and_experiences(pair, tmp_path):
    h, b = pair
    portable, client, path = runtime(tmp_path, h)
    authored = {p.name: p.read_bytes() for p in path.glob("*.yaml")}
    try:
        portable._cartridge.memory.add("Lantern sail design", memory_type="semantic", importance=.8)
        portable.submit_input("I am excited about the observatory.")
        result = portable.run_turn()
        assert result.companion_advisory["applied"]
        assert result.docking_status["capture"]["status"] == "recorded"
        base = PubPartnerSpine(tmp_path / "base-data", docking_node=b)
        base.provider_dispatcher.dispatch = AsyncMock(return_value=ProviderResult(
            ok=True, provider="mock", raw_response="The tidal charts are ready."))
        turn = await base.run_turn(user_id="u", session_id="s", message="Can you help with tidal charts?",
            friend={"id": "alex", "name": "Alex"}, provider={"provider": "mock"})
        assert turn["docking_capture"]["status"] == "recorded"
        b.record_knowledge("fact", text="Lantern uses tidal power", friend_id="alex", source_ref="owner", confirmed=True)
        assert h.dock(b)["status"] == "synced"
        assert {x.entity_type for x in b.store.all_entities()} == {"memory", "knowledge", "experience"}
        packet = await base.build_turn_packet(user_id="u", session_id="new", message="observatory Lantern",
            friend={"id": "alex", "name": "Alex"})
        assert packet["docking_recall"]["count"] >= 2
        assert "observatory" in json.dumps(packet["fcp1"])
        portable.submit_input("What about tidal charts?")
        portable.run_turn()
        assert "The tidal charts are ready." in client.messages.create.call_args.kwargs["system"]
        assert authored == {p.name: p.read_bytes() for p in path.glob("*.yaml")}
        public = await base.build_turn_packet(user_id="u", session_id="new", message="observatory Lantern",
            task={"audience": "public"}, room_id="stage", friend={"id": "alex", "name": "Alex"})
        assert "docking_recall" not in public
    finally:
        portable.close()


@pytest.mark.asyncio
async def test_base_docking_failures_do_not_discard_a_successful_reply(pair, tmp_path):
    _, b = pair
    b.recall = Mock(side_effect=OSError("disk unavailable"))
    b.record_experience = Mock(side_effect=OSError("disk unavailable"))
    base = PubPartnerSpine(tmp_path, docking_node=b)
    base.provider_dispatcher.dispatch = AsyncMock(return_value=ProviderResult(ok=True, provider="mock", raw_response="A useful reply."))
    result = await base.run_turn(user_id="u", session_id="s", message="Hello", provider={"provider": "mock"})
    assert result["friend_response"] == "A useful reply."
    assert result["docking_capture"]["status"] == "failed"
    assert result["docking_recall"]["error"] == "OSError"
    assert base.verify_receipts(user_id="u", session_id="s")["ok"]


def test_portable_docking_failure_is_visible_without_losing_reply(pair, tmp_path):
    h, _ = pair
    portable, _, _ = runtime(tmp_path, h)
    try:
        h.recall = Mock(side_effect=OSError())
        h.record_experience = Mock(side_effect=OSError())
        portable.submit_input("Hello")
        result = portable.run_turn()
        assert result.reply_text == "We can compare practical choices."
        assert result.docking_status["capture"]["status"] == "failed"
        assert result.docking_status["recall"]["error"] == "OSError"
    finally:
        portable.close()


@pytest.mark.asyncio
async def test_auto_detected_writing_skips_base_advice_and_preserves_bytes(tmp_path):
    base = PubPartnerSpine(tmp_path)
    text = '```python\nprint("I am sad")\n```\n'
    result = await base.run_turn(user_id="u", session_id="s", message=text, provider={"provider": "mock"})
    assert result["source"]["kind"] == "code"
    assert not result["companion_advisory"]["applied"]
    assert not result["companion_review"]["applied"]
    assert base.restore_source(user_id="u", session_id="s", source_id=result["source"]["id"])["text"] == text


def test_portable_protected_writing_and_legacy_switch(tmp_path):
    portable, client, _ = runtime(tmp_path)
    try:
        portable.submit_input("I am sad\nThe authored poem")
        result = portable.run_turn(content_kind="poetry")
        assert not result.companion_advisory["applied"]
        assert not result.companion_review["applied"]
        assert "companion_advisory=" not in client.messages.create.call_args.kwargs["system"]
        portable._companion_advisory_enabled = False
        portable.submit_input("Hello")
        assert portable.run_turn().companion_advisory is None
    finally:
        portable.close()
