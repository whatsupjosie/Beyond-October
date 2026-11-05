"""Private migrations, explicit discovery, image isolation and concurrent edits."""
import io

from PIL import Image

from modules import userdb
from tests.test_production_notes import env


def test_setup_visibility_and_auth_responses_preserve_permanent_id(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from modules import auth, auth_routes

    monkeypatch.setattr(userdb, '_DB_PATH', tmp_path / 'users.db')
    userdb._sync_init_db()
    auth_routes.set_auth_instance(auth)
    app = FastAPI()
    app.include_router(auth_routes.router)
    with TestClient(app) as client:
        payload = {'username': 'profile-owner', 'password': 'strong-secret-A19!',
                   'confirm_password': 'strong-secret-A19!', 'profile_visibility': 'discoverable'}
        setup = client.post('/api/auth/setup', json=payload)
        assert setup.status_code == 201, setup.text
        uid = setup.json()['user_id']
        assert uid.startswith('u_') and uid != payload['username']
        profile = userdb._sync_get_profile(uid)
        assert profile['details']['discoverable'] is True
        assert profile['details']['public_fields'] == []
        assert client.post('/api/auth/setup', json=payload).status_code == 409
        userdb._sync_init_db()
        login = client.post('/api/auth/login', json={k:payload[k] for k in ('username', 'password')})
        assert login.json()['user_id'] == uid
        verified = client.get('/api/auth/verify', headers={'Authorization': 'Bearer ' + login.json()['access_token']})
        assert verified.json()['user_id'] == uid


def test_old_ids_survive_migration_and_details_start_private(env):
    client, auth, people, _ = env
    owner=auth('josie','owner'); guest=auth('pete','guest')
    before=client.get('/api/profile/me',headers=owner).json()
    assert before['details']=={'discoverable':False,'public_fields':[],'about':{},'onboarding_complete':False}
    assert client.get('/api/profiles',headers=guest).json()['profiles']==[]
    assert client.get('/api/profiles/'+before['user_id'],headers=guest).status_code==404
    userdb._sync_init_db()
    assert client.get('/api/profile/me',headers=owner).json()['user_id']==before['user_id']==people['josie']['user_id']


def test_discovery_discloses_only_explicit_fields_and_never_email(env):
    client, auth, people, _ = env
    owner=auth('josie','owner'); guest=auth('pete','guest')
    payload={'discoverable':True,'public_fields':['pronouns','portfolio'],
             'about':{'pronouns':'she/her','real_name':'Private real name','city':'Private city',
                      'portfolio':'https://portfolio.example/work','resume':'Private résumé'},'onboarding_complete':True}
    saved=client.patch('/api/profile/me',headers=owner,json={'details':payload,'revision':0})
    assert saved.status_code==200,saved.text
    card=client.get('/api/profiles/'+people['josie']['user_id'],headers=guest).json()
    assert card['about']=={'pronouns':'she/her','portfolio':'https://portfolio.example/work'}
    assert 'email' not in card and 'details' not in card
    found=client.get('/api/profiles?q=Josie',headers=guest).json()
    assert found['scope']=='this-host' and found['profiles']==[card]
    payload['discoverable']=False
    assert client.patch('/api/profile/me',headers=owner,json={'details':payload,'revision':1}).status_code==200
    assert client.get('/api/profiles/'+people['josie']['user_id'],headers=guest).status_code==404
    assert client.get('/api/profiles').status_code==401


def test_profile_revision_fences_stale_windows_and_bad_links_are_atomic(env):
    client, auth, _, _ = env
    owner=auth('josie','owner')
    assert client.patch('/api/profile/me',headers=owner,json={'details':{'about':{'pronouns':'she/her'}},'revision':0}).status_code==200
    assert client.patch('/api/profile/me',headers=owner,json={'display_name':'Stale window','revision':0}).status_code==409
    bad={'details':{'about':{'reel':'javascript:alert(1)'}},'display_name':'Bad write','revision':1}
    assert client.patch('/api/profile/me',headers=owner,json=bad).status_code==400
    me=client.get('/api/profile/me',headers=owner).json()
    assert me['display_name']=='Josie' and me['revision']==1 and me['details']['about']['pronouns']=='she/her'
    assert client.patch('/api/profile/me',headers=owner,json={'details':{'about':{'role':'owner'}}}).status_code==400
    assert client.patch('/api/profile/me',headers=owner,json={'details':None}).status_code==400


def test_photo_bytes_are_normalized_private_and_revision_protected(env):
    client, auth, people, _ = env
    owner=auth('josie','owner'); guest=auth('pete','guest')
    out=io.BytesIO(); Image.new('RGB',(900,800),'red').save(out,format='JPEG',comment=b'private metadata')
    response=client.post('/api/profile/photo?revision=0',headers=owner,content=out.getvalue())
    assert response.status_code==200,response.text
    assert response.json()['has_photo'] and response.json()['revision']==1
    endpoint='/api/profiles/'+people['josie']['user_id']+'/photo'
    assert client.get(endpoint,headers=guest).status_code==404
    photo=client.get(endpoint,headers=owner)
    assert photo.headers['cache-control']=='private, no-store'
    with Image.open(io.BytesIO(photo.content)) as image:
        assert image.format=='PNG' and max(image.size)==512 and not image.info
    assert client.post('/api/profile/photo?revision=0',headers=owner,content=out.getvalue()).status_code==409
    assert client.post('/api/profile/photo?revision=1',headers=owner,content=b'<svg>bad</svg>').status_code==400
    assert client.post('/api/profile/photo?revision=1',headers=owner,content=b'X'*(2*1024*1024+1)).status_code==413
    assert client.patch('/api/profile/me',headers=owner,json={'details':{'discoverable':True,'public_fields':['photo']},'revision':1}).status_code==200
    assert client.get(endpoint,headers=guest).content==photo.content
