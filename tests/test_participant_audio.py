"""Audio contribution authorization, capabilities, frame bounds and leases."""
import struct
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from modules.participant_audio import create_participant_audio_router
from modules.route_security import current_identity
from modules.auth import create_access_token


def fixture():
    actor = {'user_id':'director','role':'owner','authenticated':True}
    now = [100.0]
    app = FastAPI();app.dependency_overrides[current_identity] = lambda:dict(actor)
    app.include_router(create_participant_audio_router(clock=lambda:now[0]))
    return TestClient(app),actor,now


def endpoint(r):
    return f'/api/participant-audio/rooms/{r["room"]}/peers/{r["peer"]}'


def ws_headers(actor='director',origin='http://testserver'):
    return {'Authorization':'Bearer '+create_access_token({'sub':actor,'role':'owner'}),'Origin':origin}


def test_auth_consent_capabilities_capacity_and_lease():
    client,actor,now=fixture()
    actor['authenticated']=False
    assert client.post('/api/participant-audio/rooms').status_code==401
    actor.update(authenticated=True,role='guest')
    assert client.post('/api/participant-audio/rooms').status_code==403
    actor['role']='owner';host=client.post('/api/participant-audio/rooms').json()
    path=f'/api/participant-audio/rooms/{host["room"]}/peers'
    assert client.post(path,json={'consent':False}).status_code==400
    assert client.post(path,json={'consent':True}).status_code==409
    with client.websocket_connect(endpoint(host)+'/media',headers=ws_headers()) as h:
        h.send_json({'key':host['key'],'sample_rate':48000});assert h.receive_json()=={'ok':True}
        for _ in range(8):assert client.post(path,json={'consent':True}).status_code==201
        assert client.post(path,json={'consent':True}).status_code==429
        assert client.delete(endpoint(host),headers={'X-Audio-Key':'wrong'}).status_code==404
        actor['user_id']='intruder'
        assert client.delete(endpoint(host),headers={'X-Audio-Key':host['key']}).status_code==404
        now[0]+=21
        assert client.post(path,json={'consent':True}).status_code==404


def test_real_socket_relay_identity_order_and_disconnect():
    client,actor,_=fixture();host=client.post('/api/participant-audio/rooms').json()
    with client.websocket_connect(endpoint(host)+'/media',headers=ws_headers()) as h:
        h.send_json({'key':host['key'],'sample_rate':48000});assert h.receive_json()=={'ok':True}
        actor['user_id']='performer'
        guest=client.post(f'/api/participant-audio/rooms/{host["room"]}/peers',json={'consent':True}).json()
        with client.websocket_connect(endpoint(guest)+'/media',headers=ws_headers('performer')) as g:
            g.send_json({'key':guest['key'],'sample_rate':48000});assert g.receive_json()=={'ok':True}
            source=h.receive_json();assert source['actor']=='performer' and source['peer']==guest['peer']
            packet=struct.pack('<Ihhh',0,100,200,-100)
            g.send_bytes(packet);assert h.receive_bytes()==bytes.fromhex(guest['peer'])+packet
            g.send_bytes(struct.pack('<Ih',4,0))
            assert h.receive_json()=={'type':'left','peer':guest['peer']}
            with pytest.raises(WebSocketDisconnect):g.receive_json()


@pytest.mark.parametrize('case',['origin','key','identity','oversize','host_publish'])
def test_socket_rejects_boundary_violations(case):
    client,actor,_=fixture();host=client.post('/api/participant-audio/rooms').json()
    headers=ws_headers('intruder' if case=='identity' else 'director','https://evil.invalid' if case=='origin' else 'http://testserver')
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(endpoint(host)+'/media',headers=headers) as ws:
            ws.send_json({'key':'wrong' if case=='key' else host['key'],'sample_rate':48000})
            if case in ('host_publish','oversize'):
                assert ws.receive_json()=={'ok':True};ws.send_bytes(b'\0'* (20000 if case=='oversize' else 6))
            ws.receive_json()
