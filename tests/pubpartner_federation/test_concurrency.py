from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from pubpartner_federation.service import Config, create_app

def test_concurrent_manuscript_commits_do_not_crash_or_corrupt(tmp_path):
    c=TestClient(create_app(Config({'PP_ROLE':'resident','PP_DATA_DIR':str(tmp_path)})))
    def commit(i): return c.post('/api/manuscript/commit',json={'project_id':'novel_one','chapter_id':f'ch{i%5}','content':f'revision {i}'})
    with ThreadPoolExecutor(max_workers=16) as pool: results=list(pool.map(commit,range(40)))
    assert all(r.status_code==200 for r in results)
    for i in range(5):
        r=c.get(f'/api/manuscript/novel_one/ch{i}'); assert r.status_code==200; assert r.json()['fields']['content'].startswith('revision ')

def test_concurrent_candidate_capture_all_persist(tmp_path):
    c=TestClient(create_app(Config({'PP_ROLE':'portable','PP_DATA_DIR':str(tmp_path)})))
    with ThreadPoolExecutor(max_workers=16) as pool: results=list(pool.map(lambda i:c.post('/api/memory/candidates',json={'text':f'moment {i}'}),range(30)))
    assert all(r.status_code==200 for r in results)
    ids={r.json()['candidate_id'] for r in results}; assert len(ids)==30; assert len(c.get('/api/memory/candidates').json())==30
