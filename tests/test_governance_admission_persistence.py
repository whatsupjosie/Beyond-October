"""Admission decisions must survive restart and agree across host workers."""
from concurrent.futures import ThreadPoolExecutor

from modules.governance import GovernanceEngine, EntryStatus


def test_waiting_request_and_decision_survive_new_engine(tmp_path):
    first = GovernanceEngine(tmp_path)
    entry = first.request_entry('u_guest', 'Guest', 'studio', {'recording': True})
    restarted = GovernanceEngine(tmp_path)
    restored = restarted.get_waiting_entry(entry.entry_id)
    assert restored is not None
    assert restored.user_id == 'u_guest' and restored.consents == {'recording': True}
    assert [e.entry_id for e in restarted.list_waiting('studio')] == [entry.entry_id]
    assert restarted.approve_entry(entry.entry_id, 'owner').status == EntryStatus.APPROVED
    assert first.get_waiting_entry(entry.entry_id).resolved_by == 'owner'
    first.mark_entered(entry.entry_id)
    assert GovernanceEngine(tmp_path).get_waiting_entry(entry.entry_id).status == EntryStatus.ENTERED
    assert restarted.list_waiting() == []


def test_concurrent_decisions_have_one_winner_and_cannot_enter_denied_request(tmp_path):
    first, second = GovernanceEngine(tmp_path), GovernanceEngine(tmp_path)
    entry = first.request_entry('u_guest', 'Guest', 'studio')
    assert second.get_waiting_entry(entry.entry_id).status == EntryStatus.WAITING
    with ThreadPoolExecutor(max_workers=2) as pool:
        decisions = list(pool.map(lambda engine: engine.deny_entry(entry.entry_id, 'owner'), [first, second]))
    assert sum(result is not None for result in decisions) == 1
    assert first.approve_entry(entry.entry_id, 'owner') is None
    second.mark_entered(entry.entry_id)
    assert first.get_waiting_entry(entry.entry_id).status == EntryStatus.DENIED


def test_session_and_permanent_bans_propagate_and_unban_has_no_stale_cache(tmp_path, monkeypatch):
    from modules.governance import BanType
    monkeypatch.setenv('PUBCAST_SESSION_ID','one-server-run')
    first,second=GovernanceEngine(tmp_path),GovernanceEngine(tmp_path)
    first.ban_user('visitor','session ban','owner')
    assert second.is_banned('visitor')[0]
    assert second.unban_user('visitor','owner')
    assert not first.is_banned('visitor')[0]
    first.ban_user('visitor','session ban','owner')
    monkeypatch.setenv('PUBCAST_SESSION_ID','next-server-run')
    restarted=GovernanceEngine(tmp_path)
    assert not restarted.is_banned('visitor')[0]
    first.ban_user('persistent','permanent ban','owner',BanType.PERMANENT)
    assert restarted.is_banned('persistent')[0]
    assert restarted.unban_user('persistent','owner')
    assert not first.is_banned('persistent')[0]
