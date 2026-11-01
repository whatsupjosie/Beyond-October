"""Exercise assembled host contracts. Speech engines below are test doubles."""
import io
import wave
from unittest.mock import AsyncMock
from types import SimpleNamespace

from modules.auth import create_access_token


def headers(role='owner', who='contract-owner'):
    return {'Authorization': 'Bearer ' + create_access_token({'sub':who,'role':role})}


def test_speech_routes_reach_lifespan_engines(client, monkeypatch):
    import main
    assert main.stt_engine is main.app.state.stt_engine
    assert main.tts_engine is main.app.state.tts_engine
    transcription = AsyncMock(return_value={'ok':True,'text':'known audio','segments':[]})
    monkeypatch.setattr(main.stt_engine,'transcribe',transcription)
    response = client.post('/api/stt/transcribe',content=b'test audio',headers={'Content-Type':'audio/webm'})
    assert response.status_code == 200 and response.json()['text'] == 'known audio'
    out=io.BytesIO()
    with wave.open(out,'wb') as wav:
        wav.setparams((1,2,16000,0,'NONE','not compressed'));wav.writeframes(b'\0\0'*160)
    synthesis = AsyncMock(return_value={'ok':True,'audio':out.getvalue(),'mime_type':'audio/wav'})
    monkeypatch.setattr(main.tts_engine,'synthesize',synthesis)
    response=client.post('/api/tts/synthesize',json={'text':'test'})
    assert response.status_code == 200
    assert response.headers['content-type']=='audio/wav'
    assert response.content.startswith(b'RIFF')


def test_host_required_turn_auth_and_receipt(client, monkeypatch):
    import main
    request_turn=AsyncMock(return_value={'state':'completed','request_id':'abc'})
    monkeypatch.setattr(main.bot_manager,'request_turn',request_turn)
    assert client.post('/api/bots/pete/request-turn',json={}).status_code==403
    assert client.post('/api/bots/pete/request-turn',json={},headers=headers('guest')).status_code==403
    response=client.post('/api/bots/pete/request-turn',json={'direction':'Offer a thought'},headers=headers())
    assert response.status_code==200 and response.json()['ok']
    assert request_turn.call_args.kwargs['required'] is True


def test_legacy_personal_chat_delegates_to_scoped_canonical_spine(client,monkeypatch):
    import main
    turn=AsyncMock(return_value={'provider_result':{'ok':True,'model':'test','usage':{'profile':'test','backend':'test'}},
                                 'friend_response':'own words','receipt':{'receipt_id':'test'}})
    monkeypatch.setattr(main.app.state.pubpartner_spine,'run_turn',turn)
    assert client.post('/api/pub-partner-chat/message',json={'message':'Hi'}).status_code==401
    response=client.post('/api/pub-partner-chat/message',json={'message':'Hi','session_id':'scoped'},headers=headers())
    assert response.status_code==200,response.text
    assert response.json()['canonical_pipeline'] and response.json()['reply']=='own words'
    assert turn.call_args.kwargs['user_id']=='contract-owner'
    assert turn.call_args.kwargs['allow_fallback'] is False
    denied=client.post('/api/pub-partner-chat/message',json={'message':'Hi','user_id':'someone-else'},headers=headers())
    assert denied.status_code==403


async def _real_spine_legacy_contract(tmp_path, monkeypatch):
    import json
    from modules import ai_providers
    from modules.pubpartner_core import PubPartnerSpine
    from modules.pub_partner_chat import chat_with_pub_partner
    (tmp_path/'config').mkdir()
    (tmp_path/'config'/'ai_runtime.json').write_text(json.dumps({'active_profile':'local', 'profiles':{
        'local':{'backend':'ollama','model':'contract','enabled':True,'endpoint':'http://127.0.0.1:11434'}}}))
    fake=AsyncMock(return_value=SimpleNamespace(text='I remember the topic.',model='contract',backend='ollama'))
    monkeypatch.setattr(ai_providers,'generate_with_profile',fake)
    # Use declared legacy slot names to select our known runtime profile.
    from modules import pub_partner_chat
    from modules.ai_runtime import load_ai_runtime_config
    config=load_ai_runtime_config(tmp_path)
    monkeypatch.setattr(pub_partner_chat,'_resolve_profile',lambda config,role:(config.profiles['local'],'alex',{'fallback_profile':''}))
    spine=PubPartnerSpine(tmp_path/'runtime',scoped_memory=True)
    spine.provider_dispatcher.runtime_repo_root=tmp_path
    result=await chat_with_pub_partner(repo_root=tmp_path,data_dir=tmp_path/'runtime',
        body={'message':'Discuss our topic','user_id':'alice','session_id':'one'},spine=spine)
    assert result['ok'],result
    assert result['canonical_pipeline']
    assert result['receipt']
    assert fake.await_count==1
    assert 'Discuss our topic' in fake.call_args.args[2]


def test_actual_spine_accepts_trusted_legacy_profile(tmp_path,monkeypatch):
    import asyncio
    asyncio.run(_real_spine_legacy_contract(tmp_path,monkeypatch))


def test_program_audio_command_feed_respects_room_roles(client):
    private=client.post('/api/program-audio/event',headers=headers(),json={
        'action':'play','room':'controlroom','url':'/private-test.wav','bus':'dialogue'})
    assert private.status_code==200,private.text
    sequence=private.json()['event']['sequence']
    guest=client.get('/api/program-audio/events',params={'after':sequence-1},headers=headers('guest','listener'))
    assert guest.status_code==200 and not guest.json()['events']
    owner=client.get('/api/program-audio/events',params={'after':sequence-1},headers=headers())
    assert owner.json()['events'][0]['url']=='/private-test.wav'
    blocked=client.post('/api/program-audio/event',headers=headers(),json={
        'action':'play','room':'dressing','url':'/test.wav'})
    assert blocked.status_code==403
    allowed=client.post('/api/program-audio/event',headers=headers(),json={
        'action':'play','room':'dressing','url':'/call.wav','director_announcement':True})
    assert allowed.status_code==200 and allowed.json()['event']['authorized_director']
