"""Exercise Primp's actual host mounts and session contract in an isolated process."""
import os
from pathlib import Path
import subprocess
import sys


def test_primp_real_host_auth_and_static_mounts(tmp_path):
    env = dict(os.environ, PUBCAST_DATA_DIR=str(tmp_path), PUBCAST_ENFORCE_AUTH='1')
    probe = r'''
import asyncio
import secrets
import os
os.environ['PUBCAST_JWT_SECRET'] = secrets.token_urlsafe(48)
from fastapi.testclient import TestClient
import main
from modules import userdb
with TestClient(main.app) as client:
    assert client.get('/health').status_code == 200
    assert client.get('/api/auth/status').json()['auth_enforced'] is True
    assert client.get('/api/auth/verify').status_code == 401
    assert asyncio.run(userdb.create_user('primp-audit', 'session-only-'+secrets.token_hex(16), role='owner'))
    # Use real password login, not a fabricated token.
    password = 'session-only-'+secrets.token_hex(16)
    assert asyncio.run(userdb.create_user('primp-login', password, role='owner'))
    login = client.post('/api/auth/login', json={'username':'primp-login','password':password})
    assert login.status_code == 200, login.text
    headers = {'Authorization':'Bearer '+login.json()['access_token']}
    verified=client.get('/api/auth/verify',headers=headers)
    assert verified.status_code == 200 and verified.json()['username']=='primp-login'
    assert verified.json()['valid'] is True
    for path in ['/static/primp.html','/static/primp/app.mjs','/static/primp/uv-islands.mjs','/static/reach_auth.js','/static/primp/avatars/manny.glb','/static/primp/avatars/sheila.glb']:
        result=client.get(path,headers=headers)
        assert result.status_code==200, (path,result.status_code)
        if path.endswith('.glb'): assert result.content[:4]==b'glTF'
    assert client.get('/api/auth/verify',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert client.post('/api/auth/logout').status_code==200
    assert 'pubcast_ws_session' not in client.cookies
# Reenter real host lifespan and confirm mounts/session verifier remain usable.
with TestClient(main.app) as client:
    assert client.get('/health').status_code==200
    assert client.get('/static/primp.html').status_code==200
    assert client.get('/api/auth/verify',headers=headers).status_code==200
print('PRIMP_HOST_ACCEPTED')
'''
    completed = subprocess.run([sys.executable, '-c', probe], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True, timeout=150)
    assert completed.returncode == 0, (completed.stdout + completed.stderr)[-20000:]
    assert 'PRIMP_HOST_ACCEPTED' in completed.stdout
