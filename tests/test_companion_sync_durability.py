"""Sync must not acknowledge data that was never durably applied."""
from unittest.mock import patch

import pytest

from pubpartner.pubpartner_federation.docking import DockingNode
from pubpartner.pubpartner_federation.protocol import VectorClock


def node(tmp_path, name, role="portable"):
    return DockingNode(tmp_path / name, owner_id="u", role=role, node_id=name)


def test_failed_local_write_rolls_back_data_and_clock_across_restart(tmp_path):
    h = node(tmp_path, "h")
    try:
        with patch.object(h.store, "record_change", side_effect=OSError("simulated write failure")):
            with pytest.raises(OSError):
                h.record_knowledge("x", text="Lantern", friend_id="alex", source_ref="owner", confirmed=True)
        assert not h.store.all_entities()
        assert h.engine.clock == VectorClock()
        h.close()
        h = node(tmp_path, "h")
        assert not h.store.all_entities()
        assert h.engine.clock == VectorClock()
    finally:
        h.close()


def test_partial_receive_failure_rolls_back_entire_envelope_and_can_retry(tmp_path):
    h, b = node(tmp_path, "h"), node(tmp_path, "b", "resident")
    try:
        for i in range(2):
            h.record_knowledge(str(i), text=f"Lantern {i}", friend_id="alex", source_ref="owner", confirmed=True)
        original = b.store.put
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated interruption")
            return original(*args, **kwargs)
        envelope = h.engine.envelope(b.engine.clock)
        with patch.object(b.store, "put", side_effect=fail_second):
            with pytest.raises(OSError):
                b.engine.receive(envelope)
        assert not b.store.all_entities()
        assert b.engine.clock == VectorClock()
        h.dock(b)
        assert len(b.recall(owner_id="u", friend_id="alex", query="Lantern")["items"]) == 2
    finally:
        h.close()
        b.close()


def test_base_relays_received_experiences_to_another_horizon(tmp_path):
    first, base, second = node(tmp_path, "first"), node(tmp_path, "base", "resident"), node(tmp_path, "second")
    try:
        first.record_experience(user_text="Lantern workshop", reply_text="The design worked.",
            session_id="s", friend_id="alex", source_ref="turn:one")
        first.dock(base)
        second.dock(base)
        recalled = second.recall(owner_id="u", friend_id="alex", query="Lantern")
        assert len(recalled["items"]) == 1
        assert "The design worked." in recalled["items"][0]["text"]
    finally:
        first.close()
        base.close()
        second.close()


def test_failed_delete_keeps_existing_knowledge_and_causal_clock(tmp_path):
    h = node(tmp_path, "h")
    try:
        identity = h.record_knowledge("x", text="Lantern", friend_id="alex", source_ref="owner", confirmed=True)
        previous = h.engine.clock
        with patch.object(h.store, "mark_change", side_effect=OSError("interrupted delete")):
            with pytest.raises(OSError):
                h.engine.delete("knowledge", identity)
        assert not h.store.get("knowledge", identity).deleted
        assert h.engine.clock == h.store.load_clock() == previous
    finally:
        h.close()
