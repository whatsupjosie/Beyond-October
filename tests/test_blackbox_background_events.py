"""Real durable event paths; generated bot text is not a live-provider test."""
import json
from unittest.mock import AsyncMock

import pytest

from blackbox_event_language.schema import decode_record
from blackbox_recorder import map_pubcast_event
from modules.blackbox_runtime import create_blackbox_witness
from modules.hub import Hub


def records(witness):
    return [decode_record(line) for line in witness.path.read_text().splitlines()]


def test_nested_details_round_trip_without_losing_event_identity():
    data = {'event_type':'untrusted-detail', 'source_name':'forged',
            'judgment':{'steps':['a', {'text':'exact\n☕|,: reply'}], 'allowed':False}}
    mapped = map_pubcast_event({'event_type':'system.event', 'source':'jeremy', 'data':data})
    assert json.loads(mapped.payload['data_json']) == data
    assert mapped.payload['event_type'] == 'system.event'
    assert mapped.payload['source_name'] == 'jeremy'


@pytest.mark.asyncio
async def test_system_event_is_witnessed_once_without_listeners_and_survives_reopen(tmp_path):
    hub = Hub(tmp_path); witness = create_blackbox_witness(tmp_path, session_id='background')
    hub.blackbox_witness = witness
    event = {'type':'production_state', 'payload':{'stage':{'scene':'set-1'}, 'ready':False}}
    await hub.broadcast_system_event(event)
    witness.close()
    reopened = create_blackbox_witness(tmp_path, session_id='background')
    found = [r for r in records(reopened) if r['payload'].get('event_type')=='system.event']
    assert len(found)==1
    assert json.loads(found[0]['payload']['data_json'])['event']==event
    assert reopened.verify().ok
    reopened.close()


def test_bridge_audit_reaches_both_existing_log_and_verified_ledger(tmp_path):
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    from modules.dressing_room_security import log_black_box_event
    witness = create_blackbox_witness(tmp_path)
    bridge = AlexJeremyBridge(tmp_path, blackbox_logger=witness.internal_audit_logger(log_black_box_event))
    assert bridge._record_bridge_event('alex_message_analysis', user_id='owner', session_id='session',
        room_id='studio', status='ok', fields={'alex_state':{'tone':'steady'}, 'token':'excluded'})
    witness.close()
    audit = [r for r in records(witness) if r['payload'].get('event_type')=='internal.audit']
    assert len(audit)==1 and audit[0]['channel']['code']=='AIT'
    event = json.loads(audit[0]['payload']['data_json'])['event']
    assert event['event_type']=='alex_message_analysis'
    assert event['alex_state']=={'tone':'steady'} and 'token' not in event
    assert json.loads((tmp_path/'black_box'/'dressing_room_access.jsonl').read_text())==event
    assert witness.verify().ok


def test_internal_audit_failure_is_not_reported_as_approval_success(tmp_path):
    witness = create_blackbox_witness(tmp_path)
    witness.close()
    logger = witness.internal_audit_logger(lambda data_dir, event: None)
    with pytest.raises(OSError, match='receipt failed'):
        logger(tmp_path, {'event_type':'pub_manager_human_decision','status':'human_approved'})


def test_real_host_records_chat_coordination_system_events_and_restarts(tmp_path):
    from tests.host_lifespan_helpers import run_isolated_host
    run_isolated_host(r'''
import json
from pathlib import Path
from starlette.testclient import TestClient
from blackbox_event_language.schema import decode_record
import main
from modules.auth import create_access_token

with TestClient(main.app) as client:
    token = create_access_token({'sub':'test-owner','role':'owner'})
    headers = {'Authorization':'Bearer '+token}
    # This test exercises event persistence, not live model availability.
    main.hub.on_chat_callback = None
    exact = 'Hello, from chat: preserve this.\n☕|%'
    response = client.post('/api/chat/rooms/world/send', headers=headers, json={'text':exact})
    assert response.status_code==200, response.text
    message_id = response.json()['message_id']
    response = client.post('/api/state/production', headers=headers, json={})
    assert response.status_code==200, response.text
    spine = main.app.state.pubpartner_spine
    async def turn():
        return await spine.run_turn(user_id='test-owner', session_id='bbx-audit',
            room_id='pubpartner', message='A coordination test, with exact punctuation.',
            provider={'provider':'mock'}, allow_fallback=False)
    result = client.portal.call(turn)
    assert result['provider_result']['provider']=='mock'
    assert result['blackbox_committed'] and result['blackbox_started']
    witness = main.blackbox_witness
    assert witness.verify().ok

events = [decode_record(line) for line in witness.path.read_text().splitlines()]
chat = [r for r in events if r['payload'].get('event_type')=='chat.message' and r['payload'].get('message_id')==message_id]
assert len(chat)==1 and chat[0]['payload']['text']==exact
assert any(r['payload'].get('event_type')=='system.event' for r in events)
assert any(r['payload'].get('event_type')=='internal.audit' for r in events)
starts = [r for r in events if r['payload'].get('event_type')=='partner.turn_started']
assert len(starts)==1
details = json.loads(starts[0]['payload']['data_json'])
assert details['coordination']['text']==result['jeremy_whisper']
assert details['coordination']['recipient']==result['fcp1']['f']['id']
assert details['turn_id']==result['turn_id']
assert any(r['payload'].get('event_type')=='partner.private_turn' and
           r['payload']['reply']==result['friend_response'] for r in events)
''', tmp_path)
    run_isolated_host(r'''
from starlette.testclient import TestClient
from blackbox_recorder import AppendOnlyBlackBoxRecorder
from blackbox_event_language.schema import decode_record
import main
with TestClient(main.app) as client:
    async def history():
        return await main.hub.get_recent_history('world',10)
    assert client.portal.call(history)[0]['text']=='Hello, from chat: preserve this.\n☕|%'
    paths=list((main.DATA_DIR/'blackbox').glob('*.bbx'))
    assert len(paths)>=2
    for path in paths:
        recorder=AppendOnlyBlackBoxRecorder(path,path.stem)
        assert recorder.verify().ok
    events=[decode_record(line) for path in paths for line in path.read_text().splitlines()]
    assert sum(r['payload'].get('event_type')=='partner.turn_started' for r in events)==1
''', tmp_path)


@pytest.mark.asyncio
async def test_requested_bot_turn_has_ordered_states_and_exact_chat_receipt(tmp_path):
    from modules.bots import BotManager
    from modules.models import BotConfig, BotProvider
    hub = Hub(tmp_path); witness = create_blackbox_witness(tmp_path);hub.blackbox_witness=witness
    bot = BotManager(tmp_path, hub)
    bot.upsert_config(BotConfig(bot_id='test',name='Test',provider=BotProvider.OLLAMA,
                              model='test', api_key_env='', rooms=['studio']))
    bot._call_provider = AsyncMock(return_value='An exact bot reply, with punctuation: yes.\n☕|%')
    result = await bot.request_turn('test','studio','Discuss this',actor='system:jeremy',required=True)
    assert result['state']=='completed'
    witness.close()
    decoded = records(witness)
    states = [r for r in decoded if r['payload'].get('event_type')=='partner.turn_request']
    assert [r['payload']['state'] for r in states]==['requested','speaking','completed']
    assert all(r['channel']['code']=='ACT' for r in states)
    chats = [r for r in decoded if r['payload'].get('event_type')=='chat.message']
    assert len(chats)==1 and chats[0]['actor']=='bot-test'
    assert chats[0]['payload']['text']=='An exact bot reply, with punctuation: yes.\n☕|%'
    history = await Hub(tmp_path).get_recent_history('studio',10)
    assert history[0]['message_id']==chats[0]['payload']['message_id']
    generations = [r for r in decoded if r['payload'].get('event_type')=='partner.generation']
    assert [r['payload']['state'] for r in generations]==['started','completed']
    assert generations[-1]['payload']['message_id']==chats[0]['payload']['message_id']
    assert generations[0]['payload']['generation_id']==generations[-1]['payload']['generation_id']
    assert states[0]['payload']['hint']=='Discuss this'
    assert witness.verify().ok


@pytest.mark.asyncio
async def test_automatic_bot_failure_is_journalled_without_inventing_chat(tmp_path):
    from modules.bots import BotManager
    from modules.models import BotConfig, BotProvider
    hub = Hub(tmp_path); witness = create_blackbox_witness(tmp_path);hub.blackbox_witness=witness
    bot = BotManager(tmp_path, hub)
    bot.upsert_config(BotConfig(bot_id='test',name='Test',provider=BotProvider.OLLAMA,
                              model='test', api_key_env='', rooms=['studio']))
    bot._call_provider = AsyncMock(side_effect=RuntimeError('Provider unavailable, retry later'))
    result = await bot._generate_and_send(bot._sessions['test'],
        {'room':'studio', 'message_id':'trigger-id', 'text':'Question', 'nudge':True})
    assert not result['ok']
    witness.close()
    decoded = records(witness)
    generations = [r for r in decoded if r['payload'].get('event_type')=='partner.generation']
    assert [r['payload']['state'] for r in generations]==['started','failed']
    assert generations[-1]['payload']['error']=='Provider unavailable, retry later'
    assert generations[-1]['payload']['trigger_message_id']=='trigger-id'
    assert not any(r['payload'].get('event_type')=='chat.message' for r in decoded)
    assert witness.verify().ok
