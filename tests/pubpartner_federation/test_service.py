from fastapi.testclient import TestClient
from pubpartner_federation.service import Config, create_app

def test_manuscript_commit_returns_id(tmp_path):
    app=create_app(Config({'PP_ROLE':'resident','PP_DATA_DIR':str(tmp_path)})); c=TestClient(app)
    r=c.post('/api/manuscript/commit',json={'project_id':'novel_one','chapter_id':'ch3','content':'hello'})
    assert r.status_code==200 and r.json()['manuscript_id']=='novel_one:ch3'

def test_manuscript_readable_after_commit(tmp_path):
    app=create_app(Config({'PP_DATA_DIR':str(tmp_path)})); c=TestClient(app)
    c.post('/api/manuscript/commit',json={'project_id':'p','chapter_id':'c','content':'x'})
    r=c.get('/api/manuscript/p/c'); assert r.status_code==200 and r.json()['fields']['content']=='x'

def test_auth_when_configured(tmp_path):
    app=create_app(Config({'PP_DATA_DIR':str(tmp_path),'PP_API_KEY':'secret'})); c=TestClient(app)
    payload={'project_id':'p','chapter_id':'c','content':'x'}
    assert c.post('/api/manuscript/commit',json=payload).status_code==401
    assert c.post('/api/manuscript/commit',json=payload,headers={'Authorization':'Bearer secret'}).status_code==200

def test_candidate_capture_list_promote(tmp_path):
    app=create_app(Config({'PP_DATA_DIR':str(tmp_path)})); c=TestClient(app)
    r=c.post('/api/memory/candidates',json={'text':'remember this'}); cid=r.json()['candidate_id']
    assert len(c.get('/api/memory/candidates').json())==1
    r=c.post(f'/api/memory/candidates/{cid}/promote'); assert r.status_code==200 and r.json()['promoted_at'] is not None

def test_unknown_candidate_is_404(tmp_path):
    app=create_app(Config({'PP_DATA_DIR':str(tmp_path)})); c=TestClient(app)
    assert c.post('/api/memory/candidates/nope/promote').status_code==404

def test_sync_round_trip(tmp_path):
    a=create_app(Config({'PP_ROLE':'portable','PP_DATA_DIR':str(tmp_path/'a')})); b=create_app(Config({'PP_ROLE':'resident','PP_DATA_DIR':str(tmp_path/'b')}))
    ca,cb=TestClient(a),TestClient(b)
    ca.post('/api/manuscript/commit',json={'project_id':'p','chapter_id':'c','content':'portable'})
    env=ca.app.state.pp.engine.envelope().to_dict()
    assert cb.post('/api/sync',json={'envelope':env}).status_code==200
    assert cb.get('/api/manuscript/p/c').json()['fields']['content']=='portable'
