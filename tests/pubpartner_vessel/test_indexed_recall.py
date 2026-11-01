import hashlib
import json

import pytest

from modules.pubpartner_vessel import PubPartnerVesselRuntime
from modules.pubpartner_vessel.search import MemorySearch


def record(runtime, content, source=''):
    return runtime.record_user_turn(user_id='owner', message=content,
        source_ref=source, source_hash=hashlib.sha256(content.encode()).hexdigest(),
        session_id='session', room_id='private')


def compile_context(runtime, query='telescope'):
    return runtime.compile_turn(user_id='owner', message=query,
        session_id='session', room_id='private')


def test_search_limits_do_not_limit_storage_and_timeout_is_explicit(tmp_path, monkeypatch):
    runtime = PubPartnerVesselRuntime.create(tmp_path / 'alex.pubpartner')
    for i in range(270):
        record(runtime, f'telescope observation {i}', str(i))
    context = compile_context(runtime)
    assert len(context.events) == 20
    assert runtime.memory.search.status['events']['status'] == 'bounded'
    monkeypatch.setattr(MemorySearch, 'MAX_SQL_STEPS', 0)
    context = compile_context(runtime)
    assert context.events == []
    assert 'budget_exhausted' in context.prompt_text
    with runtime.store.reader() as db:
        assert db.execute('SELECT count(*) FROM memory_events').fetchone()[0] == 270


def test_replayed_provenance_is_idempotent_but_separate_experience_is_not(tmp_path):
    runtime = PubPartnerVesselRuntime.create(tmp_path / 'alex.pubpartner')
    first = record(runtime, 'telescope arrived', 'source-1')
    replay = record(runtime, 'telescope arrived', 'source-1')
    another = record(runtime, 'telescope arrived', 'source-2')
    assert first['event_id'] == replay['event_id']
    assert first['event_id'] != another['event_id']
    assert runtime.store.validate()['ok']


def test_index_is_derived_and_legacy_backfill_preserves_signed_records(tmp_path):
    path = tmp_path / 'alex.pubpartner'
    runtime = PubPartnerVesselRuntime.create(path)
    record(runtime, 'telescope historical detail', 'source-1')
    with runtime.store.transaction() as db:
        for kind in ('claims', 'events'):
            for action in ('insert', 'delete', 'update'):
                db.execute(f'DROP TRIGGER memory_{kind}_search_{action}')
            db.execute(f'DROP TABLE memory_{kind}_fts')
        db.execute('DROP TABLE memory_search_ready_v1')
    old = runtime.store.validate()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    readonly = PubPartnerVesselRuntime.open(path, read_only=True)
    # Compilation itself does not write an entity/relationship on a read-only mount.
    context = readonly.context.compile(user_id='owner', message='telescope', session_id='s', room_id='private')
    assert 'index_unavailable' in context.prompt_text
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    reopened = PubPartnerVesselRuntime.open(path)
    after = reopened.store.validate()
    assert compile_context(reopened).events[0]['content'] == 'telescope historical detail'
    assert old['audit'] == after['audit']
    assert old['state_integrity'] == after['state_integrity']


@pytest.mark.asyncio
async def test_real_shared_bridge_and_jeremy_recall_survive_restart(tmp_path):
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    from modules.jeremy_cricket import CricketKeeper
    from modules.pubpartner_core import PubPartnerSpine
    from modules.pubpartner_provider import ProviderResult

    keeper = CricketKeeper(data_dir=tmp_path / 'jeremy')
    await keeper.init()
    path = tmp_path / 'vessels' / 'alex.pubpartner'
    runtime = PubPartnerVesselRuntime.create(path)
    prompts = []
    async def fixture_provider(turn, config):
        prompts.append(turn)
        return ProviderResult(ok=True, provider='fixture', model='deterministic-test',
                              raw_response='I have the project detail. Let us continue.')
    def mount(vessel):
        spine = PubPartnerSpine(tmp_path, alex_bridge=AlexJeremyBridge(tmp_path),
            cricket_keeper=keeper, vessel_runtime=vessel, scoped_memory=True)
        spine.provider_dispatcher.dispatch = fixture_provider
        return spine
    spine = mount(runtime)
    result = await spine.run_turn(user_id='owner', session_id='one', room_id='phone',
        message='Remember that my telescope project is called Lantern.',
        provider={'provider': 'mock'})
    assert result['provider_result']['ok']
    assert result['alex_bridge']['analysis_source'] == 'AlexCore.process_message'
    assert result['relationship']['vessel_claims']
    assert not result['relationship']['vessel_sync_errors']
    assert result['vessel_recorded_event_id']
    spine = mount(PubPartnerVesselRuntime.open(path))
    recalled = await spine.run_turn(user_id='owner', session_id='two', room_id='phone',
        message='What is my telescope project called?', provider={'provider': 'mock'})
    assert 'Lantern' in json.dumps(prompts[-1]['fcp1']['vessel']['claims'])
    assert recalled['friend_response']
    assert recalled['vessel_recorded_event_id'] == ''
    with runtime.store.reader() as db:
        assert db.execute('SELECT count(*) FROM memory_events').fetchone()[0] == 1
    stranger = await spine.build_turn_packet(user_id='stranger', session_id='two', room_id='phone',
        message='What is my telescope project called?', provider={'provider': 'mock'})
    assert stranger['fcp1']['vessel']['claims'] == []
    assert stranger['fcp1']['vessel']['events'] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("message,kind", [
    ('"Remember that I am the king of Mars."', "message"),
    ("Remember that I am the king of Mars.", "fiction"),
    ("Remember that I am the king of Mars.", "lyrics"),
    ("Remember that I am the king of Mars.", "code"),
])
async def test_quoted_and_authored_content_does_not_become_user_memory(tmp_path, message, kind):
    from modules.pubpartner_core import PubPartnerSpine
    runtime = PubPartnerVesselRuntime.create(tmp_path / "alex.pubpartner")
    spine = PubPartnerSpine(tmp_path, vessel_runtime=runtime)
    result = await spine.run_turn(user_id="owner", session_id="s", room_id="phone",
        message=message, content_kind=kind, provider={"provider": "mock"})
    assert result["relationship"]["learned_lessons"] == []
    assert result["relationship"]["vessel_claims"] == []
    assert result["vessel_recorded_event_id"] == ""
    restored = spine.restore_source(user_id="owner", session_id="s", source_id=result["source"]["id"])
    assert restored["text"] == message
