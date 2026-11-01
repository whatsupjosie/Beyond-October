import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules import pubpartner_routes as routes
from modules.route_security import current_identity


def client(monkeypatch):
    monkeypatch.setenv('PUBCAST_LOCAL_MODEL_URL','http://127.0.0.1:8111/v1')
    monkeypatch.setenv('PUBCAST_LOCAL_MODEL_KEY','launcher-secret')
    seen=[]
    class Spine:
        async def run_turn(self,**kwargs):
            seen.append(kwargs)
            return {'ok':False,'provider_result':{'ok':False,'error':'synthetic unavailable'},'friend_response':''}
    app=FastAPI();app.state.pubpartner_spine=Spine()
    app.dependency_overrides[current_identity]=lambda:{'user_id':'test-'+uuid.uuid4().hex,'role':'guest'}
    app.include_router(routes.router)
    return TestClient(app),seen


def test_provider_diagnostic_cannot_select_server_env_secret(monkeypatch):
    c,seen=client(monkeypatch)
    result=c.post('/api/pubpartner/providers/test',json={'provider':{
        'provider':'openai_compatible','base_url':'https://example.invalid/v1',
        'model':'x','allow_inline_key':True,'api_key_env':'PUBCAST_LOCAL_MODEL_KEY',
        'api_key':'inline','extra_headers':{'Authorization':'override'}}})
    assert result.status_code==200
    cfg=seen[0]['provider']
    assert not {'api_key_env','api_key','allow_inline_key','extra_headers'} & cfg.keys()
    assert 'launcher-secret' not in result.text


def test_legacy_live_turn_route_defaults_to_real_provider_without_fallback(monkeypatch):
    c,seen=client(monkeypatch)
    c.post('/api/pubpartner/turns',json={'message':'hi','generate_response':True})
    assert seen[0]['provider']['model']=='smollm2'
    assert seen[0]['allow_fallback'] is False


def test_fallback_flag_requires_boolean(monkeypatch):
    c,seen=client(monkeypatch)
    assert c.post('/api/pubpartner/turns',json={'message':'hi','generate_response':True,'allow_fallback':'false'}).status_code==400
    assert not seen
