"""Two real host processes with separate owners, data roots, keys and JWT secrets."""
from contextlib import contextmanager
import sqlite3

from tests.test_human_profile_onboarding_browser import fresh_host
from tests.test_guest_identity import CONSENTS


def setup(api, name):
    password = 'independent-owner-password-A19!'
    result = api.post('/api/auth/setup', json={'username': name, 'password': password, 'confirm_password': password})
    assert result.status_code == 201, result.text
    return result.json(), {'Authorization': 'Bearer ' + result.json()['access_token']}


def test_two_copies_keep_own_identity_and_guest_cannot_use_owner_powers(tmp_path):
    start = contextmanager(fresh_host.__wrapped__)
    with start(tmp_path/'production') as (host_url, host), start(tmp_path/'visitor') as (home_url, home):
        owner, owner_headers = setup(host, 'production-owner')
        human, home_headers = setup(home, 'visiting-owner')
        assert human['user_id'] != owner['user_id']
        assert host.get('/api/profile/me', headers=home_headers).status_code == 401
        assert home.get('/api/profile/me', headers=owner_headers).status_code == 401
        invite = host.post('/api/guests/invites', headers=owner_headers, json={}).json()['invite_code']
        challenge = host.post('/api/guests/challenge', json={'invite_code': invite}).json()
        signed = home.post('/api/guests/sign', headers=home_headers,
                           json={'challenge': challenge['challenge'], 'consents': CONSENTS})
        assert signed.status_code == 200, signed.text
        submitted = host.post('/api/guests/request', json=signed.json())
        assert submitted.status_code == 201, submitted.text
        ticket = {'poll_token': challenge['poll_token']}
        assert 'access_token' not in host.post('/api/guests/status', json=ticket).json()
        pending = host.get('/api/guests/pending', headers=owner_headers).json()['pending'][0]
        assert pending['card']['user_id'] == human['user_id'] and pending['known_key'] is False
        accepted = host.post('/api/guests/entries/'+pending['entry_id']+'/approve', headers=owner_headers,
                             json={'fingerprint': pending['fingerprint']})
        assert accepted.status_code == 200, accepted.text
        session = host.post('/api/guests/status', json=ticket)
        assert session.status_code == 200, session.text
        guest = {'Authorization': 'Bearer ' + session.json()['access_token']}
        me = host.get('/api/profile/me', headers=guest).json()
        assert me['user_id'] == human['user_id'] and me['visiting']
        assert host.post('/api/guests/invites', headers=guest, json={}).status_code == 403
        assert host.post('/api/guests/sign', headers=guest, json={'challenge': challenge['challenge'], 'consents': CONSENTS}).status_code == 403
        assert home.get('/api/profile/me', headers=guest).status_code == 401
        note = host.post('/api/notes', headers=owner_headers,
                         json={'subject': 'Production call', 'to': [human['user_id']]})
        assert note.status_code == 201, note.text
        assert host.get('/api/notes', headers=guest).json()['notes'][0]['subject'] == 'Production call'
        for directory in ['production', 'visitor']:
            with sqlite3.connect(tmp_path/directory/'data'/'users.db') as db:
                assert db.execute('SELECT count(*) FROM users').fetchone()[0] == 1
        assert host.post('/api/guests/entries/'+pending['entry_id']+'/revoke', headers=owner_headers).status_code == 200
        assert host.get('/api/profile/me', headers=guest).status_code == 401
