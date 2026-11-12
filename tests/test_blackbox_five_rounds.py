"""Failure-focused cases for the five-round Blackbox review."""
import json

import pytest

from blackbox_event_language.schema import BlackBoxValidationError, parse_record
from modules.blackbox_runtime import create_blackbox_witness


@pytest.mark.parametrize('suffix', ['|unhashed=ignored', '|seq=0'])
def test_round1_rejects_extra_or_duplicate_wire_fields(tmp_path, suffix):
    witness = create_blackbox_witness(tmp_path)
    wire = witness.path.read_text().splitlines()[0]
    with pytest.raises(BlackBoxValidationError):
        parse_record(wire+suffix)


@pytest.mark.parametrize('session_id', ['../escaped', 'absolute', r'..\escaped'])
def test_round1_session_id_cannot_escape_ledger_directory(tmp_path, session_id):
    if session_id == 'absolute':
        session_id = str(tmp_path/'absolute')
    with pytest.raises(ValueError):
        create_blackbox_witness(tmp_path, session_id=session_id)


def test_round2_heartbeat_cannot_hide_a_dropped_event(tmp_path):
    from blackbox_event_language.schema import decode_record
    witness = create_blackbox_witness(tmp_path)
    assert witness.record_event('system.event', data={'invalid':float('nan')}) is None
    health = witness.health()
    assert health['connection']=='running'
    assert health['coverage']=='degraded' and health['failed_events']==1
    events = [decode_record(line) for line in witness.path.read_text().splitlines()]
    gaps = [r for r in events if r['payload'].get('event_type')=='runtime.coverage_gap']
    assert len(gaps)==1 and gaps[0]['payload']['failed_events']=='1'
    assert witness.health()['failed_events']==1


def test_round2_malformed_event_is_an_explicit_failure_not_an_exception(tmp_path):
    witness = create_blackbox_witness(tmp_path)
    assert witness.record_event('system.event', data=42) is None
    assert witness.health()['coverage']=='degraded'


def test_round3_external_truncation_halts_instead_of_appending_to_damage(tmp_path):
    witness = create_blackbox_witness(tmp_path)
    witness.path.write_bytes(b'')
    assert witness.record_event('system.event', data={'state':'changed'}) is None
    assert witness.path.read_bytes()==b''


def test_round3_removed_live_ledger_never_verifies_as_empty_success(tmp_path):
    witness = create_blackbox_witness(tmp_path)
    witness.path.unlink()
    assert not witness.verify().ok


def test_round3_event_ledger_is_owner_only_on_posix(tmp_path):
    import os
    import stat
    if os.name != 'posix':pytest.skip('POSIX permissions only')
    witness = create_blackbox_witness(tmp_path)
    assert stat.S_IMODE(witness.path.stat().st_mode)==0o600


@pytest.mark.asyncio
async def test_round4_offline_audit_detects_saved_chat_missing_from_blackbox(tmp_path):
    from modules.hub import Hub
    from tools.blackbox_inspect import inspect
    witness = create_blackbox_witness(tmp_path)
    hub = Hub(tmp_path)  # Simulates a disconnected witness; canonical chat survives.
    await hub.post_chat_message('world', 'owner', 'An unwitnessed message, still saved.')
    witness.close()
    before = witness.path.read_bytes()
    report = inspect(tmp_path)
    assert not report['coverage_complete']
    assert report['chat']['missing']==1
    assert witness.path.read_bytes()==before


def test_round4_offline_audit_retains_a_known_gap_after_restart(tmp_path):
    from tools.blackbox_inspect import inspect
    witness = create_blackbox_witness(tmp_path)
    witness.record_event('system.event', data={'invalid':float('nan')})
    witness.health(); witness.close()
    restarted = create_blackbox_witness(tmp_path)
    restarted.close()
    report = inspect(tmp_path)
    assert not report['coverage_complete']
    assert report['known_failed_events']==1


@pytest.mark.asyncio
async def test_round5_deleted_chat_archive_is_detected(tmp_path):
    from modules.hub import Hub
    from tools.blackbox_inspect import inspect
    hub = Hub(tmp_path);witness = create_blackbox_witness(tmp_path)
    hub.blackbox_witness = witness
    await hub.post_chat_message('world', 'owner', 'Keep this original.')
    witness.close()
    assert inspect(tmp_path)['coverage_complete']
    (tmp_path/'logs'/'world.jsonl').unlink()
    report = inspect(tmp_path)
    assert not report['coverage_complete']
    assert report['chat']['unarchived']==1


def test_round5_bad_capture_sidecar_reports_failure_without_crashing_audit(tmp_path):
    from tools.blackbox_inspect import inspect
    witness = create_blackbox_witness(tmp_path)
    sink = witness.media.start(16000,1); sink.append(b'\0\0'*1600)
    witness.close()
    sink.path.with_suffix('.json').write_text('[]')
    report = inspect(tmp_path)
    assert not report['ok'] and report['captures'][0]['error']


@pytest.mark.asyncio
@pytest.mark.parametrize('cancelled', [False, True])
async def test_round5_pubpartner_dispatch_exception_has_a_terminal_event(tmp_path, cancelled):
    import asyncio
    from unittest.mock import AsyncMock
    from blackbox_event_language.schema import decode_record
    from modules.pubpartner_core import PubPartnerSpine
    spine = PubPartnerSpine(tmp_path)
    witness = create_blackbox_witness(tmp_path);spine.blackbox_witness = witness
    error = asyncio.CancelledError() if cancelled else RuntimeError('Provider interrupted')
    spine.provider_dispatcher.dispatch = AsyncMock(side_effect=error)
    with pytest.raises(type(error)):
        await spine.run_turn(user_id='owner', session_id='interruption', message='Hello, there.',
                             provider={'provider':'mock'}, allow_fallback=False)
    witness.close()
    events = [decode_record(line)['payload'] for line in witness.path.read_text().splitlines()]
    started = next(r for r in events if r.get('event_type')=='partner.turn_started')
    failed = [r for r in events if r.get('event_type')=='partner.turn_failed']
    assert len(failed)==1 and failed[0]['turn_id']==started['turn_id']
    assert failed[0]['state']==('interrupted' if cancelled else 'failed')
    assert not any(r.get('event_type')=='partner.private_turn' for r in events)


def test_round5_concurrent_close_leaves_no_events_after_shutdown(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from blackbox_event_language.schema import decode_record
    witness = create_blackbox_witness(tmp_path)
    def work(i):
        if i==50:
            witness.close()
        else:
            witness.record_event('system.event', data={'number':i})
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, range(200)))
    events = [decode_record(line)['payload'] for line in witness.path.read_text().splitlines()]
    assert events[-1]['event_type']=='runtime.blackbox_stopped'
    assert sum(r.get('event_type')=='runtime.blackbox_stopped' for r in events)==1
    assert witness.verify().ok


@pytest.mark.asyncio
@pytest.mark.parametrize('damage', ['text', 'duplicate'])
async def test_round5_chat_audit_detects_changed_text_or_duplicate_witness(tmp_path, damage):
    from modules.hub import Hub
    from tools.blackbox_inspect import inspect
    hub = Hub(tmp_path);witness = create_blackbox_witness(tmp_path)
    hub.blackbox_witness = witness
    message = await hub.post_chat_message('world', 'owner', 'The exact, original text.')
    if damage=='duplicate':
        # Bypass the idempotent delivery API to construct a genuinely damaged
        # ledger with a duplicate receipt for the offline inspector to catch.
        assert witness.record_event('chat.message',source='chat',actor=message['user_id'],
            data={k:message[k] for k in ('room','text','t','message_id')})
    else:
        path = tmp_path/'logs'/'world.jsonl'
        entry = json.loads(path.read_text());entry['text']='A changed message.'
        path.write_text(json.dumps(entry)+'\n')
    witness.close()
    assert witness.verify().ok  # An intact chain alone is insufficient.
    report = inspect(tmp_path)
    assert not report['ok'] and not report['coverage_complete']
    assert report['chat']['mismatched' if damage=='text' else 'duplicates']==1


def test_round5_abrupt_process_exit_preserves_durable_events(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    from blackbox_event_language.schema import decode_record
    from blackbox_recorder import AppendOnlyBlackBoxRecorder
    script = r'''
import os, sys
from modules.blackbox_runtime import create_blackbox_witness
witness=create_blackbox_witness(sys.argv[1],session_id='abrupt')
for number in range(40):
    if not witness.record_event('system.event',data={'number':number}):
        os._exit(18)
os._exit(17)  # No Python shutdown hooks, witness.close(), or file finalization.
'''
    result = subprocess.run([sys.executable,'-c',script,str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],capture_output=True,timeout=20)
    assert result.returncode==17, result.stderr
    path = tmp_path/'blackbox'/'abrupt.bbx'
    recorder = AppendOnlyBlackBoxRecorder(path,'abrupt')
    assert recorder.verify().ok
    events = [decode_record(line)['payload'] for line in path.read_text().splitlines()]
    assert [int(e['number']) for e in events if e.get('event_type')=='system.event']==list(range(40))
    assert not any(e.get('event_type')=='runtime.blackbox_stopped' for e in events)


def test_round5_explicit_reopen_recovers_after_storage_returns(tmp_path, monkeypatch):
    import os
    witness = create_blackbox_witness(tmp_path)
    def fail(_):raise OSError('Injected storage failure')
    with monkeypatch.context() as patch:
        patch.setattr(os,'fsync',fail)
        assert witness.record_event('system.event', data={'number':1}) is None
        with pytest.raises(OSError):witness.close()
    witness.reopen()
    assert witness.health()['connection']=='running'
    assert witness.health()['coverage']=='degraded'
    assert witness.verify().ok
    witness.close()


def test_round5_reopen_refuses_corrupt_source_without_modifying_it(tmp_path):
    witness = create_blackbox_witness(tmp_path); witness.close()
    damaged = witness.path.read_bytes().replace(b'external_boundary',b'damaged_boundary')
    witness.path.write_bytes(damaged)
    with pytest.raises(OSError):witness.reopen()
    assert witness.path.read_bytes()==damaged


def test_round5_disabled_witness_remains_inactive_when_reopened(tmp_path):
    witness = create_blackbox_witness(tmp_path, enabled=False)
    witness.close(); witness.reopen()
    assert witness.health()['connection']=='inactive'
    assert not witness.path.exists()
