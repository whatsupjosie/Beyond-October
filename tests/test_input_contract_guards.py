from __future__ import annotations

from starlette.testclient import TestClient

import main


def test_session_register_rejects_malformed_json():
    with TestClient(main.app) as client:
        response = client.post(
            '/api/session/register',
            content='{"user_id": ',
            headers={'content-type': 'application/json'},
        )
        assert response.status_code == 400
        assert response.json()['detail'] == 'Malformed JSON body'


def test_session_register_rejects_non_object_json():
    with TestClient(main.app) as client:
        response = client.post('/api/session/register', json=['not', 'a', 'dict'])
        assert response.status_code == 400
        assert response.json()['detail'] == 'JSON object body required'


def test_session_register_normalizes_roles_and_strings(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DATA_DIR', tmp_path)
    with TestClient(main.app) as client:
        response = client.post(
            '/api/session/register',
            headers={'X-Client-Id': 'josie'},
            json={
                'display_name': 'Josie' * 40,
                'session_id': 'sess',
                'project_id': 'proj',
                'session_role': ['host', 'host', 'director', '', 'camera', 'sound', 'writer', 'producer', 'extra'],
                'project_role': 'creator',
                'presence_mode': 'avatar_live',
                'availability': 'available',
            },
        )
        assert response.status_code == 200
        participant = response.json()['participant']
        assert participant['display_name'] == ('Josie' * 40)[:120]
        assert participant['project_role'] == ['creator']
        assert participant['session_role'] == ['host', 'director', 'camera', 'sound', 'writer', 'producer', 'extra'][:8]


def test_update_session_role_requires_target_user_id(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DATA_DIR', tmp_path)
    with TestClient(main.app) as client:
        register = client.post('/api/session/register', json={'session_id': 'sess', 'user_id': 'a'})
        assert register.status_code == 200
        response = client.post('/api/session/sess/role', json={'session_role': 'director'})
        assert response.status_code == 400
        assert response.json()['detail'] == 'target_user_id is required'


def test_dressing_room_security_code_rejects_unknown_action():
    with TestClient(main.app) as client:
        response = client.post('/api/dressing-room/security/code', json={'action': 'explode', 'code': '#123'})
        assert response.status_code == 400
        assert response.json()['detail'] == 'action must be set or disable'


def test_dressing_room_security_enter_requires_list_access_log():
    with TestClient(main.app) as client:
        response = client.post(
            '/api/dressing-room/security/enter',
            json={'room_owner_id': 'josie', 'acting_identity': 'guest', 'access_log': 'avatar_profile'},
        )
        assert response.status_code == 400
        assert response.json()['detail'] == 'access_log must be a list of strings'


def test_memory_event_rejects_non_object_payload():
    with TestClient(main.app) as client:
        response = client.post('/api/memory/events', json={'payload': ['bad']})
        assert response.status_code == 400
        assert response.json()['detail'] == 'payload must be an object'


def test_alex_jeremy_signal_rejects_non_object_payload():
    with TestClient(main.app) as client:
        response = client.post('/api/alex-jeremy/signal', json={'payload': ['bad']})
        assert response.status_code == 400
        assert response.json()['detail'] == 'payload must be an object'
