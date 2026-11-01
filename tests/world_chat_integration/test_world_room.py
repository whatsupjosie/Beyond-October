"""World Chat contract: authenticated shared room, BlackBox, and 2i isolation."""
from pathlib import Path
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from modules.auth import create_access_token
from modules.chat_rooms import create_chat_router, install_chat_websocket
from modules.hub import Hub
from modules.route_security import current_identity
from modules.writers_room import create_writers_room_router

ROOT = Path(__file__).resolve().parents[2]

def auth(user, role='guest'):
    return {'Authorization': 'Bearer ' + create_access_token({'sub':user,'role':role})}

@pytest.fixture
def built(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH','1')
    hub=Hub(tmp_path)
    witness=[]
    class Witness:
        def record_event(self, typ, **kw):
            witness.append((typ, kw)); return 'witness-test-receipt'
    hub.blackbox_witness=Witness()
    app=FastAPI()
    app.include_router(create_chat_router(hub,current_identity))
    app.include_router(create_writers_room_router(tmp_path))
    install_chat_websocket(app,hub,current_identity)
    return TestClient(app),hub,witness

def test_same_room_from_foresight_and_2i_no_sender_spoof_and_restart(built):
    c,hub,witness=built
    assert c.get('/api/chat/rooms/world').status_code==401
    payload={'text':'  The exact world message.  \n','user':'forged-owner','user_id':'forged-owner','role':'owner'}
    result=c.post('/api/chat/rooms/world/send',json=payload,headers=auth('josie')).json()
    assert result['user_id']=='josie'
    second=c.post('/api/chat/rooms/world/send',json={'text':'From the second window'},headers=auth('guest-two'))
    assert second.status_code==200
    # Both clients read the *same* append-only World room instead of an archived conversation.
    for user in ('josie','guest-two'):
        room=c.get('/api/chat/rooms/world?limit=100',headers=auth(user)).json()
        assert [m['user_id'] for m in room['recent_messages']]==['josie','guest-two']
        assert room['recent_messages'][0]['text']==payload['text']
    restarted_hub=Hub(hub.data_dir)
    assert __import__('asyncio').run(restarted_hub.get_recent_history('world',100))[0]['text']==payload['text']
    assert len(witness)==2
    assert all(event[0]=='chat.message' and event[1]['data']['room']=='world' for event in witness)
    assert witness[0][1]['data']['text']==payload['text']

def test_invalid_payload_and_nonpublic_room_guards(built):
    c,_,_=built
    for text in ('', '  ', None, {'not':'text'}, 'x'*10001):
        assert c.post('/api/chat/rooms/world/send',json={'text':text},headers=auth('josie')).status_code in (400,413)
    assert c.post('/api/chat/rooms/world/send',json=[],headers=auth('josie')).status_code==400
    assert c.get('/api/chat/rooms/world?limit=201',headers=auth('josie')).status_code==422
    assert c.get('/api/chat/rooms/studio',headers=auth('josie')).status_code==403
    assert c.post('/api/chat/rooms/studio/send',json={'text':'hello'},headers=auth('josie')).status_code==403
    assert c.get('/api/chat/rooms/studio',headers=auth('crew','crew')).status_code==200

def test_room_socket_requires_verified_identity_and_rejects_control_frames(built):
    c,hub,witness=built
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect('/ws/chat/world') as ws:
            ws.receive_json()
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect('/ws/chat/world?token=invalid') as ws:
            ws.receive_json()
    token=create_access_token({'sub':'verified-guest','role':'guest'})
    with c.websocket_connect('/ws/chat/world', headers={'Authorization':'Bearer '+token}) as ws:
        ws.receive_json() # presence
        ws.send_json({'type':'production_state','payload':{'recording':True}})
        assert ws.receive_json()['type']=='error'
        ws.send_json({'type':'chat','text':'Verified speaker','user':'forged','user_id':'forged','role':'owner'})
        reply=ws.receive_json()
        assert reply['type']=='chat'
        assert reply['payload']['user_id']=='verified-guest'
        assert reply['payload']['text']=='Verified speaker'
    assert len(witness)==1
    assert 'forged' not in json.dumps(__import__('asyncio').run(hub.get_recent_history('world',100)))

def test_world_messages_never_modify_manuscript_or_private_partner_history(built):
    c,_,_=built
    document={'title':'An unfinished chapter','expected_revision':0,'state':{
        'committed':['The opening line.'],'buffer':['A penciled line.'],'pool':[],
        'coWriting':True,'lockedLines':[0], 'partnerId':'alex',
        'conversations':{'alex':[{'role':'user','content':'Private thought'}]},
        'chapters':[{'title':'Chapter One','startLine':0}]}}
    assert c.put('/api/writers-room/documents/scene',json=document,headers=auth('josie')).status_code==200
    assert c.post('/api/chat/rooms/world/send',json={'text':'A world participant spoke.'},headers=auth('guest-two')).status_code==200
    restored=c.get('/api/writers-room/documents/scene',headers=auth('josie')).json()['state']
    assert restored==document['state']
    assert c.get('/api/writers-room/documents/scene',headers=auth('guest-two')).status_code==404

def test_ui_shared_api_and_deliberate_collab_commit():
    foresight=(ROOT/'static/foresight.html').read_text()
    writer=(ROOT/'2i/index.html').read_text()
    world=(ROOT/'static/world_chat_widget.js').read_text()
    assert "url:'/static/world_chat.html'" in foresight
    assert '/api/chat/rooms/world?limit=100' in world
    assert '/api/chat/rooms/world/send' in world
    assert 'data-world-chat' in writer and 'Your PubPartner' in writer
    assert "if (coWriting && buffer.some(line => line.trim()))" in writer
    assert 'if (coWriting && buffer.length) approveBuffer();' not in writer
    assert 'showDraftCrossing(approved)' in writer
    assert 'function exportManuscript()' in writer

def test_real_blackbox_witness_decodes_chat_as_chat_not_runtime_error(tmp_path):
    from blackbox_event_language.schema import decode_record
    from modules.blackbox_runtime import create_blackbox_witness
    import asyncio
    hub=Hub(tmp_path)
    witness=create_blackbox_witness(tmp_path,session_id='world_room_unit')
    hub.blackbox_witness=witness
    asyncio.run(hub.post_chat_message('world','writer','Verbatim public world message.'))
    assert witness.verify().ok
    rows=witness.path.read_text().splitlines()
    assert len(rows)==2, 'expected readiness plus exactly one chat message record'
    record=decode_record(rows[1])
    assert record['channel']['code']=='CHT'
    assert record['event']['code']=='MSG'
    assert record['actor']=='writer'
    assert record['payload']['text']=='Verbatim public world message.'
    assert record['payload']['room']=='world'

def test_full_shared_room_export_retains_all_text_and_uses_room_access_gate(built):
    c,_,_=built
    assert c.get('/api/chat/rooms/world/export').status_code==401
    assert c.get('/api/chat/rooms/world/export',headers=auth('writer')).status_code==404
    for i in range(105):
        assert c.post('/api/chat/rooms/world/send',json={'text':f'World line {i:03d}  '},headers=auth('writer')).status_code==200
    visible=c.get('/api/chat/rooms/world?limit=100',headers=auth('writer')).json()['recent_messages']
    assert len(visible)==100 and visible[0]['text']=='World line 005  '
    exported=c.get('/api/chat/rooms/world/export',headers=auth('writer'))
    assert exported.status_code==200
    lines=[json.loads(line) for line in exported.text.splitlines()]
    assert len(lines)==105 and lines[0]['text']=='World line 000  ' and lines[-1]['text']=='World line 104  '
    assert c.get('/api/chat/rooms/studio/export',headers=auth('writer')).status_code==403
    assert c.get('/api/chat/rooms/dm____writer____guest/export',headers=auth('writer')).status_code==404
